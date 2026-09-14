import json
import re
from pathlib import Path

from langchain_huggingface import HuggingFaceEmbeddings
from langchain_community.vectorstores import FAISS


# ============================================================
# SHARED PATTERNS
# ============================================================

# Matches a real-world model number in either style: letters-first
# (e.g. "HSU-18HFPAB", "SA-280G") or digits-first (e.g. "6500X",
# "65Q7Q"). Defined once here and reused by extract_query_info()
# (single-model lookup, tries letters-first before digits-first) and
# find_comparison_products() (multi-model comparisons, needs every
# token so the two are combined) — instead of three separate copies
# that could quietly drift out of sync.
MODEL_PATTERN_LETTERS_FIRST = r"\b(?=[a-z0-9-]*\d)(?=[a-z0-9-]*[a-z])[a-z][a-z0-9-]{1,16}\b"
MODEL_PATTERN_DIGITS_FIRST = r"\b\d[a-z0-9-]{1,16}\b"


# ============================================================
# PATHS
# ============================================================

BASE_DIR = Path(__file__).resolve().parents[3]

DATA_FILE = BASE_DIR / "data" / "products.json"
FAISS_DIR = BASE_DIR / "data" / "faiss_index"


# ============================================================
# LOAD PRODUCTS (lazy)
# ============================================================

_products = None


def get_products():

    global _products

    if _products is None:

        with open(DATA_FILE, "r", encoding="utf-8") as f:
            _products = json.load(f)

    return _products


# ============================================================
# LOAD FAISS VECTOR STORE (lazy)
# ============================================================

_vector_store = None


def get_vector_store():

    global _vector_store

    if _vector_store is None:

        print("Loading embedding model...")

        embeddings = HuggingFaceEmbeddings(
            model_name="sentence-transformers/all-MiniLM-L6-v2"
        )

        print("Loading FAISS vector store...")

        _vector_store = FAISS.load_local(
            str(FAISS_DIR),
            embeddings,
            allow_dangerous_deserialization=True
        )

        print("FAISS vector store loaded successfully!")

    return _vector_store


# ============================================================
# BASIC HELPERS
# ============================================================

def normalize_text(text):
    if text is None:
        return ""

    text = str(text).lower()

    # Protect decimal points between digits (e.g. "1.5") before
    # stripping punctuation, otherwise "1.5 Ton" becomes "1 5 ton"
    # and any decimal capacity (Ton/Kg) extraction or matching
    # silently breaks.
    text = re.sub(r"(?<=\d)\.(?=\d)", "decimalpoint", text)
    text = re.sub(r"[^a-z0-9]+", " ", text)
    text = text.replace("decimalpoint", ".")

    text = re.sub(r"\s+", " ", text)

    return text.strip()


def normalize_model(text):
    text = normalize_text(text)
    return text.replace(" ", "")


def _levenshtein(a, b):
    if a == b:
        return 0
    if len(a) < len(b):
        a, b = b, a
    previous_row = list(range(len(b) + 1))
    for i, ca in enumerate(a, start=1):
        current_row = [i]
        for j, cb in enumerate(b, start=1):
            insertions = previous_row[j] + 1
            deletions = current_row[j - 1] + 1
            substitutions = previous_row[j - 1] + (ca != cb)
            current_row.append(min(insertions, deletions, substitutions))
        previous_row = current_row
    return previous_row[-1]


def fuzzy_word_present(text, target_word, max_distance=1):
    """
    Returns True if any whitespace-separated word in `text` is within
    `max_distance` character edits of `target_word`. Used to tolerate
    common typos in category words (e.g. "conditoners" for
    "conditioners") without needing an exact-phrase match.
    """

    for word in text.split():

        if abs(len(word) - len(target_word)) > max_distance:
            continue

        if _levenshtein(word, target_word) <= max_distance:
            return True

    return False


def get_product_name(product):
    return normalize_text(product.get("name", ""))


def get_product_text(product):
    parts = []

    for key in [
        "name",
        "description",
        "specifications",
        "categories",
        "tags",
        "content",
    ]:

        value = product.get(key)

        if value is None:
            continue

        if isinstance(value, list):
            parts.extend(str(x) for x in value)

        elif isinstance(value, dict):
            parts.extend(
                f"{k} {v}"
                for k, v in value.items()
            )

        else:
            parts.append(str(value))

    return normalize_text(" ".join(parts))


def get_capacity_text(product):
    """
    A narrow text source used ONLY for capacity (kg/ton) matching.
    Deliberately excludes the free-text description, which for combo
    products (e.g. washer-dryers) can mention several DIFFERENT
    capacity numbers in different contexts — e.g. a "15 Kg wash / 8 Kg
    dry" combo machine's description repeatedly says "8 Kg" when
    talking about the DRYER, which used to falsely match a query for
    "8 kg washing machines" even though the actual wash capacity is
    15 Kg. We trust only the product name and any specification whose
    key looks capacity-related — never the marketing description.
    """

    parts = [product.get("name") or ""]

    specifications = product.get("specifications") or {}

    for key, value in specifications.items():
        if "capacity" in key.lower():
            parts.append(str(value))

    return normalize_text(" ".join(parts))


# ============================================================
# QUERY INFORMATION
# ============================================================

def extract_query_info(query):

    q = normalize_text(query)

    # Model detection needs the hyphen preserved (e.g. "HSU-18HFPAB"),
    # but normalize_text() turns hyphens into spaces, which breaks
    # the model regex. So we keep a separate lowercase-only copy
    # (punctuation intact) just for model matching.
    q_raw = query.lower()

    info = {
        "brand": None,
        "model": None,
        "kg": None,
        "ton": None,
        "product_type": None,
        "door": None,
        "washing_type": None,
    }

    brands = [
        "kenwood", "samsung", "haier", "lg", "dawlance", "pel",
        "orient", "homage", "westpoint", "philips", "boss",
        "canon", "sony", "panasonic", "toshiba", "sharp",
        "hisense", "gree", "varioline",
    ]

    for brand in brands:
        if re.search(rf"\b{re.escape(brand)}\b", q):
            info["brand"] = brand
            break

    model_patterns = [MODEL_PATTERN_LETTERS_FIRST, MODEL_PATTERN_DIGITS_FIRST]

    for pattern in model_patterns:
        match = re.search(pattern, q_raw)
        if match:
            candidate = match.group(0)
            if not candidate.isdigit():
                info["model"] = normalize_model(candidate)
                break

    kg_match = re.search(
        r"\b(\d+(?:\.\d+)?)\s*(?:kg|kgs|kilogram|kilograms)\b", q_raw
    )
    if kg_match:
        info["kg"] = float(kg_match.group(1))

    ton_match = re.search(
        r"\b(\d+(?:\.\d+)?)\s*ton\b", q_raw
    )
    if ton_match:
        info["ton"] = float(ton_match.group(1))

    # Each product type maps to: exact phrases to match, an optional
    # regex for abbreviations (e.g. "AC"/"ACs"), and words to check
    # with typo tolerance. Adding a new category is one new row here
    # instead of a new elif branch.
    PRODUCT_TYPE_RULES = [
        ("washing machine", ["washing machine", "washing machines", "washer", "washers"], None, ["washing"]),
        ("refrigerator", ["refrigerator", "refrigerators", "fridge", "fridges"], None, ["refrigerator", "refrigerators"]),
        ("deep freezer", ["deep freezer", "deep freezers", "freezer", "freezers"], None, ["freezer", "freezers"]),
        ("air conditioner", ["air conditioner", "air conditioners"], r"\bacs?\b", ["conditioner", "conditioners"]),
        ("microwave", ["microwave", "microwave oven"], None, ["microwave"]),
        ("television", ["tv", "television", "smart tv"], None, ["television"]),
        ("air fryer", ["air fryer", "air fryers"], None, ["fryer"]),
        ("blender", ["blender", "blenders"], None, ["blender"]),
    ]

    for type_name, phrases, abbrev_pattern, fuzzy_words in PRODUCT_TYPE_RULES:

        phrase_match = any(phrase in q for phrase in phrases)
        abbrev_match = bool(abbrev_pattern and re.search(abbrev_pattern, q))
        fuzzy_match = any(fuzzy_word_present(q, word) for word in fuzzy_words)

        if phrase_match or abbrev_match or fuzzy_match:
            info["product_type"] = type_name
            break

    if "double door" in q:
        info["door"] = "double door"
    elif "single door" in q:
        info["door"] = "single door"
    elif "twin door" in q:
        info["door"] = "twin door"

    if "top load" in q or "topload" in q:
        info["washing_type"] = "top load"
    elif "front load" in q or "frontload" in q:
        info["washing_type"] = "front load"
    elif "twin tub" in q:
        info["washing_type"] = "twin tub"

    return info


# ============================================================
# BRAND MATCH
# ============================================================

def brand_matches(product, brand):
    if not brand:
        return True
    name = get_product_name(product)
    return bool(re.search(rf"\b{re.escape(brand)}\b", name))


# ============================================================
# PRODUCT TYPE MATCH
# ============================================================

def product_type_matches(product, product_type):
    if not product_type:
        return True

    name = get_product_name(product)
    text = get_product_text(product)

    if product_type == "washing machine":
        return ("washing machine" in name or "washer" in name
                or ("washing" in name and "machine" in name))
    if product_type == "refrigerator":
        return "refrigerator" in name or "fridge" in name
    if product_type == "deep freezer":
        return "deep freezer" in name or "freezer" in name
    if product_type == "air conditioner":
        return (
            "air conditioner" in name
            or "air conditioner" in text
            or bool(re.search(r"\bacs?\b", name))
        )
    if product_type == "microwave":
        return "microwave" in name
    if product_type == "television":
        return "tv" in name or "television" in name
    if product_type == "air fryer":
        return "air fryer" in name
    if product_type == "blender":
        return "blender" in name

    return True


# ============================================================
# MODEL MATCH
# ============================================================

def get_product_model_tokens(product):
    """
    Break the product name into individual alphanumeric tokens (split
    on any non-alphanumeric character), plus every pair of ADJACENT
    tokens concatenated together — this lets us still match model
    numbers that got split by a hyphen in the source name (e.g.
    "KLU-18B03S" -> "klu18b03s") WITHOUT allowing accidental substring
    collisions from unrelated numbers (e.g. a short query token like
    "s24" incorrectly matching inside "ES-24NV01WT3").
    """

    raw_tokens = re.findall(r"[a-z0-9]+", (product.get("name") or "").lower())

    candidates = set(raw_tokens)

    for i in range(len(raw_tokens) - 1):
        candidates.add(raw_tokens[i] + raw_tokens[i + 1])

    return candidates


def model_matches(product, model):
    if not model:
        return False
    return model in get_product_model_tokens(product)


# ============================================================
# KG MATCH
# ============================================================

def kg_matches(product, kg):
    if kg is None:
        return True

    text = get_capacity_text(product)

    patterns = [
        rf"\b{kg:g}\s*kg\b",
        rf"\b{kg:g}\s*kgs\b",
        rf"\b{kg:g}\s*kilogram",
    ]

    return any(
        re.search(pattern, text)
        for pattern in patterns
    )


# ============================================================
# DOOR MATCH
# ============================================================

def door_matches(product, door):
    if not door:
        return True
    name = get_product_name(product)
    if door == "double door":
        return "double door" in name
    if door == "single door":
        return "single door" in name
    if door == "twin door":
        return "twin door" in name
    return True


def ton_matches(product, ton):
    if ton is None:
        return True

    text = get_capacity_text(product)

    pattern = rf"\b{ton:g}\s*ton\b"

    return bool(re.search(pattern, text))


# ============================================================
# WASHING TYPE MATCH
# ============================================================

def washing_type_matches(product, washing_type):
    if not washing_type:
        return True

    name = get_product_name(product)
    text = get_product_text(product)

    if washing_type == "top load":
        return ("top load" in name or "topload" in name
                or "top load" in text)
    if washing_type == "front load":
        return ("front load" in name or "frontload" in name
                or "front load" in text)
    if washing_type == "twin tub":
        return "twin tub" in name or "twin tub" in text

    return True


# ============================================================
# REAL PRODUCT CHECK
# ============================================================

def is_real_product(product):
    name = get_product_name(product)

    excluded_phrases = [
        "price in pakistan", "prices in pakistan", "buying guide",
        "buying guides", "review", "reviews", "comparison",
        "category", "categories", "best washing machine",
        "best refrigerator", "best freezer", "best air conditioner",
    ]

    for phrase in excluded_phrases:
        if phrase in name:
            return False

    return True


# ============================================================
# PRODUCT SCORING
# ============================================================

def calculate_product_score(product, query):
    q = normalize_text(query)
    info = extract_query_info(query)
    name = get_product_name(product)

    score = 0

    if info["model"] and model_matches(product, info["model"]):
        score += 1000

    if info["brand"] and brand_matches(product, info["brand"]):
        score += 300

    if info["product_type"] and product_type_matches(product, info["product_type"]):
        score += 250

    if info["kg"] is not None and kg_matches(product, info["kg"]):
        score += 100

    if info["ton"] is not None and ton_matches(product, info["ton"]):
        score += 100

    if info["door"] and door_matches(product, info["door"]):
        score += 80

    if info["washing_type"] and washing_type_matches(product, info["washing_type"]):
        score += 80

    query_words = set(q.split())
    for word in query_words:
        if len(word) > 2 and word in name:
            score += 5

    return score


# ============================================================
# EXACT PRODUCT
# ============================================================

def find_best_product(query):
    info = extract_query_info(query)

    if not info["model"]:
        return None

    candidates = []

    for product in get_products():
        if not is_real_product(product):
            continue
        if not model_matches(product, info["model"]):
            continue

        score = 0

        if info["brand"] and brand_matches(product, info["brand"]):
            score += 500
        if info["product_type"] and product_type_matches(product, info["product_type"]):
            score += 300

        score += calculate_product_score(product, query)

        candidates.append((score, product))

    if not candidates:
        return None

    candidates.sort(key=lambda x: x[0], reverse=True)
    return candidates[0][1]


# ============================================================
# LIST PRODUCTS
# ============================================================

def find_list_products(query, limit=8):

    info = extract_query_info(query)

    def matches(product, use_kg, use_ton, use_door, use_washing_type):

        if info["brand"] and not brand_matches(product, info["brand"]):
            return False
        if info["product_type"] and not product_type_matches(product, info["product_type"]):
            return False
        if use_kg and info["kg"] is not None and not kg_matches(product, info["kg"]):
            return False
        if use_ton and info["ton"] is not None and not ton_matches(product, info["ton"]):
            return False
        if use_door and info["door"] and not door_matches(product, info["door"]):
            return False
        if use_washing_type and info["washing_type"] and not washing_type_matches(product, info["washing_type"]):
            return False

        return True

    filter_stages = [
        dict(use_kg=True, use_ton=True, use_door=True, use_washing_type=True),
        dict(use_kg=False, use_ton=False, use_door=True, use_washing_type=True),
        dict(use_kg=False, use_ton=False, use_door=False, use_washing_type=True),
        dict(use_kg=False, use_ton=False, use_door=False, use_washing_type=False),
    ]

    for stage in filter_stages:

        candidates = []

        for product in get_products():

            if not is_real_product(product):
                continue

            if not matches(product, **stage):
                continue

            score = calculate_product_score(product, query)
            candidates.append((score, product))

        if candidates:

            candidates.sort(key=lambda x: x[0], reverse=True)

            final_products = []
            seen_names = set()

            for score, product in candidates:
                name = get_product_name(product)
                if name in seen_names:
                    continue
                seen_names.add(name)
                final_products.append(product)
                if len(final_products) >= limit:
                    break

            return final_products

    return []


# ============================================================
# NORMAL PRODUCT SEARCH
# ============================================================

def find_products(query, limit=8):

    MIN_SCORE_THRESHOLD = 10

    scored_products = []

    for product in get_products():
        if not is_real_product(product):
            continue

        score = calculate_product_score(product, query)

        if score >= MIN_SCORE_THRESHOLD:
            scored_products.append((score, product))

    scored_products.sort(key=lambda x: x[0], reverse=True)

    return [product for score, product in scored_products[:limit]]


# ============================================================
# QUERY TYPE
# ============================================================

def is_comparison_query(query):
    q = normalize_text(query)
    comparison_words = ["compare", "comparison", "difference", "vs", "versus", "which is better"]
    return any(word in q for word in comparison_words)


def is_list_query(query):
    q = normalize_text(query)
    list_phrases = ["show me", "show all", "list", "which", "what are",
                     "all available", "available", "all products", "give me"]
    return any(phrase in q for phrase in list_phrases)


# ============================================================
# COMPARISON MATCHING (shared by retrieve() and generator.py)
# ============================================================

def find_comparison_products(query):
    """
    Given a comparison query, extract candidate model tokens and find
    the real products that match each one. Returns (results,
    unmatched_labels) — unmatched_labels lists the raw tokens from the
    query that did NOT match any real product, so callers can tell the
    user "X wasn't found" deterministically instead of relying on the
    LLM to notice and mention this reliably (small local models often
    ignore that instruction and invent data for the missing product
    anyway).
    """

    q_raw = query.lower()
    model_candidates = re.findall(
        f"{MODEL_PATTERN_LETTERS_FIRST}|{MODEL_PATTERN_DIGITS_FIRST}",
        q_raw
    )

    results = []
    seen = set()
    unmatched = []

    MIN_MODEL_CANDIDATE_LENGTH = 4

    for model_candidate in model_candidates:

        # Very short fragments (e.g. "t3", a common compressor-type
        # code) are almost never real distinguishing model numbers —
        # they're usually leftover pieces of a longer hyphenated model
        # that got split, and matching on them pulls in unrelated
        # products that happen to share the same generic spec code.
        if len(model_candidate.replace("-", "")) < MIN_MODEL_CANDIDATE_LENGTH:
            continue

        normalized = normalize_model(model_candidate)
        found_for_this_candidate = False

        for product in get_products():
            if not is_real_product(product):
                continue
            if model_matches(product, normalized):
                name = get_product_name(product)
                if name not in seen:
                    results.append(product)
                    seen.add(name)
                found_for_this_candidate = True

        if not found_for_this_candidate:
            unmatched.append(model_candidate)

    return results, unmatched


# ============================================================
# MAIN RETRIEVER
# ============================================================

def retrieve(query, k=8):
    query = query.strip()

    if not query:
        return []

    info = extract_query_info(query)

    # EXACT MODEL SEARCH
    if info["model"] and not is_comparison_query(query):
        exact_product = find_best_product(query)
        if exact_product:
            return [exact_product]

    # COMPARISON SEARCH
    if is_comparison_query(query):
        results, _unmatched = find_comparison_products(query)
        if results:
            return results[:k]

    # STRICT LIST SEARCH
    if is_list_query(query):
        results = find_list_products(query, limit=k)
        if results:
            return results

    # NORMAL SEARCH
    results = find_products(query, limit=k)

    # FAISS FALLBACK
    if not results:
        docs = get_vector_store().similarity_search(query, k=k)

        seen_indices = set()

        for doc in docs:
            product_index = doc.metadata.get("product_index")

            if product_index is None:
                continue
            if product_index in seen_indices:
                continue

            products = get_products()

            if 0 <= product_index < len(products):
                product = products[product_index]

                if is_real_product(product):
                    results.append(product)
                    seen_indices.add(product_index)

    return results[:k]


if __name__ == "__main__":

    print("=" * 70)
    print("RAG RETRIEVER TEST")
    print("=" * 70)

    while True:
        query = input("\nEnter query (or 'exit'): ").strip()
        if query.lower() == "exit":
            break

        results = retrieve(query, k=8)

        print("\nResults:")
        print("-" * 70)

        if not results:
            print("No matching products found.")
            continue

        for i, product in enumerate(results, start=1):
            name = product.get("name", "Unknown Product")
            price = product.get("price")
            if price:
                print(f"{i}. {name} - Rs. {price}")
            else:
                print(f"{i}. {name}")
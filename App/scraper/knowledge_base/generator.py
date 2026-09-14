from langchain_ollama import OllamaLLM
from App.scraper.knowledge_base.retriever import retrieve, is_comparison_query, is_list_query, find_best_product, find_comparison_products
import re


# ============================================================
# LOAD LLM (lazy)
# ============================================================

_llm = None


def get_llm():

    global _llm

    if _llm is None:

        print("Loading Ollama LLM...")

        _llm = OllamaLLM(
            model="tinyllama"
        )

    return _llm


# ============================================================
# QUESTION DETECTION
# ============================================================

# Each structured question type maps to the keywords that identify it.
# Adding a new question type (e.g. "dimensions") only needs one new
# entry here, instead of a whole new is_X_question function.
QUESTION_TYPE_KEYWORDS = {
    "price": ["price", "cost", "how much", "rate", "kitne ka", "kitny ka", "qeemat", "keemat"],
    "compressor": ["compressor", "which compressor", "what compressor"],
    "capacity": ["capacity", "ton", "how many ton", "kitne ton", "kitny ton"],
    "refrigerant": ["refrigerant", "gas", "which gas", "what gas"],
    "warranty": ["warranty", "guarantee", "guarantee period"],
    "feature": ["features", "feature", "which features", "what features",
                "what does it have", "khubiyan", "khasiyat"],
}


def is_question_type(question, question_type):
    keywords = QUESTION_TYPE_KEYWORDS[question_type]
    question = question.lower()
    return any(word in question for word in keywords)


def is_price_question(question):
    return is_question_type(question, "price")


def is_compressor_question(question):
    return is_question_type(question, "compressor")


def is_capacity_question(question):
    return is_question_type(question, "capacity")


def is_refrigerant_question(question):
    return is_question_type(question, "refrigerant")


def is_warranty_question(question):
    return is_question_type(question, "warranty")


def is_feature_question(question):
    return is_question_type(question, "feature")


# ============================================================
# BUILD CONTEXT FROM PRODUCT
# ============================================================

def build_context(product):

    specifications = product.get("specifications") or {}

    spec_lines = "\n".join(
        f"- {key}: {value}"
        for key, value in specifications.items()
    )

    return f"""Product Name: {product.get("name", "")}

Current Price: Rs. {product.get("price", "")}

Lowest Recorded Price: Rs. {product.get("price_low", "")}

Highest Recorded Price: Rs. {product.get("price_high", "")}

Description:
{product.get("description", "")}

Specifications:
{spec_lines}

Product URL:
{product.get("url", "")}"""


# ============================================================
# BUILD CONTEXT FOR MULTIPLE PRODUCTS (comparisons)
# ============================================================

def build_spec_sheet_answer(product):
    """
    A deterministic, non-LLM summary of a single confidently-identified
    product — used whenever we have exact structured data, so there's
    no need to risk an LLM paraphrase introducing typos or factual
    errors (e.g. "Compressor" -> "Compounder", wrong capacity, etc).
    """

    name = product.get("name", "Unknown Product")
    price = product.get("price")
    description = product.get("description")

    lines = [name, ""]

    if price:
        lines.append(f"Price: Rs. {price}")

    if description:
        # Split on a period only when it's followed by a space/end
        # (a real sentence boundary) — not on a decimal point like
        # "1.5", which would otherwise cut the sentence short.
        match = re.match(r"(.+?\.)(?:\s|$)", description.strip())
        first_sentence = match.group(1).strip() if match else description.strip()
        if first_sentence:
            lines.append(first_sentence)

    specifications = product.get("specifications") or {}

    if specifications:
        lines.append("")
        lines.append("Specifications:")
        for key, value in specifications.items():
            lines.append(f"- {key}: {value}")

    url = product.get("url")
    if url:
        lines.append("")
        lines.append(f"More info: {url}")

    return "\n".join(lines).strip()


# ============================================================
# EXTRACT A SPEC VALUE FROM THE STRUCTURED "- Key: Value" LINES
# ============================================================

def extract_spec_value(context, keyword):
    """
    Looks for a spec line we ourselves wrote in build_context()
    (e.g. "- Refrigerant Type: R32") and returns just the value.
    This is far more reliable than searching the whole context
    (including marketing description text) with loose patterns,
    which can accidentally grab the wrong word (e.g. capturing
    "Type" out of "Refrigerant Type: R32").
    """

    pattern = rf"(?im)^- [^:\n]*{re.escape(keyword)}[^:\n]*:\s*(.+)$"

    match = re.search(pattern, context)

    if match:
        return match.group(1).strip()

    return None


# ============================================================
# EXTRACT PRODUCT NAME
# ============================================================

def extract_product_name(context):
    match = re.search(r"Product Name:\s*(.+?)(?:\s+Current Price:|$)", context, re.IGNORECASE)
    if match:
        return match.group(1).strip()
    return "This product"


# ============================================================
# EXTRACT PRICE
# ============================================================

def extract_price(context):
    patterns = [
        r"Current Price:\s*Rs\.?\s*([\d,]+)",
        r"current price is\s*Rs\.?\s*([\d,]+)",
        r"Price:\s*Rs\.?\s*([\d,]+)",
        r"Price:\s*([\d,]+)",
    ]
    for pattern in patterns:
        match = re.search(pattern, context, re.IGNORECASE)
        if match:
            price = match.group(1).replace(",", "")
            return f"Rs. {int(price):,}"
    return None


# ============================================================
# EXTRACT CAPACITY
# ============================================================

def extract_capacity(context):

    value = extract_spec_value(context, "Capacity")

    if value:
        return value

    match = re.search(r"\b([\d.]+)\s*Ton\b", context, re.IGNORECASE)

    if match:
        return f"{match.group(1)} Ton"

    return None


# ============================================================
# EXTRACT COMPRESSOR
# ============================================================

def extract_compressor(context):

    value = extract_spec_value(context, "Compressor")

    if value:
        return value

    match = re.search(
        r"((?:T3|T1|T2)\s+Tropical\s+Inverter\s+Compressor)",
        context,
        re.IGNORECASE
    )

    if match:
        return match.group(1).strip()

    return None


# ============================================================
# EXTRACT REFRIGERANT
# ============================================================

def extract_refrigerant(context):

    value = extract_spec_value(context, "Refrigerant")

    if value and value.lower() not in ["eco-friendly", "environment", "friendly"]:
        return value.upper()

    match = re.search(
        r"\b(R32|R410A|R22|R290|R600a|R134a|R404A)\b",
        context,
        re.IGNORECASE
    )

    if match:
        return match.group(1).upper()

    return None


# ============================================================
# EXTRACT WARRANTY
# ============================================================

def extract_warranty(context):

    value = extract_spec_value(context, "Warranty")

    if value:
        return value

    match = re.search(
        r"(\d+\s+Years?\s+Compressor\s*,\s*\d+\s+Year[s]?\s+General)",
        context,
        re.IGNORECASE
    )

    if match:
        return match.group(1).strip()

    return None


# ============================================================
# EXTRACT FEATURES
# ============================================================

def extract_features(context):
    features = []

    if re.search(r"T3\s+Tropical\s+Inverter\s+Compressor", context, re.IGNORECASE):
        features.append("T3 Tropical Inverter Compressor")
    elif re.search(r"T3\s+Inverter", context, re.IGNORECASE):
        features.append("T3 Inverter")

    if re.search(r"Cold Plasma", context, re.IGNORECASE):
        features.append("Cold Plasma Air Purification")

    if re.search(r"Wi-Fi|WiFi", context, re.IGNORECASE):
        features.append("Wi-Fi Smart Control")

    if re.search(r"I-Feel", context, re.IGNORECASE):
        features.append("I-Feel Intelligent Temperature Control")

    if re.search(r"Self-Clean|Self Clean", context, re.IGNORECASE):
        features.append("Self-Clean Function")

    if re.search(r"G10 Inverter", context, re.IGNORECASE):
        features.append("G10 Inverter Technology")

    if re.search(r"4-Way Air Swing", context, re.IGNORECASE):
        features.append("4-Way Air Swing")

    if re.search(r"Heat and Cool", context, re.IGNORECASE):
        features.append("Heat and Cool")

    if re.search(r"Low Voltage", context, re.IGNORECASE):
        features.append("Low Voltage Operation")

    return features


# ============================================================
# CLEAN LLM ANSWER
# ============================================================

def clean_answer(answer):
    answer = answer.strip()
    answer = re.sub(r"^FINAL ANSWER\s*:?\s*", "", answer, flags=re.IGNORECASE)
    answer = re.sub(r"^ANSWER\s*:?\s*", "", answer, flags=re.IGNORECASE)
    answer = re.sub(r"According to the context,?\s*", "", answer, flags=re.IGNORECASE)
    answer = re.sub(r"According to the given context,?\s*", "", answer, flags=re.IGNORECASE)

    match = re.search(r"\n\s*Question\s*:", answer, flags=re.IGNORECASE)
    if match:
        answer = answer[:match.start()]

    return answer.strip()


# ============================================================
# GENERATE ANSWER
# ============================================================

def generate_answer(question):

    # List queries ("show me all X") need many more candidates than
    # the default k=3.
    k = 10 if is_list_query(question) else 3

    results = retrieve(question, k=k)

    if not results:
        return "I could not find this information in the knowledge base."

    # -----------------------------------------------------
    # Comparison questions need EVERY retrieved product's
    # context, not just the first one, or the LLM will
    # invent specs for products it was never shown.
    # -----------------------------------------------------

    if is_comparison_query(question) and len(results) > 1:

        _comparison_results, unmatched_terms = find_comparison_products(question)

        answer = "Here's a comparison of the products found:\n"

        for i, product in enumerate(results, start=1):

            name = product.get("name", "Unknown Product")
            price = product.get("price")

            answer += f"\n{i}. {name}\n"

            if price:
                answer += f"   Price: Rs. {price}\n"
            else:
                answer += "   Price: Not available\n"

            specifications = product.get("specifications") or {}

            for key, value in specifications.items():
                answer += f"   - {key}: {value}\n"

        answer = answer.strip()

        # Deterministic note about anything mentioned in the question
        # that wasn't found — never left to an LLM's discretion.
        if unmatched_terms:
            note = (
                "\n\nNote: I could not find a product matching "
                f"\"{', '.join(unmatched_terms)}\" in the knowledge base "
                "— the comparison above only covers the products found."
            )
            answer += note

        return answer

    # -----------------------------------------------------
    # STRONG list-intent phrases are checked here, BEFORE any
    # structured single-value detector. Phrases like "show me" /
    # "show all" / "give me" are unambiguous browse-intent — even
    # if the question also happens to contain a word like "ton"
    # or "price" that a structured detector would otherwise match
    # first (e.g. "show me 1.5 ton Gree air conditioners" was being
    # misrouted into the capacity extractor because of the word
    # "ton"). A weaker/broader list-check still runs later (after
    # the structured detectors) as a catch-all for phrasing like
    # "which products are available" that isn't caught here.
    # -----------------------------------------------------

    STRONG_LIST_PHRASES = [
        "show me", "show all", "list all", "give me", "all available"
    ]

    if any(phrase in question.lower() for phrase in STRONG_LIST_PHRASES):

        answer = "Here are the matching products:\n\n"

        for i, product in enumerate(results, start=1):

            name = product.get("name", "Unknown Product")
            price = product.get("price")

            answer += f"{i}. {name}"

            if price:
                answer += f" - Rs. {price}"

            answer += "\n"

        return answer.strip()

    # -----------------------------------------------------
    # For structured single-fact questions (price/compressor/
    # capacity/refrigerant/warranty/features), we require the
    # query to name a SPECIFIC, exactly-identified product via
    # find_best_product(). A loose brand-only match from the
    # general retrieve() fallback (e.g. matching "Samsung" in
    # "Samsung Galaxy S24" to some unrelated Samsung washing
    # machine) is not confident enough to state a specific fact
    # as if it definitely answers the question.
    # -----------------------------------------------------

    structured_question = (
        is_price_question(question)
        or is_compressor_question(question)
        or is_capacity_question(question)
        or is_refrigerant_question(question)
        or is_warranty_question(question)
        or is_feature_question(question)
    )

    # A confidently-identified exact product (found via find_best_product,
    # e.g. the user typed a model number directly) means we already have
    # reliable structured data — there's no need to risk the LLM
    # paraphrasing it inaccurately (it has repeatedly mis-typed terms
    # like "Compressor" -> "Compounder", "Inverter" -> "Invierte", and
    # even stated the wrong capacity). We only fall back to the LLM when
    # no exact product was identified, since that's a genuinely fuzzy/
    # semantic query where synthesis actually adds value.
    confident_product = find_best_product(question)

    if structured_question:

        if confident_product is None:
            return "I could not find this specific product in the knowledge base."

        context = build_context(confident_product)

    elif confident_product is not None:

        return build_spec_sheet_answer(confident_product)

    else:
        context = build_context(results[0])

    product_name = extract_product_name(context)

    if is_price_question(question):
        price = extract_price(context)
        if price:
            return f"The current price of {product_name} is {price}."
        return "I could not find the current price of this product in the knowledge base."

    if is_compressor_question(question):
        compressor = extract_compressor(context)
        if compressor:
            return f"The {product_name} uses a {compressor}."
        return "I could not find the compressor information in the knowledge base."

    if is_capacity_question(question):
        capacity = extract_capacity(context)
        if capacity:
            return f"The capacity of {product_name} is {capacity}."
        return "I could not find the capacity information in the knowledge base."

    if is_refrigerant_question(question):
        refrigerant = extract_refrigerant(context)
        if refrigerant:
            return f"The refrigerant used in {product_name} is {refrigerant}."
        return "I could not find the refrigerant information in the knowledge base."

    if is_warranty_question(question):
        warranty = extract_warranty(context)
        if warranty:
            return f"The warranty for {product_name} is {warranty}."
        return "I could not find the warranty information in the knowledge base."

    if is_feature_question(question):
        features = extract_features(context)
        if features:
            answer = f"{product_name} has the following features:\n\n"
            for feature in features:
                answer += f"- {feature}\n"
            return answer.strip()
        return "I could not find the feature information in the knowledge base."

    # -----------------------------------------------------
    # List queries — checked AFTER every specific structured
    # detector above, since is_list_query() uses broad keywords
    # like "which"/"available" that would otherwise false-positive
    # on structured questions such as "which compressor...".
    # Only genuine catch-all list requests reach here.
    # -----------------------------------------------------

    if is_list_query(question):

        answer = "Here are the matching products:\n\n"

        for i, product in enumerate(results, start=1):

            name = product.get("name", "Unknown Product")
            price = product.get("price")

            answer += f"{i}. {name}"

            if price:
                answer += f" - Rs. {price}"

            answer += "\n"

        return answer.strip()

    prompt = f"""
You are a product assistant.

Use ONLY the information in the CONTEXT to answer the QUESTION.

CONTEXT:
{context}

QUESTION:
{question}

ANSWER:
"""

    answer = get_llm().invoke(prompt)

    return clean_answer(answer)


if __name__ == "__main__":

    while True:
        question = input("\nAsk a question: ").strip()

        if question.lower() in ["exit", "quit"]:
            print("\nExiting...")
            break

        if not question:
            print("Please enter a question.")
            continue

        answer = generate_answer(question)

        print("\nFINAL ANSWER")
        print("-------------------------")
        print(answer)
"""
Test suite for retriever.py

Run with:  pytest tests/test_retriever.py -v

These tests inject fake product data directly (via monkeypatch on the
module's internal _products cache) so they never touch the real
data/products.json or data/faiss_index — safe to run anytime, no
crawling/embedding needed.
"""

import sys
import os

sys.path.insert(
    0,
    os.path.join(os.path.dirname(__file__), "..")
)

import pytest

from App.scraper.knowledge_base import retriever


# ============================================================
# SAMPLE PRODUCT DATA
# ============================================================

SAMPLE_PRODUCTS = [
    {
        "name": "Haier HSU-18HFPAB 1.5 Ton Inverter Air Conditioner",
        "price": "175000",
        "description": "Energy efficient inverter AC.",
        "specifications": {"Refrigerant": "R32"},
        "url": "https://example.com/haier-hsu-18hfpab",
    },
    {
        "name": "Dawlance DWF-9188 8 Kg Front Load Washing Machine",
        "price": "89000",
        "description": "Automatic front load washer.",
        "specifications": {},
        "url": "https://example.com/dawlance-dwf-9188",
    },
    {
        "name": "Samsung RT38 Double Door Refrigerator",
        "price": "150000",
        "description": "Frost free double door fridge.",
        "specifications": {},
        "url": "https://example.com/samsung-rt38",
    },
    {
        "name": "Best Air Conditioner Buying Guide",
        "price": None,
        "description": "A guide article, not a real product.",
        "specifications": {},
        "url": "https://example.com/buying-guide",
    },
]


def setup_function(_):
    """Inject fake product data before every test."""
    retriever._products = list(SAMPLE_PRODUCTS)


# ============================================================
# extract_query_info
# ============================================================

def test_extract_brand():
    info = retriever.extract_query_info("haier air conditioner")
    assert info["brand"] == "haier"


def test_extract_model():
    info = retriever.extract_query_info("HSU-18HFPAB price")
    assert info["model"] == "hsu18hfpab"


def test_extract_kg():
    info = retriever.extract_query_info("8 kg washing machine")
    assert info["kg"] == 8.0


def test_extract_product_type_ac():
    info = retriever.extract_query_info("show me air conditioners")
    assert info["product_type"] == "air conditioner"


def test_extract_product_type_fridge():
    info = retriever.extract_query_info("best fridge under 150000")
    assert info["product_type"] == "refrigerator"


def test_extract_door():
    info = retriever.extract_query_info("double door refrigerator")
    assert info["door"] == "double door"


def test_extract_washing_type():
    info = retriever.extract_query_info("front load washing machine")
    assert info["washing_type"] == "front load"


def test_extract_no_match_on_generic_query():
    info = retriever.extract_query_info("hello there")
    assert info["brand"] is None
    assert info["product_type"] is None


# ============================================================
# is_real_product
# ============================================================

def test_is_real_product_true():
    assert retriever.is_real_product(SAMPLE_PRODUCTS[0]) is True


def test_is_real_product_excludes_buying_guide():
    assert retriever.is_real_product(SAMPLE_PRODUCTS[3]) is False


# ============================================================
# Individual matchers
# ============================================================

def test_brand_matches():
    assert retriever.brand_matches(SAMPLE_PRODUCTS[0], "haier") is True
    assert retriever.brand_matches(SAMPLE_PRODUCTS[0], "samsung") is False


def test_model_matches():
    assert retriever.model_matches(SAMPLE_PRODUCTS[0], "hsu18hfpab") is True
    assert retriever.model_matches(SAMPLE_PRODUCTS[0], "rt38") is False


def test_product_type_matches():
    assert retriever.product_type_matches(SAMPLE_PRODUCTS[1], "washing machine") is True
    assert retriever.product_type_matches(SAMPLE_PRODUCTS[1], "refrigerator") is False


def test_kg_matches():
    assert retriever.kg_matches(SAMPLE_PRODUCTS[1], 8.0) is True
    assert retriever.kg_matches(SAMPLE_PRODUCTS[1], 10.0) is False


def test_door_matches():
    assert retriever.door_matches(SAMPLE_PRODUCTS[2], "double door") is True
    assert retriever.door_matches(SAMPLE_PRODUCTS[2], "single door") is False


# ============================================================
# calculate_product_score
# ============================================================

def test_score_prioritizes_model_match():
    query = "HSU-18HFPAB"
    ac_score = retriever.calculate_product_score(SAMPLE_PRODUCTS[0], query)
    fridge_score = retriever.calculate_product_score(SAMPLE_PRODUCTS[2], query)
    assert ac_score > fridge_score


# ============================================================
# find_best_product / find_list_products / find_products
# ============================================================

def test_find_best_product_exact_model():
    product = retriever.find_best_product("HSU-18HFPAB")
    assert product is not None
    assert "Haier" in product["name"]


def test_find_best_product_no_model_returns_none():
    assert retriever.find_best_product("just some random text") is None


def test_find_list_products_filters_by_type():
    results = retriever.find_list_products("show me all refrigerators")
    names = [p["name"] for p in results]
    assert any("Samsung RT38" in n for n in names)
    assert not any("Washing Machine" in n for n in names)


def test_find_list_products_excludes_non_products():
    results = retriever.find_list_products("show me all air conditioners")
    names = [p["name"] for p in results]
    assert not any("Buying Guide" in n for n in names)


def test_find_products_general_query():
    results = retriever.find_products("front load washing machine")
    assert len(results) >= 1
    assert "Dawlance" in results[0]["name"]


# ============================================================
# retrieve() — end to end
# ============================================================

def test_retrieve_empty_query_returns_empty_list():
    assert retriever.retrieve("") == []
    assert retriever.retrieve("   ") == []


def test_retrieve_exact_model_short_circuits():
    results = retriever.retrieve("HSU-18HFPAB")
    assert len(results) == 1
    assert "Haier" in results[0]["name"]


def test_retrieve_list_query():
    results = retriever.retrieve("show me all air conditioners")
    assert len(results) >= 1
    assert all(retriever.is_real_product(p) for p in results)


def test_retrieve_comparison_query_returns_multiple_models():
    results = retriever.retrieve("compare HSU-18HFPAB vs RT38")
    names = [r["name"] for r in results]
    assert any("Haier" in n for n in names)
    assert any("Samsung" in n for n in names)


def test_retrieve_comparison_query_handles_digit_first_models():
    """
    Regression guard: real catalogs often use model numbers that START
    with digits (e.g. "6500X", "8000ST", "65Q7Q") rather than letters
    (e.g. "HSU-18HFPAB"). The old model regex only matched letters-first
    patterns, so a query like "compare 6500X vs 8000ST" silently matched
    ZERO products and fell through to an unrelated FAISS/semantic result.
    """
    retriever._products = list(SAMPLE_PRODUCTS) + [
        {
            "name": "Signature 6500X Air Fryer",
            "price": "38000",
            "description": "6.5 liter air fryer.",
            "specifications": {},
            "url": "https://example.com/signature-6500x",
        },
        {
            "name": "Signature 8000ST Air Fryer",
            "price": "47000",
            "description": "8 liter air fryer with steam.",
            "specifications": {},
            "url": "https://example.com/signature-8000st",
        },
    ]

    results = retriever.retrieve("Compare Signature 6500X vs Signature 8000ST")
    names = [r["name"] for r in results]

    assert any("6500X" in n for n in names)
    assert any("8000ST" in n for n in names)
    # Must NOT silently return an unrelated product like a deep freezer
    assert not any("Freezer" in n or "Refrigerator" in n for n in names)


def test_retrieve_falls_back_to_faiss_when_no_keyword_match(monkeypatch):
    """
    A query with no brand/model/type keyword overlap should hit the
    FAISS fallback branch. We fake get_vector_store() so this test
    never touches a real FAISS index, and verify the product_index
    metadata (Fix #3) is used correctly, including de-duplication.
    """

    class FakeDoc:
        def __init__(self, product_index):
            self.metadata = {"product_index": product_index}

    class FakeVectorStore:
        def similarity_search(self, query, k):
            # Same product referenced twice (simulates a product split
            # across 2 chunks) — should be de-duplicated by seen_indices.
            return [FakeDoc(0), FakeDoc(0), FakeDoc(2)]

    monkeypatch.setattr(
        retriever, "get_vector_store", lambda: FakeVectorStore()
    )

    results = retriever.retrieve("energy saving cooling appliance xyz")

    assert len(results) == 2
    returned_names = {r["name"] for r in results}
    assert SAMPLE_PRODUCTS[0]["name"] in returned_names
    assert SAMPLE_PRODUCTS[2]["name"] in returned_names


def test_retrieve_faiss_fallback_skips_out_of_range_index(monkeypatch):

    class FakeDoc:
        def __init__(self, product_index):
            self.metadata = {"product_index": product_index}

    class FakeVectorStore:
        def similarity_search(self, query, k):
            return [FakeDoc(999)]  # out of range on purpose

    monkeypatch.setattr(
        retriever, "get_vector_store", lambda: FakeVectorStore()
    )

    results = retriever.retrieve("some totally unrelated gibberish query")
    assert results == []


def test_model_matches_rejects_short_token_substring_collision():
    """
    Regression guard: found via live testing — "s24" (from a query like
    "Samsung Galaxy S24") used to match inside "ES-24NV01WT3" because
    model_matches() used plain substring containment. Now it must use
    exact token matching, which requires "s24" to be a whole token.
    """
    product = {"name": "EcoStar ES-24NV01WT3 2 Ton Inverter AC"}
    assert retriever.model_matches(product, "s24") is False


def test_model_matches_still_works_for_hyphenated_models():
    product = {"name": "Kenwood KLU-18B03S Luxury Ultra AC"}
    assert retriever.model_matches(product, "klu18b03s") is True


def test_find_products_rejects_weak_single_word_matches():
    """
    Regression guard: found via live testing — "Tesla Model 3" (a
    non-existent product) used to match a deep freezer purely because
    its name happened to contain the word "Model", and the freezer's
    price was confidently returned as if it answered the question.
    A single coincidental word match must no longer qualify.
    """
    setup_function(None)
    retriever._products = retriever._products + [
        {
            "name": "Haier Deep Freezer HDF-535 (New Twin Model)",
            "price": "114000",
            "description": "",
            "specifications": {},
            "url": "https://example.com/hdf-535",
        }
    ]
    results = retriever.find_products("what is the price of Tesla Model 3?")
    assert results == []


def test_find_list_products_kg_filter_is_strictly_enforced():
    """
    Regression guard: found via live testing — "show me 8 kg front load
    washing machines" was returning washing machines of every capacity
    (15kg, 24kg, etc.), not just 8kg ones, because the strict filter
    combination silently fell through to an unfiltered fallback.
    """
    retriever._products = [
        {
            "name": "LG FOZ6DRPK4 Front Load Automatic Washing Machine 15 KG",
            "price": "379000",
            "description": "",
            "specifications": {},
            "url": "https://example.com/lg-15kg",
        },
        {
            "name": "Samsung WW80J5413IW Front Load Automatic Washing Machine 8 Kg",
            "price": "188000",
            "description": "",
            "specifications": {},
            "url": "https://example.com/samsung-8kg",
        },
    ]
    results = retriever.find_list_products("show me 8 kg front load washing machines")
    names = [r["name"] for r in results]
    assert any("Samsung" in n for n in names)
    assert not any("15 KG" in n for n in names)


def test_find_list_products_relaxes_kg_filter_when_no_exact_match():
    """
    If NO product matches the requested capacity exactly, the search
    should relax the kg filter (rather than returning nothing at all)
    while still respecting brand/type/washing_type.
    """
    retriever._products = [
        {
            "name": "LG FOZ6DRPK4 Front Load Automatic Washing Machine 15 KG",
            "price": "379000",
            "description": "",
            "specifications": {},
            "url": "https://example.com/lg-15kg",
        },
    ]
    # No 8kg product exists at all — should still return the 15kg one
    # rather than an empty list, since kg is the least fundamental filter.
    results = retriever.find_list_products("show me 8 kg front load washing machines")
    assert len(results) == 1
    assert "LG" in results[0]["name"]


def test_model_matches_handles_product_with_none_name():
    """
    Regression guard: found via live testing — a scraped product with
    name=None (e.g. parser.py failed to find an h1 tag for that page)
    used to crash get_product_model_tokens() with
    AttributeError: 'NoneType' object has no attribute 'lower'.
    """
    broken_product = {"name": None, "price": None}
    assert retriever.model_matches(broken_product, "klu18b03s") is False


def test_retrieve_skips_products_with_none_name_without_crashing():
    retriever._products = [
        {"name": None, "price": None, "description": "", "specifications": {}, "url": None},
        {
            "name": "Kenwood KLU-18B03S Luxury Ultra AC",
            "price": "169000",
            "description": "",
            "specifications": {},
            "url": "https://example.com/klu",
        },
    ]
    results = retriever.retrieve("what is the price of Kenwood KLU-18B03S?")
    assert len(results) == 1
    assert results[0]["name"] == "Kenwood KLU-18B03S Luxury Ultra AC"


def test_normalize_text_preserves_decimal_points():
    """
    Regression guard: found via live testing — normalize_text() was
    turning "1.5" into "1 5" (destroying the decimal point along with
    other punctuation), which silently broke "1.5 Ton" and "17.5 Kg"
    style capacity extraction/matching everywhere.
    """
    assert retriever.normalize_text("1.5 Ton") == "1.5 ton"
    assert retriever.normalize_text("Gree 1.5 Ton AC") == "gree 1.5 ton ac"


def test_extract_ton_handles_decimal_values():
    info = retriever.extract_query_info("show me 1.5 ton Gree air conditioners")
    assert info["ton"] == 1.5


def test_find_list_products_ton_filter_is_strictly_enforced():
    """
    Regression guard: found via live testing — "show me 1.5 ton Gree
    air conditioners" returned ACs of every tonnage (1, 1.5, 2, 2.5...)
    because there was no ton-based filtering at all.
    """
    retriever._products = [
        {
            "name": "Gree 12AITH24S-T3 Airy Pro Inverter AC 1 Ton",
            "price": "186000",
            "description": "Split Air Conditioner with Heat and Cool",
            "specifications": {},
            "url": "",
        },
        {
            "name": "Gree 18AITH24S-T3 Airy Pro Inverter AC 1.5 Ton",
            "price": "244000",
            "description": "Split Air Conditioner with Heat and Cool",
            "specifications": {},
            "url": "",
        },
    ]
    results = retriever.find_list_products("show me 1.5 ton Gree air conditioners")
    names = [r["name"] for r in results]
    assert any("18AITH24S-T3" in n for n in names)
    assert not any("12AITH24S-T3" in n for n in names)


def test_product_type_matches_recognizes_ac_abbreviation():
    """
    Regression guard: real product names commonly abbreviate "Air
    Conditioner" as "AC" (e.g. "Gree 18AITH24S-T3 Airy Pro Inverter AC
    1.5 Ton"), which the old exact-phrase check missed entirely.
    """
    product = {"name": "Gree 18AITH24S-T3 Airy Pro Inverter AC 1.5 Ton"}
    assert retriever.product_type_matches(product, "air conditioner") is True


def test_kg_matches_ignores_dryer_capacity_mentioned_in_description():
    """
    Regression guard: found via live testing — a washer-dryer combo
    product (wash capacity 15 Kg, dryer capacity 8 Kg) had its long
    marketing description mention "8 Kg" many times (referring to the
    DRYER, e.g. "built-in 8 Kg heat-pump dryer"). kg_matches() used to
    scan the full free-text description, so a query for "8 kg washing
    machines" falsely matched this 15 Kg product. Capacity matching
    must now rely only on the product name and capacity-labeled
    specification fields, never the marketing description.
    """
    combo_product = {
        "name": "LG FOZ6DRPK4 Front Load Automatic Inverter Washing Machine – 15 KG",
        "description": (
            "built-in 8 Kg heat-pump dryer, Dry Capacity 8 Kg, "
            "8 Kg drying function, Washer Dryer (15 Kg Wash / 8 Kg Dry)"
        ),
        "specifications": {
            "Washing Machine Capacity": "15 kg",
            "Washing Machine Type": "Automatic, Front Load",
        },
    }
    assert retriever.kg_matches(combo_product, 8.0) is False
    assert retriever.kg_matches(combo_product, 15.0) is True


def test_find_list_products_excludes_washer_dryer_combo_by_dry_capacity():
    retriever._products = [
        {
            "name": "LG FOZ6DRPK4 Front Load Automatic Inverter Washing Machine – 15 KG",
            "price": "379000",
            "description": "built-in 8 Kg heat-pump dryer, Dry Capacity 8 Kg",
            "specifications": {
                "Washing Machine Capacity": "15 kg",
                "Washing Machine Type": "Automatic, Front Load",
            },
            "url": "",
        },
        {
            "name": "Samsung WW80J5413IW Front Load Automatic Washing Machine (8 Kg)",
            "price": "188000",
            "description": "Simple and reliable front load washing machine.",
            "specifications": {
                "Washing Machine Capacity": "8 kg",
                "Washing Machine Type": "Automatic, Front Load",
            },
            "url": "",
        },
    ]
    results = retriever.find_list_products("show me 8 kg front load washing machines")
    names = [r["name"] for r in results]
    assert any("Samsung" in n for n in names)
    assert not any("FOZ6DRPK4" in n for n in names)


def test_extract_product_type_handles_plural_acs():
    """
    Regression guard: "ACs" (plural abbreviation, e.g. "show me ACs
    under 100000") used to not match the singular-only \bac\b regex,
    causing product_type detection to fail entirely.
    """
    info = retriever.extract_query_info("show me ACs under 100000")
    assert info["product_type"] == "air conditioner"


def test_extract_product_type_tolerates_common_typos():
    """
    Regression guard: "show me all air conditoners" (missing an 'i')
    used to completely fail product_type detection, causing the query
    to fall through to irrelevant generic-word matching and return
    unrelated products (shavers, geysers, etc.).
    """
    info = retriever.extract_query_info("show me all air conditoners")
    assert info["product_type"] == "air conditioner"


def test_fuzzy_word_present_rejects_unrelated_words():
    """
    Sanity check: fuzzy matching shouldn't be so loose that it matches
    completely unrelated words.
    """
    assert retriever.fuzzy_word_present("show me some blenders", "conditioner") is False


def test_find_comparison_products_ignores_generic_short_fragments():
    """
    Regression guard: found via live testing — "12AITH24S-T3" (12 chars)
    exceeded the old {1,10} regex length cap, so it got split into
    "12aith24s-" and a leftover "t3" fragment. "T3" is an extremely
    common AC compressor-type code, so this leftover fragment matched
    an unrelated Dawlance product (also "T3"), pulling it into a
    comparison that never mentioned it.
    """
    products = [
        {"name": "Kenwood KLU-18B03S Luxury Ultra AC", "price": "169000", "specifications": {}},
        {"name": "Gree 12AITH24S-T3 Airy Pro Inverter AC", "price": "186000", "specifications": {}},
        {"name": "Dawlance Glacier Pro Inv 45 FS T3 Floor Stand AC", "price": "247000", "specifications": {}},
    ]
    retriever._products = products

    results, unmatched = retriever.find_comparison_products(
        "compare Kenwood KLU-18B03S vs Gree 12AITH24S-T3 vs Haier HSU-18HFPAB"
    )

    names = [r["name"] for r in results]
    assert any("Kenwood" in n for n in names)
    assert any("Gree" in n for n in names)
    assert not any("Dawlance" in n for n in names)
    assert "hsu-18hfpab" in unmatched
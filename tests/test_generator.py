"""
Test suite for generator.py

Run with:  pytest tests/test_generator.py -v

These tests never call the real Ollama LLM or the real retriever —
retrieve() and get_llm() are monkeypatched, so this file is fast and
safe to run without Ollama running or any data files present.
"""

import sys
import os

sys.path.insert(
    0,
    os.path.join(os.path.dirname(__file__), "..")
)

from App.scraper.knowledge_base import generator


# ============================================================
# SAMPLE PRODUCTS
# ============================================================

AC_PRODUCT = {
    "name": "Haier HSU-18HFPAB 1.5 Ton Inverter Air Conditioner",
    "price": "175000",
    "price_low": "160000",
    "price_high": "190000",
    "description": "Energy efficient inverter AC with fast cooling.",
    "specifications": {
        "Air Conditioner Capacity": "1.5 Ton",
        "Compressor": "T3 Tropical Inverter Compressor",
        "Refrigerant": "R32",
        "Warranty": "10 Years Compressor, 1 Year General",
        "Wi-Fi": "Yes",
    },
    "url": "https://example.com/haier-hsu-18hfpab",
}

SPARSE_PRODUCT = {
    "name": "Generic Blender X100",
    "price": None,
    "price_low": None,
    "price_high": None,
    "description": "",
    "specifications": {},
    "url": None,
}


# ============================================================
# build_context
# ============================================================

def test_build_context_includes_all_fields():
    context = generator.build_context(AC_PRODUCT)
    assert "Product Name: Haier HSU-18HFPAB" in context
    assert "Current Price: Rs. 175000" in context
    assert "- Compressor: T3 Tropical Inverter Compressor" in context
    assert "- Refrigerant: R32" in context


def test_build_context_handles_missing_fields_gracefully():
    # Must not raise, even with every optional field missing/None.
    context = generator.build_context(SPARSE_PRODUCT)
    assert "Product Name: Generic Blender X100" in context


# ============================================================
# Question-type detectors
# ============================================================

def test_is_price_question():
    assert generator.is_price_question("what is the price?") is True
    assert generator.is_price_question("kitne ka hai") is True
    assert generator.is_price_question("what is the warranty") is False


def test_is_compressor_question():
    assert generator.is_compressor_question("which compressor does it use") is True


def test_is_capacity_question():
    assert generator.is_capacity_question("how many ton is this AC") is True


def test_is_refrigerant_question():
    assert generator.is_refrigerant_question("which gas does it use") is True


def test_is_warranty_question():
    assert generator.is_warranty_question("what is the warranty period") is True


def test_is_feature_question():
    assert generator.is_feature_question("what features does it have") is True


# ============================================================
# extract_* functions (regex extraction from context)
# ============================================================

def test_extract_product_name():
    context = generator.build_context(AC_PRODUCT)
    assert generator.extract_product_name(context) == "Haier HSU-18HFPAB 1.5 Ton Inverter Air Conditioner"


def test_extract_price():
    context = generator.build_context(AC_PRODUCT)
    assert generator.extract_price(context) == "Rs. 175,000"


def test_extract_price_missing_returns_none():
    context = generator.build_context(SPARSE_PRODUCT)
    assert generator.extract_price(context) is None


def test_extract_capacity():
    context = generator.build_context(AC_PRODUCT)
    assert generator.extract_capacity(context) == "1.5 Ton"


def test_extract_compressor():
    context = generator.build_context(AC_PRODUCT)
    assert "T3 Tropical Inverter Compressor" in generator.extract_compressor(context)


def test_extract_refrigerant():
    context = generator.build_context(AC_PRODUCT)
    assert generator.extract_refrigerant(context) == "R32"


def test_extract_warranty():
    context = generator.build_context(AC_PRODUCT)
    assert "10 Years Compressor" in generator.extract_warranty(context)


def test_extract_features():
    context = generator.build_context(AC_PRODUCT)
    features = generator.extract_features(context)
    assert "T3 Tropical Inverter Compressor" in features
    assert "Wi-Fi Smart Control" in features


def test_extract_features_empty_for_sparse_product():
    context = generator.build_context(SPARSE_PRODUCT)
    assert generator.extract_features(context) == []


# ============================================================
# clean_answer
# ============================================================

def test_clean_answer_strips_prefixes():
    raw = "FINAL ANSWER: The price is Rs. 175,000."
    assert generator.clean_answer(raw) == "The price is Rs. 175,000."


def test_clean_answer_strips_context_reference():
    raw = "According to the context, the warranty is 10 years."
    assert generator.clean_answer(raw) == "the warranty is 10 years."


def test_clean_answer_cuts_generated_question():
    raw = "The price is Rs. 175,000.\nQuestion: what about compressor?"
    assert "Question" not in generator.clean_answer(raw)


# ============================================================
# generate_answer — end to end (retrieve() and LLM mocked)
# ============================================================

def test_generate_answer_price_question(monkeypatch):
    monkeypatch.setattr(generator, "retrieve", lambda q, k=3: [AC_PRODUCT])
    monkeypatch.setattr(generator, "find_best_product", lambda q: AC_PRODUCT)
    answer = generator.generate_answer("what is the price?")
    assert "175,000" in answer
    assert "Haier" in answer


def test_generate_answer_compressor_question(monkeypatch):
    monkeypatch.setattr(generator, "retrieve", lambda q, k=3: [AC_PRODUCT])
    monkeypatch.setattr(generator, "find_best_product", lambda q: AC_PRODUCT)
    answer = generator.generate_answer("which compressor does it use?")
    assert "T3 Tropical Inverter Compressor" in answer


def test_generate_answer_no_results(monkeypatch):
    monkeypatch.setattr(generator, "retrieve", lambda q, k=3: [])
    answer = generator.generate_answer("random unrelated question")
    assert answer == "I could not find this information in the knowledge base."


def test_generate_answer_sparse_product_price(monkeypatch):
    monkeypatch.setattr(generator, "retrieve", lambda q, k=3: [SPARSE_PRODUCT])
    monkeypatch.setattr(generator, "find_best_product", lambda q: SPARSE_PRODUCT)
    answer = generator.generate_answer("what is the price?")
    assert "could not find the current price" in answer


def test_generate_answer_general_question_uses_llm(monkeypatch):
    monkeypatch.setattr(generator, "retrieve", lambda q, k=3: [AC_PRODUCT])

    class FakeLLM:
        def invoke(self, prompt):
            assert "Haier" in prompt  # context was actually built and injected
            return "FINAL ANSWER: This AC is energy efficient."

    monkeypatch.setattr(generator, "get_llm", lambda: FakeLLM())

    answer = generator.generate_answer("tell me about this product")
    assert answer == "This AC is energy efficient."


def test_generate_answer_never_calls_llm_for_structured_questions(monkeypatch):
    """
    Regression guard: structured questions (price/compressor/etc.) must be
    answered from regex extraction alone and should never touch the LLM.
    """
    monkeypatch.setattr(generator, "retrieve", lambda q, k=3: [AC_PRODUCT])
    monkeypatch.setattr(generator, "find_best_product", lambda q: AC_PRODUCT)

    def fail_if_called():
        raise AssertionError("get_llm() should not be called for structured questions")

    monkeypatch.setattr(generator, "get_llm", fail_if_called)

    generator.generate_answer("what is the price?")
    generator.generate_answer("which compressor does it use?")
    generator.generate_answer("what is the warranty?")


def test_generate_answer_comparison_includes_all_products_deterministically(monkeypatch):
    """
    Regression guard: found via live testing — a comparison question used
    to only build context from results[0] (so the LLM never saw the
    second product's data), and later, even with both products' data
    given to the LLM, the small local model still hallucinated fake
    prices/specs from its own training data. Comparisons are now built
    deterministically from the retrieved product dicts — no LLM call at
    all — which eliminates hallucination risk entirely.
    """

    product_a = {
        "name": "Signature 6500X Steam Iron",
        "price": "64000",
        "price_low": "60000",
        "price_high": "70000",
        "description": "Steam iron with 6500W output.",
        "specifications": {"Water Tank": "650ml"},
        "url": "https://example.com/6500x",
    }

    product_b = {
        "name": "Signature 8000ST Steam Iron",
        "price": "78000",
        "price_low": "75000",
        "price_high": "85000",
        "description": "Steam iron with 8000W output.",
        "specifications": {"Water Tank": "800ml"},
        "url": "https://example.com/8000st",
    }

    monkeypatch.setattr(generator, "retrieve", lambda q, k=3: [product_a, product_b])
    monkeypatch.setattr(generator, "find_comparison_products", lambda q: ([product_a, product_b], []))

    def fail_if_called():
        raise AssertionError("get_llm() should never be called for comparisons anymore")
    monkeypatch.setattr(generator, "get_llm", fail_if_called)

    answer = generator.generate_answer("Compare Signature 6500X vs Signature 8000ST")

    assert "6500X" in answer
    assert "8000ST" in answer
    assert "Rs. 64000" in answer
    assert "Rs. 78000" in answer
    assert "Water Tank: 650ml" in answer
    assert "Water Tank: 800ml" in answer


def test_extract_refrigerant_handles_refrigerant_type_key():
    """
    Regression guard: found via live testing — the real site's spec
    table uses the key "Refrigerant Type" (not just "Refrigerant"),
    which caused the old regex to capture the word "Type" instead of
    the actual gas name (e.g. "R32").
    """
    product = {
        "name": "Kenwood KLU-18B03S",
        "specifications": {"Refrigerant Type": "R32"},
    }
    context = generator.build_context(product)
    assert generator.extract_refrigerant(context) == "R32"


def test_extract_compressor_handles_compressor_type_key():
    """
    Regression guard: same class of bug as refrigerant — real spec key
    is "Compressor Type", and the old loose sentence-based regex could
    grab marketing text instead of the actual spec value.
    """
    product = {
        "name": "Kenwood KLU-18B03S",
        "specifications": {"Compressor Type": "T3 Inverter Rotary Compressor"},
    }
    context = generator.build_context(product)
    assert generator.extract_compressor(context) == "T3 Inverter Rotary Compressor"


def test_generate_answer_list_query_never_uses_llm(monkeypatch):
    """
    Regression guard: "show me all X" queries used to be handed to the
    LLM with only ONE product's context, causing it to either refuse
    ("not enough information") or hallucinate a fake product list.
    List queries must now be answered directly from retrieved data.
    """
    products = [
        {"name": "Haier HSU-18HFPAB Air Conditioner", "price": "175000"},
        {"name": "Dawlance Inverter AC", "price": "150000"},
    ]
    monkeypatch.setattr(generator, "retrieve", lambda q, k=3: products)

    def fail_if_called():
        raise AssertionError("get_llm() should never be called for list queries")
    monkeypatch.setattr(generator, "get_llm", fail_if_called)

    answer = generator.generate_answer("show me all air conditioners")

    assert "Haier HSU-18HFPAB Air Conditioner" in answer
    assert "Dawlance Inverter AC" in answer


def test_generate_answer_which_question_not_treated_as_list_query(monkeypatch):
    """
    Regression guard: is_list_query() matches the generic word "which",
    which used to cause structured questions like "which compressor
    does it use?" to be misrouted into the list-formatting branch
    instead of the correct regex-based compressor extraction.
    """
    monkeypatch.setattr(generator, "retrieve", lambda q, k=3: [AC_PRODUCT])
    monkeypatch.setattr(generator, "find_best_product", lambda q: AC_PRODUCT)

    answer = generator.generate_answer("which compressor does it use?")

    assert "matching products" not in answer.lower()
    assert "T3 Tropical Inverter Compressor" in answer


def test_generate_answer_show_me_with_ton_routes_to_list_not_capacity(monkeypatch):
    """
    Regression guard: found via live testing — "show me 1.5 ton Gree air
    conditioners" was misrouted into the single-product capacity
    extractor (because of the word "ton") instead of the list branch,
    because list-detection ran AFTER structured detectors. A strong,
    unambiguous list phrase like "show me" must now win regardless.
    """
    products = [
        {"name": "Gree 12AITH24S-T3 Airy Pro Inverter AC 1 Ton", "price": "186000"},
        {"name": "Gree 18AITH24S-T3 Airy Pro Inverter AC 1.5 Ton", "price": "244000"},
    ]
    monkeypatch.setattr(generator, "retrieve", lambda q, k=3: products)

    answer = generator.generate_answer("show me 1.5 ton Gree air conditioners")

    assert "matching products" in answer.lower()
    assert "Gree 12AITH24S-T3" in answer
    assert "Gree 18AITH24S-T3" in answer


def test_generate_answer_rejects_brand_only_guess_for_structured_question(monkeypatch):
    """
    Regression guard: found via live testing — "what is the price of
    Samsung Galaxy S24?" (a non-existent product) used to confidently
    return the price of an unrelated Samsung washing machine, because
    a brand-only match was treated as confident enough. Structured
    single-fact questions must now require an exact model match via
    find_best_product(), not a loose brand-only guess.
    """
    unrelated_samsung_product = {
        "name": "Samsung WA15CK5745BDRT Automatic Top Load Washing Machine 15 Kg",
        "price": "170000",
    }
    monkeypatch.setattr(generator, "retrieve", lambda q, k=3: [unrelated_samsung_product])
    monkeypatch.setattr(generator, "find_best_product", lambda q: None)

    answer = generator.generate_answer("what is the price of Samsung Galaxy S24?")

    assert "170,000" not in answer
    assert "could not find" in answer.lower()


def test_generate_answer_comparison_notes_unmatched_product_deterministically(monkeypatch):
    """
    Regression guard: found via live testing — a 3-way comparison where
    one named product didn't exist in the catalog still led the LLM to
    invent specs for it (small local models don't reliably follow a
    "don't discuss missing products" instruction). We now track which
    query terms had zero matches and append a deterministic note
    ourselves, regardless of what the LLM says.
    """
    kenwood = {"name": "Kenwood KLU-18B03S Luxury Ultra AC", "price": "169000", "specifications": {}}
    gree = {"name": "Gree 12AITH24S-T3 Airy Pro Inverter AC", "price": "186000", "specifications": {}}

    monkeypatch.setattr(generator, "retrieve", lambda q, k=3: [kenwood, gree])
    monkeypatch.setattr(
        generator, "find_comparison_products", lambda q: ([kenwood, gree], ["hsu-18hfpab"])
    )

    class FakeLLM:
        def invoke(self, prompt):
            return "FINAL ANSWER: comparison text."

    monkeypatch.setattr(generator, "get_llm", lambda: FakeLLM())

    answer = generator.generate_answer(
        "compare Kenwood KLU-18B03S vs Gree 12AITH24S-T3 vs Haier HSU-18HFPAB"
    )

    assert "could not find" in answer.lower()
    assert "hsu-18hfpab" in answer.lower()


def test_generate_answer_comparison_no_note_when_all_products_found(monkeypatch):
    kenwood = {"name": "Kenwood KLU-18B03S Luxury Ultra AC", "price": "169000", "specifications": {}}
    gree = {"name": "Gree 12AITH24S-T3 Airy Pro Inverter AC", "price": "186000", "specifications": {}}

    monkeypatch.setattr(generator, "retrieve", lambda q, k=3: [kenwood, gree])
    monkeypatch.setattr(generator, "find_comparison_products", lambda q: ([kenwood, gree], []))

    class FakeLLM:
        def invoke(self, prompt):
            return "FINAL ANSWER: comparison text."

    monkeypatch.setattr(generator, "get_llm", lambda: FakeLLM())

    answer = generator.generate_answer("compare Kenwood KLU-18B03S vs Gree 12AITH24S-T3")

    assert "could not find" not in answer.lower()


def test_generate_answer_bare_model_number_uses_deterministic_spec_sheet(monkeypatch):
    """
    Regression guard: found via live testing — a bare model number query
    (e.g. just "KLU-18B03S", no explicit price/spec keyword) fell to the
    general LLM path, which repeatedly mis-typed technical terms
    ("Compressor" -> "Compounder", "Inverter" -> "Invierte") and even
    stated the WRONG capacity (2 Ton instead of 1.5 Ton). Whenever an
    exact product is identified via find_best_product(), we now skip
    the LLM entirely and return a deterministic spec sheet instead.
    """
    monkeypatch.setattr(generator, "retrieve", lambda q, k=3: [AC_PRODUCT])
    monkeypatch.setattr(generator, "find_best_product", lambda q: AC_PRODUCT)

    def fail_if_called():
        raise AssertionError("get_llm() should not be called when an exact product is identified")
    monkeypatch.setattr(generator, "get_llm", fail_if_called)

    answer = generator.generate_answer("HSU-18HFPAB")

    assert "Haier HSU-18HFPAB" in answer
    assert "Rs. 175000" in answer
    assert "T3 Tropical Inverter Compressor" in answer


def test_generate_answer_fuzzy_query_still_uses_llm_when_no_exact_product(monkeypatch):
    """
    Sanity check: genuinely fuzzy/semantic queries with no exact model
    match (e.g. "something to cool my room") should still use the LLM,
    since that's a real recommendation task, not a specific fact lookup.
    """
    monkeypatch.setattr(generator, "retrieve", lambda q, k=3: [AC_PRODUCT])
    monkeypatch.setattr(generator, "find_best_product", lambda q: None)

    class FakeLLM:
        def invoke(self, prompt):
            return "FINAL ANSWER: This AC would work well."

    monkeypatch.setattr(generator, "get_llm", lambda: FakeLLM())

    answer = generator.generate_answer("I need something to cool my room")
    assert answer == "This AC would work well."


def test_build_spec_sheet_answer_includes_key_fields():
    product = {
        "name": "Test Product",
        "price": "50000",
        "description": "A great product for everyone. Buy now.",
        "specifications": {"Color": "Black", "Warranty": "1 Year"},
        "url": "https://example.com/test",
    }
    answer = generator.build_spec_sheet_answer(product)
    assert "Test Product" in answer
    assert "Rs. 50000" in answer
    assert "A great product for everyone." in answer
    assert "Buy now" not in answer  # only first sentence kept
    assert "- Color: Black" in answer
    assert "https://example.com/test" in answer


def test_build_spec_sheet_answer_preserves_decimal_in_description():
    """
    Regression guard: found via live testing — splitting the description
    on the first "." naively cut sentences short at a decimal point
    (e.g. "...Price & Review (1.5 Ton..." got truncated to "...(1.").
    """
    product = {
        "name": "Kenwood KLU-18B03S",
        "price": "169000",
        "description": (
            "Description Kenwood Split AC KLU-18B03S Luxury Ultra Price "
            "& Review (1.5 Ton, T3, WiFi). Great for hot summers."
        ),
        "specifications": {"Air Conditioner Capacity": "1.5 Ton"},
    }

    answer = generator.build_spec_sheet_answer(product)

    assert "1.5 Ton, T3, WiFi)." in answer
    assert ".." not in answer  # no double-period artifact
    assert "Great for hot summers" not in answer  # only first sentence kept
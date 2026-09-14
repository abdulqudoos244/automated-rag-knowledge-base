"""
Test suite for builder.py

Run with:  pytest tests/test_builder.py -v

Tests build_documents() directly with in-memory product data —
never touches data/products.json or data/knowledge_base.json.
"""

import sys
import os

sys.path.insert(
    0,
    os.path.join(os.path.dirname(__file__), "..")
)

from App.scraper.knowledge_base.builder import build_documents


FULL_PRODUCT = {
    "name": "Haier HSU-18HFPAB 1.5 Ton Inverter Air Conditioner",
    "price": "175000",
    "price_low": "160000",
    "price_high": "190000",
    "description": "Energy efficient inverter AC with fast cooling.",
    "specifications": {
        "Air Conditioner Capacity": "1.5 Ton",
        "Compressor": "T3 Tropical Inverter Compressor",
        "Refrigerant": "R32",
    },
    "url": "https://example.com/haier-hsu-18hfpab",
}


def test_build_documents_returns_one_document_per_product():
    docs = build_documents([FULL_PRODUCT, FULL_PRODUCT])
    assert len(docs) == 2


def test_build_documents_includes_core_fields():
    docs = build_documents([FULL_PRODUCT])
    doc = docs[0]

    assert "Product Name: Haier HSU-18HFPAB 1.5 Ton Inverter Air Conditioner" in doc
    assert "Current Price: Rs. 175000" in doc
    assert "Lowest Recorded Price: Rs. 160000" in doc
    assert "Highest Recorded Price: Rs. 190000" in doc
    assert "Energy efficient inverter AC with fast cooling." in doc
    assert "Product URL:" in doc
    assert "https://example.com/haier-hsu-18hfpab" in doc


def test_build_documents_writes_all_specifications():
    docs = build_documents([FULL_PRODUCT])
    doc = docs[0]

    assert "- Air Conditioner Capacity: 1.5 Ton" in doc
    assert "- Compressor: T3 Tropical Inverter Compressor" in doc
    assert "- Refrigerant: R32" in doc

    # exactly 3 spec lines, not more/less
    spec_lines = [line for line in doc.splitlines() if line.startswith("- ")]
    assert len(spec_lines) == 3


def test_build_documents_handles_missing_fields():
    sparse_product = {"name": "Generic Blender X100"}

    # must not raise, even though price/description/specifications/url absent
    docs = build_documents([sparse_product])

    assert len(docs) == 1
    assert "Product Name: Generic Blender X100" in docs[0]


def test_build_documents_handles_none_specifications():
    product = {
        "name": "Something",
        "price": "1000",
        "specifications": None,   # e.g. a scraping edge case
        "url": "https://example.com/x",
    }

    # must not raise (None.items() would crash without the `or {}` guard)
    docs = build_documents([product])
    assert "Product Name: Something" in docs[0]


def test_build_documents_empty_specifications_produces_no_spec_lines():
    product = {"name": "No Specs Product", "specifications": {}}
    docs = build_documents([product])

    spec_lines = [line for line in docs[0].splitlines() if line.startswith("- ")]
    assert spec_lines == []


def test_build_documents_empty_product_list_returns_empty_list():
    assert build_documents([]) == []


def test_build_documents_preserves_product_order():
    product_a = {"name": "Product A"}
    product_b = {"name": "Product B"}

    docs = build_documents([product_a, product_b])

    assert "Product A" in docs[0]
    assert "Product B" in docs[1]
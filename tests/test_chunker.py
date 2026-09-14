"""
Test suite for chunker.py

Run with:  pytest tests/test_chunker.py -v

Focus: verifying product_index stays correct — this is the exact
mapping that vector_store.py and retriever.py's FAISS fallback rely
on to find the right product for a given chunk.
"""

import sys
import os

sys.path.insert(
    0,
    os.path.join(os.path.dirname(__file__), "..")
)

from App.scraper.knowledge_base.chunker import chunk_documents


def make_document(word_count, marker=""):
    """Build a fake document with N words, optionally tagged with a marker word."""
    words = [f"word{i}" for i in range(word_count)]
    if marker:
        words.insert(0, marker)
    return " ".join(words)


# ============================================================
# Basic chunk count
# ============================================================

def test_short_document_produces_one_chunk():
    documents = [make_document(50)]
    chunks = chunk_documents(documents, chunk_size=500)

    assert len(chunks) == 1
    assert chunks[0]["product_index"] == 0


def test_document_exactly_at_chunk_size_produces_one_chunk():
    documents = [make_document(500)]
    chunks = chunk_documents(documents, chunk_size=500)

    assert len(chunks) == 1


def test_document_over_chunk_size_splits_into_two_chunks():
    documents = [make_document(600)]  # 100 words over the 500 limit
    chunks = chunk_documents(documents, chunk_size=500)

    assert len(chunks) == 2
    # Both halves must still point back to the SAME product (index 0)
    assert chunks[0]["product_index"] == 0
    assert chunks[1]["product_index"] == 0


def test_document_over_chunk_size_splits_words_correctly():
    documents = [make_document(600)]
    chunks = chunk_documents(documents, chunk_size=500)

    first_chunk_words = chunks[0]["text"].split()
    second_chunk_words = chunks[1]["text"].split()

    assert len(first_chunk_words) == 500
    assert len(second_chunk_words) == 100


def test_empty_document_produces_no_chunks():
    documents = [""]
    chunks = chunk_documents(documents, chunk_size=500)
    assert chunks == []


def test_whitespace_only_document_produces_no_chunks():
    documents = ["   \n\t  "]
    chunks = chunk_documents(documents, chunk_size=500)
    assert chunks == []


# ============================================================
# THE CRITICAL TEST — product_index correctness across mixed documents
# ============================================================

def test_product_index_stays_correct_when_products_split_differently():
    """
    Regression guard for the original bug: chunk_id used to be assumed
    equal to the product's position in products.json, which broke the
    moment any single product's document got split into multiple chunks
    (shifting every following product's index out of alignment).

    This test builds 3 products where the middle one is long enough to
    split into 2 chunks, and verifies the chunk COUNT per product_index
    is correct, and product_index 2 (which comes AFTER the split
    product) still points at the right product.
    """

    documents = [
        make_document(50, marker="PRODUCT_A"),   # index 0 -> 1 chunk
        make_document(600, marker="PRODUCT_B"),  # index 1 -> 2 chunks
        make_document(50, marker="PRODUCT_C"),   # index 2 -> 1 chunk
    ]

    chunks = chunk_documents(documents, chunk_size=500)

    # 1 + 2 + 1 = 4 chunks total, but only 3 real products
    assert len(chunks) == 4

    index_0_chunks = [c for c in chunks if c["product_index"] == 0]
    index_1_chunks = [c for c in chunks if c["product_index"] == 1]
    index_2_chunks = [c for c in chunks if c["product_index"] == 2]

    assert len(index_0_chunks) == 1
    assert "PRODUCT_A" in index_0_chunks[0]["text"]

    # The split product produced 2 chunks, BOTH must carry product_index 1
    # (the old bug would have given these indices 1 and 2, colliding with
    # the next real product).
    assert len(index_1_chunks) == 2

    # PRODUCT_C must still correctly map to index 2, even though it comes
    # after a product that produced 2 chunks — this is the exact case the
    # old chunk_id == list-position assumption would get wrong.
    assert len(index_2_chunks) == 1
    assert "PRODUCT_C" in index_2_chunks[0]["text"]


def test_product_index_matches_original_products_list_order():
    """
    End-to-end sanity check: reconstruct each product's full text from its
    chunks (in order) and confirm it exactly matches the original document
    — proving no words/chunks leak into the wrong product_index.
    """

    documents = [
        "Product Alpha " + ("filler " * 700),
        "Product Beta " + ("filler " * 10),
        "Product Gamma " + ("filler " * 900),
    ]

    chunks = chunk_documents(documents, chunk_size=500)

    for product_index, original_document in enumerate(documents):

        product_chunks = [
            c for c in chunks if c["product_index"] == product_index
        ]

        reconstructed_words = []
        for chunk in product_chunks:
            reconstructed_words.extend(chunk["text"].split())

        assert reconstructed_words == original_document.split()


def test_custom_chunk_size():
    documents = [make_document(30)]
    chunks = chunk_documents(documents, chunk_size=10)

    assert len(chunks) == 3
    assert all(c["product_index"] == 0 for c in chunks)
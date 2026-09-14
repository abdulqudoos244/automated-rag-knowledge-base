"""
Test suite for parser.py

Run with:  pytest tests/test_parser.py -v

extract_product() is tested against fake HTML (built to match the same
CSS selectors the real AYS Online site uses) via a mocked requests.get —
these tests never make a real network call.
"""

import sys
import os

sys.path.insert(
    0,
    os.path.join(os.path.dirname(__file__), "..")
)

import requests
from App.scraper import parser


SAMPLE_HTML = """
<html>
  <body>
    <h1>Haier HSU-18HFPAB 1.5 Ton Inverter Air Conditioner</h1>

    <div class="woocommerce-product-gallery__image">
      <img src="https://example.com/haier.jpg" />
    </div>

    <div class="summary">
      <p class="price">Rs. 175,000</p>
    </div>

    <div class="ays-ph-summary">
      The current price is Rs. 175,000. This product has a recorded low of Rs. 160,000 and a recorded high of Rs. 190,000.
    </div>

    <div class="woocommerce-product-details__short-description">
      Energy efficient inverter AC with fast cooling.
    </div>

    <table class="woocommerce-product-attributes">
      <tr><th>Compressor</th><td>T3 Tropical Inverter Compressor</td></tr>
      <tr><th>Refrigerant</th><td>R32</td></tr>
    </table>
  </body>
</html>
"""

MINIMAL_HTML = "<html><body><p>Not a product page</p></body></html>"


class FakeResponse:
    def __init__(self, text, status_code=200):
        self.text = text
        self.status_code = status_code

    def raise_for_status(self):
        if self.status_code >= 400:
            raise requests.HTTPError(f"status {self.status_code}")


# ============================================================
# extract_product — happy path
# ============================================================

def test_extract_product_parses_name(monkeypatch):
    monkeypatch.setattr(
        requests, "get", lambda *a, **k: FakeResponse(SAMPLE_HTML)
    )
    product = parser.extract_product("https://example.com/haier-hsu-18hfpab")
    assert product["name"] == "Haier HSU-18HFPAB 1.5 Ton Inverter Air Conditioner"


def test_extract_product_parses_price(monkeypatch):
    monkeypatch.setattr(
        requests, "get", lambda *a, **k: FakeResponse(SAMPLE_HTML)
    )
    product = parser.extract_product("https://example.com/haier-hsu-18hfpab")
    assert product["price"] == "175000"


def test_extract_product_parses_price_history(monkeypatch):
    monkeypatch.setattr(
        requests, "get", lambda *a, **k: FakeResponse(SAMPLE_HTML)
    )
    product = parser.extract_product("https://example.com/haier-hsu-18hfpab")
    assert product["price_low"] == "160000"
    assert product["price_high"] == "190000"


def test_extract_product_parses_description(monkeypatch):
    monkeypatch.setattr(
        requests, "get", lambda *a, **k: FakeResponse(SAMPLE_HTML)
    )
    product = parser.extract_product("https://example.com/haier-hsu-18hfpab")
    assert "Energy efficient inverter AC" in product["description"]


def test_extract_product_parses_specifications(monkeypatch):
    monkeypatch.setattr(
        requests, "get", lambda *a, **k: FakeResponse(SAMPLE_HTML)
    )
    product = parser.extract_product("https://example.com/haier-hsu-18hfpab")
    assert product["specifications"]["Compressor"] == "T3 Tropical Inverter Compressor"
    assert product["specifications"]["Refrigerant"] == "R32"


def test_extract_product_parses_image(monkeypatch):
    monkeypatch.setattr(
        requests, "get", lambda *a, **k: FakeResponse(SAMPLE_HTML)
    )
    product = parser.extract_product("https://example.com/haier-hsu-18hfpab")
    assert product["image"] == "https://example.com/haier.jpg"


def test_extract_product_keeps_url():
    pass  # covered implicitly below


def test_extract_product_url_field_matches_input(monkeypatch):
    monkeypatch.setattr(
        requests, "get", lambda *a, **k: FakeResponse(SAMPLE_HTML)
    )
    url = "https://example.com/haier-hsu-18hfpab"
    product = parser.extract_product(url)
    assert product["url"] == url


# ============================================================
# extract_product — missing/degraded data
# ============================================================

def test_extract_product_no_name_returns_none_name(monkeypatch):
    monkeypatch.setattr(
        requests, "get", lambda *a, **k: FakeResponse(MINIMAL_HTML)
    )
    product = parser.extract_product("https://example.com/not-a-product")
    assert product["name"] is None


def test_extract_product_no_specs_returns_empty_dict(monkeypatch):
    monkeypatch.setattr(
        requests, "get", lambda *a, **k: FakeResponse(MINIMAL_HTML)
    )
    product = parser.extract_product("https://example.com/not-a-product")
    assert product["specifications"] == {}


def test_extract_product_no_price_returns_none(monkeypatch):
    monkeypatch.setattr(
        requests, "get", lambda *a, **k: FakeResponse(MINIMAL_HTML)
    )
    product = parser.extract_product("https://example.com/not-a-product")
    assert product["price"] is None


# ============================================================
# Retry logic
# ============================================================

def test_extract_product_retries_then_succeeds(monkeypatch):
    call_count = {"n": 0}

    def flaky_get(*a, **k):
        call_count["n"] += 1
        if call_count["n"] < 3:
            raise requests.ConnectionError("simulated network blip")
        return FakeResponse(SAMPLE_HTML)

    monkeypatch.setattr(requests, "get", flaky_get)
    monkeypatch.setattr(parser.time, "sleep", lambda *a, **k: None)  # skip real delay

    product = parser.extract_product("https://example.com/haier-hsu-18hfpab")

    assert call_count["n"] == 3
    assert product["name"] == "Haier HSU-18HFPAB 1.5 Ton Inverter Air Conditioner"


def test_extract_product_raises_after_max_retries(monkeypatch):
    def always_fails(*a, **k):
        raise requests.ConnectionError("simulated network failure")

    monkeypatch.setattr(requests, "get", always_fails)
    monkeypatch.setattr(parser.time, "sleep", lambda *a, **k: None)

    try:
        parser.extract_product("https://example.com/unreachable")
        assert False, "expected extract_product to raise after MAX_RETRIES"
    except requests.ConnectionError:
        pass
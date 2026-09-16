import os
import sys
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

import attribution


class FakeResponse:
    def __init__(self, text, status_code=200):
        self.text = text
        self.status_code = status_code


def test_fetch_website_facts_finds_phone(monkeypatch):
    html = "<html><body>Call us at (719) 555-1234</body></html>"
    monkeypatch.setattr(attribution.requests, "get", lambda *a, **k: FakeResponse(html))
    facts = attribution.fetch_website_facts("example.com")
    assert facts["phone"] == "7195551234"
    assert facts["fetched"] is True


def test_fetch_website_facts_no_phone_found(monkeypatch):
    monkeypatch.setattr(attribution.requests, "get", lambda *a, **k: FakeResponse("<html>no phone here</html>"))
    facts = attribution.fetch_website_facts("example.com")
    assert facts["phone"] is None


def test_fetch_website_facts_request_fails(monkeypatch):
    def raise_error(*a, **k):
        raise attribution.requests.RequestException("timeout")
    monkeypatch.setattr(attribution.requests, "get", raise_error)
    facts = attribution.fetch_website_facts("example.com")
    assert facts == {"phone": None, "fetched": False}


def test_attribute_answer_matches_website():
    website_facts = {"phone": "7195551234", "fetched": True}
    result = attribution.attribute_answer("Call 719-555-1234 for a quote.", {}, website_facts)
    assert result == "website"


def test_attribute_answer_matches_a_listing_source():
    website_facts = {"phone": None, "fetched": True}
    listing_sources = {"Google": {"found": True, "phone": "(719) 555-9999"}}
    result = attribution.attribute_answer("Their number is 719-555-9999.", listing_sources, website_facts)
    assert result == "Google"


def test_attribute_answer_unknown_when_no_source_matches():
    website_facts = {"phone": "7195551234", "fetched": True}
    listing_sources = {"Google": {"found": True, "phone": "7195559999"}}
    result = attribution.attribute_answer("Call 719-000-0000.", listing_sources, website_facts)
    assert result == "unknown"


def test_attribute_answer_none_when_no_phone_in_quote():
    website_facts = {"phone": "7195551234", "fetched": True}
    assert attribution.attribute_answer("A great local photographer.", {}, website_facts) is None


def test_attribute_all_only_counts_mentioning_answers_with_a_phone():
    website_facts = {"phone": "7195551234", "fetched": True}
    results = [
        {"mentioned": True, "quote": "Call 719-555-1234."},
        {"mentioned": True, "quote": "No phone mentioned."},
        {"mentioned": False, "quote": "Call 719-555-1234."},
    ]
    counts = attribution.attribute_all(results, {}, website_facts)
    assert counts == {"website": 1}


if __name__ == "__main__":
    import pytest
    raise SystemExit(pytest.main([__file__, "-q"]))

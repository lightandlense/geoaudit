import os
import sys
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

import listings


class FakeResponse:
    def __init__(self, json_data, status_code=200):
        self._json = json_data
        self.status_code = status_code

    def json(self):
        return self._json

    def raise_for_status(self):
        if self.status_code >= 400:
            raise listings.requests.HTTPError(f"HTTP {self.status_code}")


# ---- fetch_* soft-fail on missing key ----

def test_fetch_google_no_key():
    assert listings.fetch_google("Acme", "Denver", None) == listings._empty()


def test_fetch_yelp_no_key():
    assert listings.fetch_yelp("Acme", "Denver", None) == listings._empty()


def test_fetch_foursquare_no_key():
    assert listings.fetch_foursquare("Acme", "Denver", None) == listings._empty()


# ---- fetch_yelp with mocked HTTP ----

def test_fetch_yelp_found(monkeypatch):
    search_resp = FakeResponse({"businesses": [{"id": "abc123"}]})
    details_resp = FakeResponse({
        "name": "Acme Photography",
        "location": {"address1": "123 Main St", "city": "Denver", "state": "CO", "zip_code": "80202"},
        "display_phone": "(303) 555-1212",
        "categories": [{"alias": "photographers", "title": "Photographers"}],
        "hours": [{"hour_type": "REGULAR", "open": [{"day": 1, "start": "0900", "end": "1700",
                                                       "is_overnight": False}]}],
    })
    calls = [search_resp, details_resp]
    monkeypatch.setattr(listings.requests, "get", lambda *a, **k: calls.pop(0))
    result = listings.fetch_yelp("Acme Photography", "Denver", "fake-key")
    assert result["found"] is True
    assert result["name"] == "Acme Photography"
    assert "123 Main St" in result["address"]
    assert result["phone"] == "(303) 555-1212"
    assert result["category"] == "Photographers"
    assert "day1" in result["hours"]


def test_fetch_yelp_no_match(monkeypatch):
    monkeypatch.setattr(listings.requests, "get", lambda *a, **k: FakeResponse({"businesses": []}))
    result = listings.fetch_yelp("Nobody", "Nowhere", "fake-key")
    assert result == listings._empty()


def test_fetch_yelp_request_error(monkeypatch):
    def raise_error(*a, **k):
        raise listings.requests.RequestException("timeout")
    monkeypatch.setattr(listings.requests, "get", raise_error)
    result = listings.fetch_yelp("Acme", "Denver", "fake-key")
    assert result == listings._empty()


# ---- fetch_foursquare with mocked HTTP ----

def test_fetch_foursquare_found(monkeypatch):
    resp = FakeResponse({"results": [{
        "name": "Acme Photography",
        "location": {"formatted_address": "123 Main St, Denver, CO 80202"},
        "tel": "+13035551212",
        "categories": [{"name": "Photography Studio"}],
        "hours": {"display": "Mon-Fri 9:00 AM-5:00 PM", "open_now": True},
    }]})
    monkeypatch.setattr(listings.requests, "get", lambda *a, **k: resp)
    result = listings.fetch_foursquare("Acme Photography", "Denver", "fake-key")
    assert result["found"] is True
    assert result["address"] == "123 Main St, Denver, CO 80202"
    assert result["phone"] == "+13035551212"
    assert result["category"] == "Photography Studio"


def test_fetch_foursquare_no_match(monkeypatch):
    monkeypatch.setattr(listings.requests, "get", lambda *a, **k: FakeResponse({"results": []}))
    result = listings.fetch_foursquare("Nobody", "Nowhere", "fake-key")
    assert result == listings._empty()


# ---- fetch_google reuses resolve.py, minimal mock at that boundary ----

def test_fetch_google_found(monkeypatch):
    monkeypatch.setattr(listings.resolve, "_find_place",
                         lambda business, city, key: {"place_id": "p1", "name": "Acme Photography",
                                                        "types": ["photographer"]})
    monkeypatch.setattr(listings.resolve, "_place_details",
                         lambda place_id, key, fields=None: {
                             "name": "Acme Photography",
                             "formatted_address": "123 Main St, Denver, CO",
                             "formatted_phone_number": "(303) 555-1212",
                             "opening_hours": {"weekday_text": ["Monday: 9:00 AM – 5:00 PM"]},
                             "types": ["photographer"],
                         })
    result = listings.fetch_google("Acme Photography", "Denver", "fake-key")
    assert result["found"] is True
    assert result["address"] == "123 Main St, Denver, CO"
    assert "Monday" in result["hours"]


def test_fetch_google_no_place(monkeypatch):
    monkeypatch.setattr(listings.resolve, "_find_place", lambda business, city, key: None)
    result = listings.fetch_google("Nobody", "Nowhere", "fake-key")
    assert result == listings._empty()


# ---- compare_nap ----

def test_compare_nap_not_enough_sources():
    sources = {"Google": listings._empty(), "Yelp": {**listings._empty(), "found": True, "name": "Acme"}}
    result = listings.compare_nap(sources)
    assert result["disagreements"] is None
    assert result["note"] == "not enough sources configured to compare"


def test_compare_nap_all_agree():
    a = {"name": "Acme Photography", "address": "123 Main St, Denver, CO", "phone": "(303) 555-1212",
         "hours": "Mon-Fri 9-5", "category": "Photographer", "found": True}
    b = {"name": "Acme Photography", "address": "123 MAIN ST, DENVER, CO", "phone": "303-555-1212",
         "hours": "Mon-Fri 9-5", "category": "photographer", "found": True}
    result = listings.compare_nap({"Google": a, "Yelp": b})
    assert result["disagreements"] == []


def test_compare_nap_inconsistent_beats_missing():
    a = {"name": "Acme Photography", "address": "123 Main St", "phone": "(303) 555-1212",
         "hours": None, "category": "Photographer", "found": True}
    b = {"name": "Acme Photo Studio", "address": "123 Main St", "phone": "(303) 555-9999",
         "hours": None, "category": "Photographer", "found": True}
    result = listings.compare_nap({"Google": a, "Yelp": b})
    by_field = {d["field"]: d["severity"] for d in result["disagreements"]}
    assert by_field["name"] == "inconsistent"
    assert by_field["phone"] == "inconsistent"
    assert "hours" not in by_field  # missing from both -- nothing to disagree about
    assert "address" not in by_field  # agrees


def test_compare_nap_missing_from_one_source():
    a = {"name": "Acme Photography", "address": "123 Main St", "phone": "(303) 555-1212",
         "hours": "Mon-Fri 9-5", "category": "Photographer", "found": True}
    b = {"name": "Acme Photography", "address": "123 Main St", "phone": "(303) 555-1212",
         "hours": None, "category": "Photographer", "found": True}
    result = listings.compare_nap({"Google": a, "Yelp": b})
    by_field = {d["field"]: d["severity"] for d in result["disagreements"]}
    assert by_field["hours"] == "missing"


if __name__ == "__main__":
    import pytest
    raise SystemExit(pytest.main([__file__, "-q"]))

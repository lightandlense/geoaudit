import os
import sys
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

import pytest
import resolve


class FakeResponse:
    def __init__(self, json_data, status_code=200):
        self._json = json_data
        self.status_code = status_code

    def json(self):
        return self._json

    def raise_for_status(self):
        if self.status_code >= 400:
            raise resolve.requests.HTTPError(f"HTTP {self.status_code}")


def test_verdict_green():
    assert resolve._verdict(4.5, 20, 30) == "GREEN"


def test_verdict_good_fit_stale():
    assert resolve._verdict(4.5, 20, 400) == "GOOD FIT"


def test_verdict_good_fit_sparse():
    assert resolve._verdict(4.5, 3, 10) == "GOOD FIT"


def test_verdict_pause():
    assert resolve._verdict(3.2, 20, 10) == "PAUSE"


def test_verdict_open_field():
    assert resolve._verdict(None, None, None) == "OPEN FIELD"


def test_resolve_business_no_api_key_uses_supplied_website(monkeypatch):
    monkeypatch.delenv("GOOGLE_PLACES_API_KEY", raising=False)
    result = resolve.resolve_business("Peak Roofing", "Colorado Springs", website="https://peakroofing.com")
    assert result["website"] == "https://peakroofing.com"
    assert result["profile_found"] is False
    assert result["verdict"] == "OPEN FIELD"


def test_resolve_business_no_website_no_key_raises(monkeypatch):
    monkeypatch.delenv("GOOGLE_PLACES_API_KEY", raising=False)
    with pytest.raises(ValueError):
        resolve.resolve_business("Peak Roofing", "Colorado Springs")


# ---- Places API (New) request/response shape ----

def test_find_place_posts_new_api_shape(monkeypatch):
    captured = {}

    def fake_post(url, headers=None, json=None, timeout=None):
        captured["url"] = url
        captured["headers"] = headers
        captured["json"] = json
        return FakeResponse({"places": [{"id": "abc123", "displayName": {"text": "Peak Roofing"},
                                          "types": ["roofing_contractor"]}]})

    monkeypatch.setattr(resolve.requests, "post", fake_post)
    place = resolve._find_place("Peak Roofing", "Colorado Springs", "fake-key")

    assert captured["url"] == "https://places.googleapis.com/v1/places:searchText"
    assert captured["headers"]["X-Goog-Api-Key"] == "fake-key"
    assert "places.id" in captured["headers"]["X-Goog-FieldMask"]
    assert captured["json"] == {"textQuery": "Peak Roofing Colorado Springs"}
    assert place == {"place_id": "abc123", "name": "Peak Roofing", "types": ["roofing_contractor"]}


def test_find_place_no_results(monkeypatch):
    monkeypatch.setattr(resolve.requests, "post", lambda *a, **k: FakeResponse({"places": []}))
    assert resolve._find_place("Nobody", "Nowhere", "fake-key") is None


def test_place_details_new_api_shape(monkeypatch):
    captured = {}

    def fake_get(url, headers=None, timeout=None):
        captured["url"] = url
        captured["headers"] = headers
        return FakeResponse({
            "websiteUri": "https://peakroofing.com",
            "rating": 4.7,
            "userRatingCount": 42,
            "types": ["roofing_contractor", "point_of_interest"],
            "reviews": [
                {"publishTime": "2026-08-01T12:00:00Z"},
                {"publishTime": "2026-09-01T12:00:00Z"},
            ],
        })

    monkeypatch.setattr(resolve.requests, "get", fake_get)
    details = resolve._place_details("abc123", "fake-key")

    assert captured["url"] == "https://places.googleapis.com/v1/places/abc123"
    assert captured["headers"]["X-Goog-Api-Key"] == "fake-key"
    assert "websiteUri" in captured["headers"]["X-Goog-FieldMask"]
    assert details["website"] == "https://peakroofing.com"
    assert details["rating"] == 4.7
    assert details["user_ratings_total"] == 42
    assert details["types"] == ["roofing_contractor", "point_of_interest"]
    # publishTime (RFC3339) converted to epoch, not left as a string
    assert all(isinstance(r["time"], float) for r in details["reviews"])


def test_place_details_extended_fields_for_listings(monkeypatch):
    monkeypatch.setattr(resolve.requests, "get", lambda *a, **k: FakeResponse({
        "displayName": {"text": "Peak Roofing"},
        "formattedAddress": "123 Main St, Colorado Springs, CO",
        "nationalPhoneNumber": "(719) 555-1212",
        "regularOpeningHours": {"weekdayDescriptions": ["Monday: 8:00 AM – 5:00 PM"]},
    }))
    details = resolve._place_details(
        "abc123", "fake-key",
        fields="name,formatted_address,formatted_phone_number,opening_hours,types",
    )
    assert details["name"] == "Peak Roofing"
    assert details["formatted_address"] == "123 Main St, Colorado Springs, CO"
    assert details["formatted_phone_number"] == "(719) 555-1212"
    assert details["opening_hours"]["weekday_text"] == ["Monday: 8:00 AM – 5:00 PM"]


def test_resolve_business_end_to_end_with_new_api(monkeypatch):
    monkeypatch.setenv("GOOGLE_PLACES_API_KEY", "fake-key")
    monkeypatch.setattr(resolve.requests, "post", lambda *a, **k: FakeResponse(
        {"places": [{"id": "abc123", "displayName": {"text": "Peak Roofing"}, "types": ["roofing_contractor"]}]}))
    monkeypatch.setattr(resolve.requests, "get", lambda *a, **k: FakeResponse({
        "websiteUri": "https://peakroofing.com", "rating": 4.7, "userRatingCount": 42,
        "types": ["roofing_contractor"], "reviews": [{"publishTime": "2026-09-01T12:00:00Z"}],
    }))
    result = resolve.resolve_business("Peak Roofing", "Colorado Springs")
    assert result["website"] == "https://peakroofing.com"
    assert result["profile_found"] is True
    assert result["industry"] == "roofing contractor"


if __name__ == "__main__":
    raise SystemExit(pytest.main([__file__, "-q"]))

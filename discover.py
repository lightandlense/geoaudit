"""Discover the SUPPLY side: every business in a vertical+city via Google Places,
filtered by the ideal-client rubric (rating + review count).

Uses the same legacy Places Text Search endpoint as resolve.py (same API key).
Text Search already returns rating + user_ratings_total, so no per-business
Details call is needed here — keeps a full-city scan to a handful of requests.
"""
import os
import time
import requests

PLACES_TEXTSEARCH = "https://maps.googleapis.com/maps/api/place/textsearch/json"


def _page(params):
    resp = requests.get(PLACES_TEXTSEARCH, params=params, timeout=15)
    resp.raise_for_status()
    body = resp.json()
    status = body.get("status")
    if status not in ("OK", "ZERO_RESULTS"):
        raise RuntimeError(f"Places API status={status}: {body.get('error_message', '')}")
    return body.get("results", []), body.get("next_page_token")


def discover_candidates(vertical, city, min_rating=4.0, min_reviews=25, max_results=60):
    """Return rubric-passing businesses, sorted by review count desc.

    Each item: name, place_id, rating, review_count, address.
    max_results caps at 60 (Places returns up to 3 pages of 20).
    """
    api_key = os.environ.get("GOOGLE_PLACES_API_KEY")
    if not api_key:
        raise RuntimeError("GOOGLE_PLACES_API_KEY not set")

    params = {"query": f"{vertical} in {city}", "key": api_key}
    raw = []
    while len(raw) < max_results:
        results, token = _page(params)
        raw.extend(results)
        if not token:
            break
        # Google requires a short delay before a next_page_token becomes valid.
        time.sleep(2)
        params = {"pagetoken": token, "key": api_key}

    seen = set()
    candidates = []
    for r in raw:
        pid = r.get("place_id")
        if pid in seen:
            continue
        seen.add(pid)
        rating = r.get("rating")
        reviews = r.get("user_ratings_total") or 0
        if rating is None or rating < min_rating or reviews < min_reviews:
            continue
        candidates.append({
            "name": r.get("name"),
            "place_id": pid,
            "rating": rating,
            "review_count": reviews,
            "address": r.get("formatted_address", ""),
        })

    candidates.sort(key=lambda c: c["review_count"], reverse=True)
    return candidates

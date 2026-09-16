"""Google Places lookup + qualifying verdict logic.

Uses Places API (New) -- the legacy Text Search/Details JSON API is
deprecated and REQUEST_DENIED for keys not specifically enabled for it.
Verified live against Google's current docs 2026-09-16 (POST + JSON body,
X-Goog-Api-Key header, X-Goog-FieldMask header, no `key` query param).

Public function signatures and resolve_business()'s return shape are
unchanged from the legacy version -- callers (listings.fetch_google,
audit.py) don't need to change. _place_details still accepts the OLD
legacy-style field names in its `fields` param (translated internally to
the New API's field mask) so existing call sites keep working unchanged.
"""
import os
import time
from datetime import datetime

import requests

PLACES_SEARCH_TEXT = "https://places.googleapis.com/v1/places:searchText"
PLACES_DETAILS = "https://places.googleapis.com/v1/places"

_SEARCH_FIELD_MASK = "places.id,places.displayName,places.types"

# Legacy field name -> New API field-mask path. Kept so _place_details's
# public `fields` param (and callers passing it) don't need to change.
_FIELD_MASK_MAP = {
    "website": "websiteUri",
    "rating": "rating",
    "user_ratings_total": "userRatingCount",
    "reviews": "reviews",
    "types": "types",
    "name": "displayName",
    "formatted_address": "formattedAddress",
    "formatted_phone_number": "nationalPhoneNumber",
    "opening_hours": "regularOpeningHours",
}

# Places "types" that aren't a useful industry label on their own.
GENERIC_TYPES = {
    "point_of_interest", "establishment", "premise", "store",
    "food", "health", "local_government_office",
}


def _find_place(name, city, api_key):
    resp = requests.post(
        PLACES_SEARCH_TEXT,
        headers={
            "X-Goog-Api-Key": api_key,
            "X-Goog-FieldMask": _SEARCH_FIELD_MASK,
            "Content-Type": "application/json",
        },
        json={"textQuery": f"{name} {city}"},
        timeout=10,
    )
    resp.raise_for_status()
    places = resp.json().get("places") or []
    if not places:
        return None
    place = places[0]
    return {
        "place_id": place.get("id"),
        "name": (place.get("displayName") or {}).get("text"),
        "types": place.get("types"),
    }


def _publish_time_to_epoch(publish_time):
    """New API reviews use an RFC3339 `publishTime` string, not a Unix
    `time` int like the legacy API. Convert so _newest_review_days doesn't
    need to change."""
    if not publish_time:
        return 0
    try:
        return datetime.fromisoformat(publish_time.replace("Z", "+00:00")).timestamp()
    except ValueError:
        return 0


def _place_details(place_id, api_key, fields="website,rating,user_ratings_total,reviews,types"):
    legacy_fields = [f.strip() for f in fields.split(",") if f.strip()]
    field_mask = ",".join(_FIELD_MASK_MAP.get(f, f) for f in legacy_fields)

    resp = requests.get(
        f"{PLACES_DETAILS}/{place_id}",
        headers={"X-Goog-Api-Key": api_key, "X-Goog-FieldMask": field_mask},
        timeout=10,
    )
    resp.raise_for_status()
    new_result = resp.json() or {}

    result = {}
    if "website" in legacy_fields:
        result["website"] = new_result.get("websiteUri")
    if "rating" in legacy_fields:
        result["rating"] = new_result.get("rating")
    if "user_ratings_total" in legacy_fields:
        result["user_ratings_total"] = new_result.get("userRatingCount")
    if "reviews" in legacy_fields:
        result["reviews"] = [
            {"time": _publish_time_to_epoch(r.get("publishTime"))}
            for r in (new_result.get("reviews") or [])
        ]
    if "types" in legacy_fields:
        result["types"] = new_result.get("types")
    if "name" in legacy_fields:
        result["name"] = (new_result.get("displayName") or {}).get("text")
    if "formatted_address" in legacy_fields:
        result["formatted_address"] = new_result.get("formattedAddress")
    if "formatted_phone_number" in legacy_fields:
        result["formatted_phone_number"] = (new_result.get("nationalPhoneNumber")
                                             or new_result.get("internationalPhoneNumber"))
    if "opening_hours" in legacy_fields:
        weekday_text = (new_result.get("regularOpeningHours") or {}).get("weekdayDescriptions")
        result["opening_hours"] = {"weekday_text": weekday_text} if weekday_text else {}
    return result


def _infer_industry(types):
    for t in types or []:
        if t not in GENERIC_TYPES:
            return t.replace("_", " ")
    return None


def _newest_review_days(reviews):
    if not reviews:
        return None
    newest = max(r.get("time", 0) for r in reviews)
    return int((time.time() - newest) / 86400)


def _verdict(rating, review_count, newest_days):
    if rating is None:
        return "OPEN FIELD"
    if rating < 4.0:
        return "PAUSE"
    if newest_days is not None and newest_days < 90 and (review_count or 0) >= 10:
        return "GREEN"
    return "GOOD FIT"


def resolve_business(name, city, website=None, industry=None):
    """Returns a dict: website, rating, review_count, newest_review_days,
    verdict, industry, profile_found."""
    api_key = os.environ.get("GOOGLE_PLACES_API_KEY")

    place = None
    details = {}
    if api_key:
        place = _find_place(name, city, api_key)
        if place:
            details = _place_details(place["place_id"], api_key)

    rating = details.get("rating")
    review_count = details.get("user_ratings_total")
    newest_days = _newest_review_days(details.get("reviews"))
    resolved_website = website or details.get("website")
    resolved_industry = industry or _infer_industry(details.get("types"))

    if not resolved_website:
        raise ValueError(
            "No website found via Google Places and none supplied with --website."
        )

    return {
        "website": resolved_website,
        "rating": rating,
        "review_count": review_count,
        "newest_review_days": newest_days,
        "verdict": _verdict(rating, review_count, newest_days),
        "industry": resolved_industry or "local business",
        "profile_found": place is not None,
    }

"""Listings/NAP consistency check (SPEC-8 check 6): Google Business Profile,
Yelp, Foursquare. Each fetch fails soft (missing key or no match -> found:
False) -- same style as checks.py. None of the three keys are configured yet
(2026-09); this is built ready to run the moment they land.

API shapes verified live against current docs 2026-09-16, not guessed:
- Google: reuses resolve.py's Places Text Search + Details (same place_id,
  no duplicate search call), Details fields extended for
  formatted_address/formatted_phone_number/opening_hours.
- Yelp Fusion v3: /v3/businesses/search then /v3/businesses/{id} for hours.
  Confirmed field names (location.address1/city/state/zip_code,
  display_phone, categories[].title, hours[].open[].day/start/end) via the
  published OpenAPI spec.
- Foursquare Places API (2025 rewrite, base https://places-api.foursquare.com):
  GET /places/search, Bearer token. Confirmed response field names
  (location.formatted_address, tel, categories[].name, hours.display) via
  current docs. NOT confirmed: whether this API version needs an extra
  version header beyond the bearer token (their docs reference a
  ServiceKeyBearerTokenAuth scheme without detailing headers) -- check
  Foursquare's onboarding docs when the key arrives; a wrong/missing header
  just fails soft here like any other error, it doesn't silently misreport.
"""
import re
import requests

import resolve

TIMEOUT = 10


def _empty():
    return {"name": None, "address": None, "phone": None, "hours": None,
            "category": None, "found": False}


def fetch_google(business, city, api_key):
    if not api_key:
        return _empty()
    try:
        place = resolve._find_place(business, city, api_key)
        if not place:
            return _empty()
        details = resolve._place_details(
            place["place_id"], api_key,
            fields="name,formatted_address,formatted_phone_number,opening_hours,types",
        )
    except requests.RequestException:
        return _empty()

    hours = None
    weekday_text = (details.get("opening_hours") or {}).get("weekday_text")
    if weekday_text:
        hours = "; ".join(weekday_text)

    return {
        "name": details.get("name") or place.get("name"),
        "address": details.get("formatted_address"),
        "phone": details.get("formatted_phone_number"),
        "hours": hours,
        "category": resolve._infer_industry(details.get("types") or place.get("types")),
        "found": True,
    }


def fetch_yelp(business, city, api_key):
    if not api_key:
        return _empty()
    try:
        r = requests.get(
            "https://api.yelp.com/v3/businesses/search",
            headers={"Authorization": f"Bearer {api_key}"},
            params={"term": business, "location": city, "limit": 1},
            timeout=TIMEOUT,
        )
        r.raise_for_status()
        results = r.json().get("businesses") or []
        if not results:
            return _empty()
        biz_id = results[0]["id"]

        details_r = requests.get(
            f"https://api.yelp.com/v3/businesses/{biz_id}",
            headers={"Authorization": f"Bearer {api_key}"},
            timeout=TIMEOUT,
        )
        details_r.raise_for_status()
        biz = details_r.json()
    except requests.RequestException:
        return _empty()

    hours = None
    hour_blocks = biz.get("hours") or []
    if hour_blocks:
        opens = hour_blocks[0].get("open") or []
        if opens:
            hours = "; ".join(f"day{o.get('day')} {o.get('start')}-{o.get('end')}" for o in opens)

    location = biz.get("location") or {}
    address_parts = [location.get("address1"), location.get("city"),
                      location.get("state"), location.get("zip_code")]
    categories = biz.get("categories") or []

    return {
        "name": biz.get("name"),
        "address": ", ".join(p for p in address_parts if p) or None,
        "phone": biz.get("display_phone") or biz.get("phone"),
        "hours": hours,
        "category": categories[0]["title"] if categories else None,
        "found": True,
    }


def fetch_foursquare(business, city, api_key):
    if not api_key:
        return _empty()
    try:
        r = requests.get(
            "https://places-api.foursquare.com/places/search",
            headers={"Authorization": f"Bearer {api_key}"},
            params={"query": business, "near": city, "limit": 1,
                    "fields": "name,location,tel,categories,hours"},
            timeout=TIMEOUT,
        )
        r.raise_for_status()
        results = r.json().get("results") or []
        if not results:
            return _empty()
        place = results[0]
    except requests.RequestException:
        return _empty()

    location = place.get("location") or {}
    hours_obj = place.get("hours") or {}
    categories = place.get("categories") or []

    return {
        "name": place.get("name"),
        "address": location.get("formatted_address"),
        "phone": place.get("tel"),
        "hours": hours_obj.get("display"),
        "category": categories[0]["name"] if categories else None,
        "found": True,
    }


_PHONE_DIGITS_RE = re.compile(r"\D+")
_WS_RE = re.compile(r"\s+")


def _norm_phone(value):
    digits = _PHONE_DIGITS_RE.sub("", value or "")
    return digits[-10:] if len(digits) >= 10 else (digits or None)


def _norm_text(value):
    if not value:
        return None
    return _WS_RE.sub(" ", value).strip().lower().rstrip(".,")


_NORMALIZERS = {"phone": _norm_phone, "address": _norm_text, "name": _norm_text,
                "category": _norm_text, "hours": _norm_text}


def compare_nap(sources):
    """sources: {source_name: {...}}, only entries with found=True are used.

    Returns {"sources_used": [...], "disagreements": [...] or None,
    "note": str or None}. disagreements is None (not an empty list) when
    fewer than 2 sources are usable -- that's a "can't compare yet" state,
    not a fake clean result.

    Each disagreement has severity "inconsistent" (values conflict -- worse,
    per SPEC-8) or "missing" (some sources have the field, at least one
    usable source doesn't, but no conflict among the ones that do).
    """
    usable = {name: data for name, data in (sources or {}).items() if data and data.get("found")}
    if len(usable) < 2:
        return {"sources_used": list(usable), "disagreements": None,
                "note": "not enough sources configured to compare"}

    disagreements = []
    for field, normalize in _NORMALIZERS.items():
        per_source = {name: data.get(field) for name, data in usable.items()}
        present = {name: v for name, v in per_source.items() if v}
        missing_from = [name for name, v in per_source.items() if not v]

        distinct_normalized = {normalize(v) for v in present.values()}
        if len(distinct_normalized) > 1:
            disagreements.append({"field": field, "severity": "inconsistent", "values": present})
        elif missing_from and present:
            disagreements.append({"field": field, "severity": "missing", "values": present,
                                   "missing_from": missing_from})

    return {"sources_used": list(usable), "disagreements": disagreements, "note": None}

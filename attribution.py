"""Heuristic v1 of "where they got it" — AUDIT-REPORT.html's citation-source
attribution ("Your Google Business Profile — cited in eleven answers", etc).

Real attribution needs the engine's own citation metadata (which URL it
actually read) — none of aiquery.py's four _query_* functions return that
yet, same gap noted in aiquery._cited's docstring. Without it, this can only
ask a narrower, answerable question: does a fact asserted in the AI's answer
MATCH what's on record at each known source? A phone-number match is
suggestive of where the fact came from, not proof the model read that page.
Treat every attribution here as "consistent with", not "confirmed from".

v1 checks phone numbers only (the one fact that's cheaply comparable across
Google/Foursquare/the business's own site with an exact, low-false-positive
match). Address/hours/service-description matching would need fuzzier text
comparison — flagged as a follow-up, not built here to avoid a heuristic
that reports high confidence it doesn't have.
"""
import requests

from checks import BROWSER_UA, TIMEOUT, _PHONE_RE
from listings import _norm_phone


def fetch_website_facts(website):
    """The one fact this v1 needs from the business's own site: its phone
    number, if a plain-request fetch finds one."""
    base = website if website.startswith("http") else f"https://{website}"
    try:
        r = requests.get(base, timeout=TIMEOUT, headers={"User-Agent": BROWSER_UA})
    except requests.RequestException:
        return {"phone": None, "fetched": False}
    m = _PHONE_RE.search(r.text)
    return {"phone": _norm_phone(m.group()) if m else None, "fetched": True}


def attribute_answer(quote, listing_sources, website_facts):
    """quote: one AI answer's quoted sentence. listing_sources: the same
    {"Google": {...}, "Foursquare": {...}, ...} dict audit.py already builds
    for the NAP check. website_facts: fetch_website_facts()'s output.

    Returns the source name whose phone number matches a phone number found
    in the quote, "unknown" if a phone was asserted but matches nothing on
    record, or None if the quote doesn't assert a phone number at all (there
    is nothing to attribute).
    """
    m = _PHONE_RE.search(quote or "")
    if not m:
        return None
    quote_phone = _norm_phone(m.group())
    if website_facts.get("phone") == quote_phone:
        return "website"
    for name, data in (listing_sources or {}).items():
        if data and data.get("found") and _norm_phone(data.get("phone")) == quote_phone:
            return name
    return "unknown"


def attribute_all(aiquery_results, listing_sources, website_facts):
    """Rolls up attribute_answer() over every mentioning answer that quotes a
    phone number. Returns {source_name_or_"unknown": count}; answers with no
    phone number asserted are excluded (nothing to attribute), not counted
    as "unknown"."""
    counts = {}
    for r in aiquery_results or []:
        if not r.get("mentioned") or not r.get("quote"):
            continue
        source = attribute_answer(r["quote"], listing_sources, website_facts)
        if source:
            counts[source] = counts.get(source, 0) + 1
    return counts


def demo():
    website_facts = {"phone": "7195551234", "fetched": True}
    listing_sources = {"Google": {"found": True, "phone": "(719) 555-9999"},
                        "Foursquare": {"found": False, "phone": None}}
    assert attribute_answer("Call them at 719-555-1234 today.", listing_sources, website_facts) == "website"
    assert attribute_answer("Call (719) 555-9999.", listing_sources, website_facts) == "Google"
    assert attribute_answer("Call 719-555-0000.", listing_sources, website_facts) == "unknown"
    assert attribute_answer("No phone mentioned here.", listing_sources, website_facts) is None
    print("ok")


if __name__ == "__main__":
    demo()

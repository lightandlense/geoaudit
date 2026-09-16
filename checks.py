"""Crawler access, schema, machine-view, and Bing indexation checks. Each fails soft."""
import json
import re
import requests
from bs4 import BeautifulSoup
from urllib.parse import urlparse

TIMEOUT = 10
BROWSER_UA = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/124.0 Safari/537.36"
)
AI_BOTS = ["GPTBot", "OAI-SearchBot", "PerplexityBot", "ClaudeBot", "Google-Extended", "Bingbot", "*"]
CHALLENGE_MARKERS = ["just a moment", "cf-browser-verification", "checking your browser"]

_ADDRESS_RE = re.compile(
    r"\d{1,6}\s+[\w.\s]{0,30}\b(street|st|avenue|ave|road|rd|drive|dr|lane|ln|"
    r"blvd|boulevard|way|court|ct|circle|cir|place|pl)\b",
    re.IGNORECASE,
)
_PHONE_RE = re.compile(r"\(?\d{3}\)?[\s.\-]?\d{3}[\s.\-]?\d{4}")
_DAY_RE = re.compile(r"\b(mon|tue|wed|thu|fri|sat|sun)(day)?\b", re.IGNORECASE)
_TIME_RE = re.compile(r"\b\d{1,2}(:\d{2})?\s*(am|pm)\b", re.IGNORECASE)


def _domain(url):
    return urlparse(url if "//" in url else f"//{url}").netloc or url


def check_crawler_access(website):
    domain = _domain(website)
    base = website if website.startswith("http") else f"https://{website}"

    blocked = []
    try:
        r = requests.get(f"{base}/robots.txt", timeout=TIMEOUT, headers={"User-Agent": BROWSER_UA})
        if r.status_code == 200:
            current_agents = []
            for line in r.text.splitlines():
                line = line.strip()
                if not line or line.startswith("#"):
                    continue
                if ":" not in line:
                    continue
                key, _, value = line.partition(":")
                key, value = key.strip().lower(), value.strip()
                if key == "user-agent":
                    current_agents = [value]
                elif key == "disallow" and value == "/":
                    for agent in current_agents:
                        if agent in AI_BOTS:
                            blocked.append(agent)
    except requests.RequestException:
        return {"passed": None, "finding": "could not verify robots.txt"}

    try:
        home = requests.get(base, timeout=TIMEOUT, headers={"User-Agent": BROWSER_UA})
        text_lower = home.text.lower()
        if home.status_code >= 400:
            return {"passed": False, "finding": f"homepage returned HTTP {home.status_code}"}
        if any(marker in text_lower for marker in CHALLENGE_MARKERS):
            return {"passed": False, "finding": "homepage serves a bot-challenge page (blocks AI crawlers too)"}
    except requests.RequestException:
        return {"passed": None, "finding": "could not verify homepage access"}

    if blocked:
        return {"passed": False, "finding": f"robots.txt blocks: {', '.join(sorted(set(blocked)))}"}
    return {"passed": True, "finding": "crawlers can access the site"}


def check_schema(website):
    base = website if website.startswith("http") else f"https://{website}"
    try:
        r = requests.get(base, timeout=TIMEOUT, headers={"User-Agent": BROWSER_UA})
    except requests.RequestException:
        return {"passed": None, "finding": "could not verify schema"}

    soup = BeautifulSoup(r.text, "html.parser")
    blocks = soup.find_all("script", type="application/ld+json")
    if not blocks:
        return {"passed": False, "finding": "no structured data (JSON-LD) found on homepage"}

    for block in blocks:
        try:
            data = json.loads(block.string or "")
        except (json.JSONDecodeError, TypeError):
            continue
        items = data if isinstance(data, list) else [data]
        for item in items:
            if not isinstance(item, dict):
                continue
            types = item.get("@type")
            types = types if isinstance(types, list) else [types]
            if any(t in ("LocalBusiness", "Organization") or (t and "Business" in str(t)) for t in types):
                has_name = bool(item.get("name"))
                has_phone = bool(item.get("telephone"))
                if has_name and has_phone:
                    return {"passed": True, "finding": "LocalBusiness/Organization schema with name and phone present"}
                return {"passed": False, "finding": "LocalBusiness schema present but missing name or phone"}

    return {"passed": False, "finding": "JSON-LD present but no LocalBusiness/Organization schema found"}


def check_machine_view(website, business=None):
    """SPEC-8 check 2 ("what a machine sees"): fetch the page as a plain
    request (no scripts run) and check whether business name, address,
    phone and hours are present as readable text in that raw response.

    Deliberately does NOT render the page in a browser to compare against
    what a human with JS enabled sees -- that needs Playwright/Selenium, a
    new dependency requiring sign-off first. This only answers the
    actionable half of the spec: if a crawler-visible plain-request fetch
    doesn't contain these fields, no AI retrieval agent sees them either,
    regardless of what a JS-enabled human visitor would see.
    """
    base = website if website.startswith("http") else f"https://{website}"
    try:
        r = requests.get(base, timeout=TIMEOUT, headers={"User-Agent": BROWSER_UA})
    except requests.RequestException:
        return {"passed": None, "finding": "could not verify machine view", "present": [], "missing": []}

    text = r.text
    found = {
        "address": bool(_ADDRESS_RE.search(text)),
        "phone": bool(_PHONE_RE.search(text)),
        "hours": bool(_DAY_RE.search(text) and _TIME_RE.search(text)),
    }
    if business:
        found = {"business name": business.lower() in text.lower(), **found}

    present = [k for k, v in found.items() if v]
    missing = [k for k, v in found.items() if not v]
    passed = not missing
    finding = "all present in the raw HTML" if passed else f"missing from raw HTML: {', '.join(missing)}"
    return {"passed": passed, "finding": finding, "present": present, "missing": missing}


def check_bing_index(website):
    domain = _domain(website)
    try:
        r = requests.get(
            "https://www.bing.com/search",
            params={"q": f"site:{domain}"},
            timeout=TIMEOUT,
            headers={"User-Agent": BROWSER_UA},
        )
    except requests.RequestException:
        return {"passed": None, "finding": "could not verify Bing indexation"}

    text_lower = r.text.lower()
    if r.status_code != 200 or "did not match any documents" in text_lower:
        return {"passed": False, "finding": f"{domain} not indexed on Bing (or zero results)"}

    soup = BeautifulSoup(r.text, "html.parser")
    if soup.find("li", class_="b_algo"):
        return {"passed": True, "finding": f"{domain} is indexed on Bing"}
    return {"passed": None, "finding": "could not verify Bing indexation"}


def check_sitemap(website):
    base = website if website.startswith("http") else f"https://{website}"
    try:
        r = requests.get(f"{base}/sitemap.xml", timeout=TIMEOUT, headers={"User-Agent": BROWSER_UA})
    except requests.RequestException:
        return {"passed": None, "finding": "could not verify sitemap"}
    if r.status_code == 200 and "<urlset" in r.text[:2000].lower():
        return {"passed": True, "finding": "sitemap.xml found"}
    return {"passed": False, "finding": "no sitemap.xml at the standard location"}


_VAGUE_WORDS = ["transformative", "exceptional", "premium", "amazing", "outstanding",
                "best-in-class", "world-class", "unparalleled", "cutting-edge"]
_TRUST_WORDS = ["award", "certified", "licensed", "insured", "featured in", "as seen in",
                "years of experience", "review"]

# OD-1 (geo-agency build-specs.md, resolved 2026-08-23): clarity/summarization 25%,
# E-E-A-T 23%, Q&A format 19%, section structure 17%, structured data 16%.
OD1_WEIGHTS = {"clarity": 25, "eeat": 23, "qa_format": 19, "structure": 17, "structured_data": 16}


def check_content_grade(website, business=None):
    """Heuristic v1 of OD-1's 5-factor content-quality grade — the "what a
    machine can lift off your pages" check (ten-checks list, OPEN-ME.html).
    OD-1 says each factor is scored 0-100 and shown individually for
    diagnosis, plus one composite computed as the weighted average — never
    collapse straight to one number, per its own wording.

    Every sub-score here is a cheap single-page proxy (homepage only — a real
    per-service-page version needs a page list this pipeline doesn't have
    yet), not the real methodology OD-1 describes. OD-1 itself says the
    weights are v1 and should be recalibrated against which factors actually
    predict AI citations once real outcome data exists — same caveat applies
    doubly to these proxy measurements underneath them.
    """
    base = website if website.startswith("http") else f"https://{website}"
    try:
        r = requests.get(base, timeout=TIMEOUT, headers={"User-Agent": BROWSER_UA})
    except requests.RequestException:
        return {"passed": None, "finding": "could not verify content grade", "factors": {},
                "weights": OD1_WEIGHTS, "composite": None}

    soup = BeautifulSoup(r.text, "html.parser")
    text = soup.get_text(" ", strip=True)
    text_lower = text.lower()
    headings = [h.get_text(" ", strip=True) for h in soup.find_all(["h1", "h2", "h3"])]

    # Clarity/summarization: concrete specifics (digits) vs. vague marketing
    # adjectives. No signal either way (no digits, no vague words) scores 0 —
    # this proxy can only reward a positive signal, not "nothing to judge".
    vague_count = sum(text_lower.count(w) for w in _VAGUE_WORDS)
    digit_count = sum(c.isdigit() for c in text)
    clarity = round(100 * digit_count / (digit_count + vague_count * 3 + 1))

    # E-E-A-T: contact info present (phone/address — same regexes as the
    # machine-view check), a trust/authority word, and https.
    has_contact = bool(_PHONE_RE.search(text) or _ADDRESS_RE.search(text))
    has_trust_word = any(w in text_lower for w in _TRUST_WORDS)
    has_https = r.url.startswith("https://")
    eeat = round(100 * sum([has_contact, has_trust_word, has_https]) / 3)

    # Q&A format: a heading phrased as a question, and an FAQ block (schema or visible).
    has_question_heading = any("?" in h for h in headings)
    has_faq = "faqpage" in r.text.lower() or any("faq" in h.lower() or "frequently asked" in h.lower() for h in headings)
    qa_format = round(100 * sum([has_question_heading, has_faq]) / 2)

    # Section structure: exactly one h1, and at least two h2/h3 subheadings.
    h1_count = len(soup.find_all("h1"))
    subheading_count = len(soup.find_all(["h2", "h3"]))
    structure = round(100 * sum([h1_count == 1, subheading_count >= 2]) / 2)

    # Structured data: any JSON-LD present, and whether it's a business-shaped type.
    ld_blocks = soup.find_all("script", type="application/ld+json")
    has_business_type = any(t in r.text for t in ('"LocalBusiness"', '"Organization"')) if ld_blocks else False
    structured_data = 100 if has_business_type else (50 if ld_blocks else 0)

    factors = {"clarity": clarity, "eeat": eeat, "qa_format": qa_format,
               "structure": structure, "structured_data": structured_data}
    composite = round(sum(factors[k] * OD1_WEIGHTS[k] for k in OD1_WEIGHTS) / 100)
    passed = composite >= 60
    finding = f"content grade {composite}/100" + ("" if passed else " — weak on: " +
               ", ".join(k for k, v in factors.items() if v < 60))
    return {"passed": passed, "finding": finding, "factors": factors,
            "weights": OD1_WEIGHTS, "composite": composite}


_PLACE_RE = re.compile(r"\b[A-Za-z][a-z]+,\s*[A-Z]{2}\b")  # "Denver, CO" shaped


def check_business_confusion(aiquery_results, business, city):
    """Heuristic v1 of detection layer 3 (OPEN-ME.html: "the one that solves
    the real problem: Fernwood Aesthetics in Monument being confused with
    Fernwood Wellness in Denver"). The real design wants a per-client
    conflation blocklist seeded at onboarding and grown from a model's
    layer-4 decisions — that's Stage 2 (beta/database) work, not a single
    function. This v1 only catches the cheapest case: a mentioning answer
    that names a "City, ST" that isn't this business's own city. Flags for
    human review, never auto-corrects.
    """
    flagged = []
    for r in aiquery_results:
        if not r.get("mentioned") or not r.get("quote"):
            continue
        other_places = [p for p in _PLACE_RE.findall(r["quote"]) if city.lower() not in p.lower()]
        if other_places:
            flagged.append({"prompt_label": r["prompt_label"], "quote": r["quote"], "places": other_places})
    return {"flagged": flagged, "finding": "no confusion detected" if not flagged else
            f"{len(flagged)} answer(s) may confuse this business with one elsewhere"}


def run_all(website, business=None):
    return {
        "crawler": check_crawler_access(website),
        "schema": check_schema(website),
        "machine_view": check_machine_view(website, business=business),
        "bing": check_bing_index(website),
        "sitemap": check_sitemap(website),
        "content_grade": check_content_grade(website, business=business),
    }

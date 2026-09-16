#!/usr/bin/env python
"""Prospect scanner: find businesses that DESERVE AI citations but don't get them.

Supply side (Google Places) = who's good enough to be recommended.
Demand side (ChatGPT/Perplexity/Gemini) = who the engines actually name.
Gap = passed-the-rubric businesses the engines never mention. Those are the leads.

Usage:
  python scan.py --vertical roofing --city "Colorado Springs, CO"
  python scan.py --vertical "dentist" --city "Boise, ID" --min-reviews 40 --json

Self-check (no API keys needed):  python scan.py --selftest
"""
import argparse
import csv
import json
import re
import sys
from datetime import date
from pathlib import Path

SCANS_DIR = Path(__file__).parent / "scans"

# Buyer prompts that surface a SET of businesses (vetting is excluded — it needs a
# named business). Kept here rather than in prompts.toml because discovery has no
# {business} to fill.
DISCOVERY_PROMPTS = [
    ("Recommendation", "Who is the most reliable {vertical} in {city}? Name specific companies."),
    ("Emergency", "I need a {vertical} near me in {city} right now. Who should I call? Name companies."),
    ("Comparison", "What are the best {vertical} companies in {city}? Compare a few by name."),
    ("Problem-first", "I have a problem that needs a {vertical} in {city}. Which local companies can help?"),
]

# Legal / generic suffixes stripped from BOTH the candidate name and the answer
# text before substring matching, so "Peak Roofing Co" matches "Peak Roofing".
_SUFFIXES = r"\b(llc|inc|incorporated|co|company|corp|corporation|ltd|pllc|pc|group|the)\b"


def normalize(text):
    text = text.lower()
    text = re.sub(r"[^a-z0-9\s]", " ", text)
    text = re.sub(_SUFFIXES, " ", text)
    return re.sub(r"\s+", " ", text).strip()


def is_mentioned(candidate_name, answer_text):
    """True if the candidate's normalized name appears in the answer.

    ponytail: substring match on normalized names. Ceiling — misses model
    abbreviations/misspellings and can false-match a very short 1-word name.
    Upgrade path: fuzzy match (rapidfuzz) if false rates matter in practice.
    """
    cand = normalize(candidate_name)
    if len(cand) < 4:  # too short to match safely (e.g. "A1")
        return False
    return cand in normalize(answer_text)


def compute_gap(candidates, answers):
    """answers: list of answer-text strings. Annotates each candidate with
    engines_naming (count of answers that mention it) and returns candidates
    sorted invisible-first, then by review count."""
    scored = []
    for c in candidates:
        hits = sum(1 for a in answers if a and is_mentioned(c["name"], a))
        scored.append({**c, "engines_naming": hits})
    scored.sort(key=lambda c: (c["engines_naming"], -c["review_count"]))
    return scored


def _gather_answers(vertical, city, on_progress=None):
    """Run every discovery prompt across every engine. Returns list of answer
    strings (failed calls are dropped, not fatal)."""
    import aiquery  # reuse the existing provider clients
    answers = []
    for label, template in DISCOVERY_PROMPTS:
        text = template.format(vertical=vertical, city=city)
        for engine_name, engine_fn in aiquery.ENGINES.items():
            if on_progress:
                on_progress(engine_name, label)
            try:
                answers.append(engine_fn(text))
            except Exception:
                pass  # one dead engine shouldn't sink the scan
    return answers


def _write_outputs(rows, vertical, city, want_json):
    SCANS_DIR.mkdir(exist_ok=True)
    slug = re.sub(r"[^a-z0-9]+", "-", f"{vertical}-{city}".lower()).strip("-")
    base = SCANS_DIR / f"{slug}-{date.today().isoformat()}"
    with open(base.with_suffix(".csv"), "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=["name", "rating", "review_count",
                                          "engines_naming", "address", "place_id"])
        w.writeheader()
        for r in rows:
            w.writerow({k: r[k] for k in w.fieldnames})
    if want_json:
        base.with_suffix(".json").write_text(json.dumps(rows, indent=2))
    return base.with_suffix(".csv")


def run(vertical, city, min_rating, min_reviews, max_results, want_json):
    import discover
    print(f"Discovering {vertical} in {city} (Google Places)...")
    candidates = discover.discover_candidates(
        vertical, city, min_rating, min_reviews, max_results)
    print(f"  {len(candidates)} businesses pass the rubric (>= {min_rating}star, >= {min_reviews} reviews)")
    if not candidates:
        print("Nothing to scan. Loosen --min-reviews or check the vertical/city spelling.")
        return

    n_calls = len(DISCOVERY_PROMPTS) * 3
    print(f"Querying AI engines ({n_calls} calls, the slow part)...")
    answers = _gather_answers(
        vertical, city, on_progress=lambda e, l: print(f"  {e}: {l}"))
    print(f"  {len(answers)}/{n_calls} answers returned")

    rows = compute_gap(candidates, answers)
    invisible = [r for r in rows if r["engines_naming"] == 0]

    print(f"\n=== GAP LIST: {len(invisible)} deserving-but-invisible prospects ===")
    print(f"{'Reviews':>7}  {'Rating':>6}  {'AI cites':>8}  Name")
    for r in rows[:25]:
        print(f"{r['review_count']:>7}  {r['rating']:>6}  {r['engines_naming']:>8}  {r['name']}")

    out = _write_outputs(rows, vertical, city, want_json)
    print(f"\nSaved: {out}")


def _selftest():
    assert normalize("Peak Roofing Co., LLC") == "peak roofing"
    assert is_mentioned("Peak Roofing Co", "I'd call Peak Roofing, they're great")
    assert not is_mentioned("Summit Plumbing", "Try Peak Roofing or Ace HVAC")
    assert not is_mentioned("A1", "some long answer text here")  # too-short guard
    cands = [
        {"name": "Peak Roofing", "rating": 4.8, "review_count": 200, "place_id": "p", "address": ""},
        {"name": "Summit Roofing", "rating": 4.5, "review_count": 90, "place_id": "s", "address": ""},
    ]
    answers = ["The best is Summit Roofing in town."]
    gap = compute_gap(cands, answers)
    assert gap[0]["name"] == "Peak Roofing" and gap[0]["engines_naming"] == 0  # invisible first
    assert gap[1]["name"] == "Summit Roofing" and gap[1]["engines_naming"] == 1
    print("selftest OK")


def main():
    p = argparse.ArgumentParser(description="Find deserving-but-AI-invisible local businesses.")
    p.add_argument("--vertical", help="e.g. roofing, dentist, HVAC")
    p.add_argument("--city", help='e.g. "Colorado Springs, CO"')
    p.add_argument("--min-rating", type=float, default=4.0)
    p.add_argument("--min-reviews", type=int, default=25)
    p.add_argument("--max-results", type=int, default=60)
    p.add_argument("--json", action="store_true", help="also write raw rows as JSON")
    p.add_argument("--selftest", action="store_true", help="run logic self-check, no API keys needed")
    args = p.parse_args()

    if args.selftest:
        _selftest()
        return
    if not args.vertical or not args.city:
        p.error("--vertical and --city are required (or use --selftest)")

    from dotenv import load_dotenv
    load_dotenv()
    run(args.vertical, args.city, args.min_rating, args.min_reviews,
        args.max_results, args.json)


if __name__ == "__main__":
    main()

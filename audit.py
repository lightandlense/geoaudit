#!/usr/bin/env python
"""CLI entry point. python audit.py "<business>" "<city>" [--website URL] [--industry X] [--json]"""
import argparse
import json
import os
import re
import sys
from datetime import date
from pathlib import Path

from dotenv import load_dotenv

import resolve
import checks
import aiquery
import listings
import scoring
import attribution
import report
import report_html

# SPEC-3's search/local/brand channels are 0-3 human judgment calls in the
# source tool (SCORE-BUILDER.html), not automated — see scoring.py's
# docstring. These CLI flags take the same 0-3 scale; omit any of them and
# that channel is reported as "not scored" rather than guessed.
_MANUAL_FLAGS = {
    "position": "Google ranking: 0=top three, 1=4-10, 2=page two, 3=not in first three pages",
    "indexed": "Google indexing: 0=all indexed, 1=some missing, 2=most missing, 3=nothing indexed",
    "bing": "Bing: 0=listed+ranking, 1=listed not ranking, 2=listed but stale, 3=not on Bing",
    "pack": "Map pack: 0=consistently, 1=sometimes, 2=only by name, 3=no",
    "gbp": "Google Business Profile completeness: 0=complete .. 3=barely filled in",
    "apple": "Apple Maps: 0=correct .. 3=not on Apple Maps at all",
    "nap": "Directory NAP agreement (6+ checked): 0=all agree .. 3=several disagree",
    "acc": "Accuracy when asked by name: 0=accurate .. 3=confuses with another business",
}

AUDITS_DIR = Path(__file__).parent / "audits"


def _slug(text):
    text = re.sub(r"[^a-z0-9]+", "-", text.lower()).strip("-")
    return text or "business"


def main():
    load_dotenv()
    parser = argparse.ArgumentParser(description="Generate a GEO visibility audit PDF for a business.")
    parser.add_argument("business")
    parser.add_argument("city")
    parser.add_argument("--website", default=None)
    parser.add_argument("--industry", default=None)
    parser.add_argument("--json", action="store_true", help="also write the raw findings dict as JSON")
    parser.add_argument("--engines", default=None,
                         help="comma-separated subset of ChatGPT,Perplexity,Gemini,Claude "
                              "(default: all four)")
    parser.add_argument("--competitors", default=None,
                         help="comma-separated competitor names to score the same way (SPEC-8 check 5)")
    parser.add_argument("--samples", type=int, default=1,
                         help="repeats per (prompt, engine) pair. Default 1, matching SPEC-8's "
                              "23x4x1=92 math -- AUDIT-REPORT.html's footer says 3, that's still open")
    for flag, help_text in _MANUAL_FLAGS.items():
        parser.add_argument(f"--{flag}", type=int, choices=[0, 1, 2, 3], default=None, help=help_text)
    args = parser.parse_args()

    competitors = [c.strip() for c in args.competitors.split(",")] if args.competitors else []

    engines = None
    if args.engines:
        names = [n.strip() for n in args.engines.split(",")]
        unknown = [n for n in names if n not in aiquery.ENGINES]
        if unknown:
            print(f"Error: unknown engine(s) {unknown}, choose from {list(aiquery.ENGINES)}", file=sys.stderr)
            sys.exit(1)
        engines = {n: aiquery.ENGINES[n] for n in names}

    try:
        resolved = resolve.resolve_business(args.business, args.city, args.website, args.industry)
    except ValueError as e:
        print(f"Error: {e}", file=sys.stderr)
        sys.exit(1)

    print(f"Resolved: {resolved['website']} (verdict: {resolved['verdict']})")

    print("Running technical checks...")
    check_results = checks.run_all(resolved["website"], business=args.business)

    n_engines = len(engines) if engines else len(aiquery.ENGINES)
    print(f"Querying AI engines ({n_engines * 23 * args.samples} calls, this is the slow part)...")

    def progress(engine, label):
        print(f"  {engine}: {label}")

    ai_results = aiquery.run_all(args.business, args.city, resolved["industry"],
                                  on_progress=progress, engines=engines, competitors=competitors,
                                  samples=args.samples)

    print("Checking listing consistency (Google/Yelp/Foursquare)...")
    listing_sources = {
        "Google": listings.fetch_google(args.business, args.city, os.environ.get("GOOGLE_PLACES_API_KEY")),
        "Yelp": listings.fetch_yelp(args.business, args.city, os.environ.get("YELP_API_KEY")),
        "Foursquare": listings.fetch_foursquare(args.business, args.city, os.environ.get("FOURSQUARE_API_KEY")),
    }
    listings_data = {
        "sources": listing_sources,
        "comparison": listings.compare_nap(listing_sources),
    }

    confusion = checks.check_business_confusion(ai_results, args.business, args.city)

    website_facts = attribution.fetch_website_facts(resolved["website"])
    attribution_counts = attribution.attribute_all(ai_results, listing_sources, website_facts)

    rates = aiquery.business_rates(ai_results)
    ai_score = scoring.ai_risk(rates["mention_rate"], rates["cite_rate"], rates["platform_rate"])
    google_score = scoring.google_risk(args.position, args.indexed, args.bing)
    local_score = scoring.local_risk(args.pack, args.gbp, args.apple, args.nap)
    brand_score = scoring.brand_risk(args.acc)
    score = {
        "ai": ai_score, "google": google_score, "local": local_score, "brand": brand_score,
        "composite": scoring.composite(ai_score, google_score, local_score, brand_score),
        "weights": scoring.CHANNEL_WEIGHTS,
        "rates": rates,
    }

    data = {
        "business": args.business,
        "city": args.city,
        "date": date.today().isoformat(),
        "resolve": resolved,
        "checks": check_results,
        "confusion": confusion,
        "attribution": attribution_counts,
        "aiquery": ai_results,
        "competitor_scores": aiquery.score_competitors(ai_results, competitors),
        "listings": listings_data,
        "score": score,
    }

    AUDITS_DIR.mkdir(exist_ok=True)
    slug = _slug(args.business)
    pdf_path = AUDITS_DIR / f"{slug}-{data['date']}.pdf"
    report.generate_report(data, str(pdf_path))

    html_path = AUDITS_DIR / f"{slug}-{data['date']}.html"
    report_html.generate_html_report(data, str(html_path))

    if args.json:
        json_path = pdf_path.with_suffix(".json")
        json_path.write_text(json.dumps(data, indent=2))

    print(str(pdf_path))
    print(str(html_path))
    sys.exit(0)


if __name__ == "__main__":
    main()

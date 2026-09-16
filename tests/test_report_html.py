import os
import sys
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

import report_html


def _tmp_path(tmp_path):
    return str(tmp_path / "report.html")


def test_generate_html_report_full_data(tmp_path):
    data = {
        "business": "Light & Lense",
        "city": "Colorado Springs",
        "date": "2026-09-16",
        "resolve": {
            "website": "lightandlense.com",
            "rating": None,
            "review_count": None,
            "newest_review_days": None,
            "verdict": "OPEN FIELD",
            "profile_found": False,
        },
        "checks": {
            "crawler": {"passed": True, "finding": "crawlers can access the site"},
            "schema": {"passed": False, "finding": "no structured data (JSON-LD) found on homepage"},
            "bing": {"passed": None, "finding": "could not verify Bing indexation"},
        },
        "aiquery": [
            {"engine": "Claude", "prompt_label": "Vetting", "mentioned": True,
             "quote": "Light & Lense is a well-regarded light painting photographer.",
             "error": None, "competitors_mentioned": []},
            {"engine": "Claude", "prompt_label": "Recommendation", "mentioned": False,
             "quote": "Jerry Siroky is a popular choice.", "error": None,
             "competitors_mentioned": ["Jerry Siroky"]},
        ],
        "competitor_scores": {
            "Jerry Siroky": {"mentioned": 1, "total": 2},
            "Mandy Penn Photography": {"mentioned": 0, "total": 2},
        },
    }
    out = report_html.generate_html_report(data, _tmp_path(tmp_path))
    html = open(out, encoding="utf-8").read()
    assert "<!doctype html>" in html.lower()
    assert "Light &amp; Lense" in html
    assert "Jerry Siroky" in html
    assert "50%" in html  # 1/2 mention rate for the competitor
    assert "Pending" not in html or "not scored yet" not in html  # sanity: real data path used somewhere


def test_generate_html_report_all_pending(tmp_path):
    """No checks, no aiquery, no competitors yet -- must not crash, must render pending states."""
    data = {
        "business": "New Client",
        "city": "Denver",
        "date": "2026-09-16",
        "resolve": {"website": "newclient.com", "rating": None, "review_count": None,
                    "newest_review_days": None, "verdict": "OPEN FIELD", "profile_found": False},
        "checks": None,
        "aiquery": None,
        "competitor_scores": {},
    }
    out = report_html.generate_html_report(data, _tmp_path(tmp_path))
    html = open(out, encoding="utf-8").read()
    assert "<!doctype html>" in html.lower()
    assert "Pending" in html
    assert "No competitors supplied" in html


def test_generate_html_report_with_score_and_confusion(tmp_path):
    data = {
        "business": "Light & Lense",
        "city": "Colorado Springs",
        "date": "2026-09-16",
        "resolve": {"website": "lightandlense.com", "rating": 5, "review_count": 1,
                    "newest_review_days": 2403, "verdict": "GOOD FIT", "profile_found": True},
        "checks": {
            "crawler": {"passed": True, "finding": "crawlers can access the site"},
            "schema": {"passed": False, "finding": "no structured data found"},
            "content_grade": {"passed": False, "finding": "content grade 42/100 — weak on: qa_format",
                               "factors": {"clarity": 60, "eeat": 33, "qa_format": 0,
                                           "structure": 50, "structured_data": 50},
                               "weights": {"clarity": 25, "eeat": 23, "qa_format": 19,
                                           "structure": 17, "structured_data": 16},
                               "composite": 42},
            "sitemap": {"passed": True, "finding": "sitemap.xml found"},
        },
        "aiquery": [{"engine": "Claude", "prompt_label": "Vetting", "mentioned": True,
                     "quote": "Light & Lense is actually based in Denver, CO.",
                     "error": None, "competitors_mentioned": []}],
        "competitor_scores": {},
        "confusion": {"flagged": [{"prompt_label": "Vetting", "quote": "Light & Lense is actually based in Denver, CO.",
                                    "places": ["Denver, CO"]}],
                      "finding": "1 answer(s) may confuse this business with one elsewhere"},
        "score": {
            "ai": 44.0, "google": None, "local": None, "brand": None,
            "composite": 44.0, "weights": {"ai": 40, "google": 25, "local": 25, "brand": 10},
            "rates": {"mention_rate": 0.61, "cite_rate": 0.1, "platform_rate": 1.0},
        },
    }
    out = report_html.generate_html_report(data, _tmp_path(tmp_path))
    html = open(out, encoding="utf-8").read()
    assert "44" in html
    assert "Denver, CO" in html
    assert "SPEC-3" in html
    assert "Apple Maps" in html


if __name__ == "__main__":
    import pytest
    raise SystemExit(pytest.main([__file__, "-q"]))

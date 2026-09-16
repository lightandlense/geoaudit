import os
import sys
import tempfile
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

import report


def _fake_data():
    engines = ["ChatGPT", "Perplexity", "Gemini"]
    labels = ["Recommendation", "Emergency / near-me", "Comparison", "Vetting", "Problem-first"]
    aiquery = []
    for label in labels:
        for engine in engines:
            aiquery.append({
                "engine": engine, "prompt_label": label,
                "mentioned": False, "quote": "Try Summit Roofing, they are well reviewed.",
                "error": None,
            })
    return {
        "business": "Peak Roofing", "city": "Colorado Springs", "date": "2026-07-17",
        "resolve": {
            "website": "https://peakroofing.com", "rating": 4.6, "review_count": 42,
            "newest_review_days": 12, "verdict": "GREEN", "industry": "roofing contractor",
            "profile_found": True,
        },
        "checks": {
            "crawler": {"passed": True, "finding": "crawlers can access the site"},
            "schema": {"passed": False, "finding": "no structured data found"},
            "bing": {"passed": None, "finding": "could not verify"},
        },
        "aiquery": aiquery,
    }


def test_generate_report_smoke():
    data = _fake_data()
    with tempfile.TemporaryDirectory() as tmp:
        out = os.path.join(tmp, "test.pdf")
        result = report.generate_report(data, out)
        assert result == out
        assert os.path.exists(out)
        assert os.path.getsize(out) > 500


if __name__ == "__main__":
    import pytest
    raise SystemExit(pytest.main([__file__, "-q"]))

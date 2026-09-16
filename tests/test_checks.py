import os
import sys
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

import checks

FIXTURES = os.path.join(os.path.dirname(__file__), "fixtures")


def _read(name):
    with open(os.path.join(FIXTURES, name), encoding="utf-8") as f:
        return f.read()


class FakeResponse:
    def __init__(self, text, status_code=200, url="https://example.com"):
        self.text = text
        self.status_code = status_code
        self.url = url

    def json(self):
        return {}


def test_crawler_access_blocked(monkeypatch):
    robots = _read("robots_blocked.txt")

    def fake_get(url, timeout=None, headers=None, params=None):
        if url.endswith("/robots.txt"):
            return FakeResponse(robots)
        return FakeResponse("<html>homepage ok</html>")

    monkeypatch.setattr(checks.requests, "get", fake_get)
    result = checks.check_crawler_access("https://peakroofing.com")
    assert result["passed"] is False
    assert "GPTBot" in result["finding"]


def test_crawler_access_ok(monkeypatch):
    robots = _read("robots_ok.txt")

    def fake_get(url, timeout=None, headers=None, params=None):
        if url.endswith("/robots.txt"):
            return FakeResponse(robots)
        return FakeResponse("<html>homepage ok</html>")

    monkeypatch.setattr(checks.requests, "get", fake_get)
    result = checks.check_crawler_access("https://peakroofing.com")
    assert result["passed"] is True


def test_schema_present(monkeypatch):
    monkeypatch.setattr(checks.requests, "get", lambda *a, **k: FakeResponse(_read("schema_present.html")))
    result = checks.check_schema("https://peakroofing.com")
    assert result["passed"] is True


def test_schema_absent(monkeypatch):
    monkeypatch.setattr(checks.requests, "get", lambda *a, **k: FakeResponse(_read("schema_absent.html")))
    result = checks.check_schema("https://peakroofing.com")
    assert result["passed"] is False


def test_machine_view_all_present(monkeypatch):
    html = ("<html><body>Acme Photography, 123 Main Street, Colorado Springs. "
            "Call us at (719) 555-1234. Hours: Mon-Fri 9am-5pm.</body></html>")
    monkeypatch.setattr(checks.requests, "get", lambda *a, **k: FakeResponse(html))
    result = checks.check_machine_view("https://example.com", business="Acme Photography")
    assert result["passed"] is True
    assert set(result["present"]) == {"business name", "address", "phone", "hours"}
    assert result["missing"] == []


def test_machine_view_some_missing(monkeypatch):
    html = "<html><body>Welcome to our site. Contact us for more info.</body></html>"
    monkeypatch.setattr(checks.requests, "get", lambda *a, **k: FakeResponse(html))
    result = checks.check_machine_view("https://example.com", business="Acme Photography")
    assert result["passed"] is False
    assert "business name" in result["missing"]
    assert "address" in result["missing"]
    assert "phone" in result["missing"]
    assert "hours" in result["missing"]


def test_machine_view_no_business_name_given(monkeypatch):
    html = "<html><body>123 Main Street. Call (719) 555-1234. Open Mon-Fri 9am-5pm.</body></html>"
    monkeypatch.setattr(checks.requests, "get", lambda *a, **k: FakeResponse(html))
    result = checks.check_machine_view("https://example.com")
    assert "business name" not in result["present"] and "business name" not in result["missing"]
    assert result["passed"] is True


def test_machine_view_fetch_fails(monkeypatch):
    def raise_error(*a, **k):
        raise checks.requests.RequestException("timeout")
    monkeypatch.setattr(checks.requests, "get", raise_error)
    result = checks.check_machine_view("https://example.com", business="Acme")
    assert result["passed"] is None
    assert result["present"] == [] and result["missing"] == []


def test_run_all_includes_machine_view(monkeypatch):
    monkeypatch.setattr(checks.requests, "get", lambda *a, **k: FakeResponse("<html></html>"))
    result = checks.run_all("https://example.com", business="Acme")
    assert "machine_view" in result


def test_bing_indexed(monkeypatch):
    monkeypatch.setattr(checks.requests, "get", lambda *a, **k: FakeResponse(_read("bing_indexed.html")))
    result = checks.check_bing_index("peakroofing.com")
    assert result["passed"] is True


def test_bing_not_indexed(monkeypatch):
    monkeypatch.setattr(checks.requests, "get", lambda *a, **k: FakeResponse(_read("bing_empty.html")))
    result = checks.check_bing_index("peakroofing.com")
    assert result["passed"] is False


def test_sitemap_found(monkeypatch):
    monkeypatch.setattr(checks.requests, "get",
                         lambda *a, **k: FakeResponse('<?xml version="1.0"?><urlset></urlset>'))
    assert checks.check_sitemap("example.com")["passed"] is True


def test_sitemap_missing(monkeypatch):
    monkeypatch.setattr(checks.requests, "get", lambda *a, **k: FakeResponse("not found", status_code=404))
    assert checks.check_sitemap("example.com")["passed"] is False


def test_content_grade_weights_sum_to_100():
    assert sum(checks.OD1_WEIGHTS.values()) == 100


def test_content_grade_strong_page(monkeypatch):
    html = ("<html><body><h1>Light Painting Photography</h1>"
            "<h2>How much does it cost?</h2><h3>FAQ</h3>"
            "<p>20 minutes, $12 per unit, lasts 3-4 months. Call (719) 555-1234. "
            "Certified and featured in local press.</p>"
            '<script type="application/ld+json">{"@type":"LocalBusiness","name":"Acme"}</script>'
            "</body></html>")
    monkeypatch.setattr(checks.requests, "get", lambda *a, **k: FakeResponse(html, url="https://example.com/"))
    result = checks.check_content_grade("example.com")
    assert result["passed"] is True
    assert set(result["factors"]) == set(checks.OD1_WEIGHTS)
    assert all(0 <= v <= 100 for v in result["factors"].values())
    assert result["composite"] >= 60


def test_content_grade_weak_vague_page(monkeypatch):
    html = "<html><body><h1>Exceptional Premium Service</h1><p>Transformative, exceptional, premium results.</p></body></html>"
    monkeypatch.setattr(checks.requests, "get", lambda *a, **k: FakeResponse(html))
    result = checks.check_content_grade("example.com")
    assert result["passed"] is False
    assert result["factors"]["qa_format"] == 0
    assert result["factors"]["structured_data"] == 0


def test_content_grade_fetch_fails(monkeypatch):
    def raise_error(*a, **k):
        raise checks.requests.RequestException("timeout")
    monkeypatch.setattr(checks.requests, "get", raise_error)
    result = checks.check_content_grade("example.com")
    assert result["passed"] is None
    assert result["composite"] is None


def test_business_confusion_flags_other_city():
    results = [{"mentioned": True, "prompt_label": "Vetting",
                "quote": "Fernwood Aesthetics is actually based in Denver, CO."}]
    result = checks.check_business_confusion(results, "Fernwood Aesthetics", "Monument")
    assert len(result["flagged"]) == 1


def test_business_confusion_clean_when_own_city_only():
    results = [{"mentioned": True, "prompt_label": "Vetting",
                "quote": "Fernwood Aesthetics is a medical spa in Monument, CO."}]
    result = checks.check_business_confusion(results, "Fernwood Aesthetics", "Monument")
    assert result["flagged"] == []


def test_business_confusion_ignores_unmentioned_results():
    results = [{"mentioned": False, "prompt_label": "x", "quote": "Some other business in Denver, CO."}]
    result = checks.check_business_confusion(results, "Fernwood Aesthetics", "Monument")
    assert result["flagged"] == []


if __name__ == "__main__":
    import pytest
    raise SystemExit(pytest.main([__file__, "-q"]))

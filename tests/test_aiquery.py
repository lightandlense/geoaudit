import os
import sys
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

import aiquery


def _fake_engine(answer):
    return lambda prompt_text: answer


def test_run_all_records_competitors_mentioned():
    engines = {"Fake": _fake_engine("Acme Photography and Beta Studios both do great work.")}
    results = aiquery.run_all(
        "Light & Lense", "Colorado Springs", "photographer",
        engines=engines, competitors=["Acme Photography", "Beta Studios", "Gamma Photos"],
    )
    assert all(r["competitors_mentioned"] == ["Acme Photography", "Beta Studios"] for r in results)


def test_run_all_no_competitors_passed():
    engines = {"Fake": _fake_engine("some answer")}
    results = aiquery.run_all("Light & Lense", "Colorado Springs", "photographer", engines=engines)
    assert all(r["competitors_mentioned"] == [] for r in results)


def test_run_all_error_still_has_empty_competitors_mentioned():
    def boom(prompt_text):
        raise RuntimeError("api down")

    results = aiquery.run_all(
        "Light & Lense", "Colorado Springs", "photographer",
        engines={"Fake": boom}, competitors=["Acme Photography"],
    )
    assert all(r["competitors_mentioned"] == [] and r["error"] for r in results)


def test_score_competitors_rolls_up_same_shape_as_mention_rate():
    results = [
        {"competitors_mentioned": ["Acme Photography"]},
        {"competitors_mentioned": ["Acme Photography", "Beta Studios"]},
        {"competitors_mentioned": []},
    ]
    scores = aiquery.score_competitors(results, ["Acme Photography", "Beta Studios", "Gamma Photos"])
    assert scores == {
        "Acme Photography": {"mentioned": 2, "total": 3},
        "Beta Studios": {"mentioned": 1, "total": 3},
        "Gamma Photos": {"mentioned": 0, "total": 3},
    }


def test_score_competitors_empty_list():
    assert aiquery.score_competitors([{"competitors_mentioned": []}], []) == {}


def test_run_all_default_samples_is_one():
    calls = []
    engines = {"Fake": _fake_engine("some answer")}
    results = aiquery.run_all("Light & Lense", "Colorado Springs", "photographer", engines=engines)
    assert len(results) == len(aiquery.load_prompts("Light & Lense", "Colorado Springs", "photographer"))
    assert all(r["sample"] == 0 for r in results)


def test_run_all_samples_repeats_each_pair():
    engines = {"Fake": _fake_engine("some answer")}
    results = aiquery.run_all("Light & Lense", "Colorado Springs", "photographer",
                               engines=engines, samples=3)
    n_prompts = len(aiquery.load_prompts("Light & Lense", "Colorado Springs", "photographer"))
    assert len(results) == n_prompts * 3
    assert sorted({r["sample"] for r in results}) == [0, 1, 2]


def test_run_all_cited_true_when_answer_has_a_url():
    engines = {"Fake": _fake_engine("Light & Lense is great, see https://lightandlense.com for more.")}
    results = aiquery.run_all("Light & Lense", "Colorado Springs", "photographer", engines=engines)
    assert all(r["cited"] is True for r in results)


def test_run_all_cited_false_without_a_url():
    engines = {"Fake": _fake_engine("Light & Lense is a great photographer.")}
    results = aiquery.run_all("Light & Lense", "Colorado Springs", "photographer", engines=engines)
    assert all(r["cited"] is False for r in results)


def test_business_rates_excludes_errors_from_denominator():
    results = [
        {"error": None, "mentioned": True, "cited": True, "engine": "A"},
        {"error": None, "mentioned": False, "cited": False, "engine": "A"},
        {"error": "could not verify", "mentioned": None, "cited": None, "engine": "B"},
    ]
    rates = aiquery.business_rates(results)
    assert rates["checked"] == 2  # the errored run is excluded, not counted as a miss
    assert rates["mention_rate"] == 0.5
    assert rates["cite_rate"] == 1.0  # of the 1 mention, 1 was cited
    assert rates["platforms_checked"] == 1  # engine B never successfully checked


def test_score_competitors_excludes_errors_from_denominator():
    results = [
        {"error": None, "competitors_mentioned": ["Acme"]},
        {"error": "could not verify", "competitors_mentioned": []},
    ]
    scores = aiquery.score_competitors(results, ["Acme"])
    assert scores == {"Acme": {"mentioned": 1, "total": 1}}


if __name__ == "__main__":
    import pytest
    raise SystemExit(pytest.main([__file__, "-q"]))

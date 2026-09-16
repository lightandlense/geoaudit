"""SPEC-3: the Digital Invisibility Risk Score. Source: SCORE-BUILDER.html's
own JS (the weights are "already written" there per the master build brief,
OPEN-ME.html) — this ports that exact formula, not an invented one.

0-100, LOWER IS BETTER (it's a risk score, not a visibility score).

Four channels, weights sum to 100:
    AI assistants   40%  (automated — real data from aiquery.py)
    Search engines   25%  (manual 0-3 judgment, see the *_manual params)
    Local and maps  25%  (manual 0-3 judgment)
    What AI says    10%  (manual 0-3 judgment)

Three of the four channels are 0-3 human judgment calls in the source tool,
not automated checks — SPEC-8's own manual-phase framing. ponytail: don't
fabricate an automated stand-in for a judgment call the spec designed to be
manual; take the same 0-3 inputs the real tool takes, and score a channel as
"not scored" when its inputs are None rather than guessing 0.
"""

# Each sub-weight set sums to 100 (asserted in demo() below), matching
# OPEN-ME.html's "Assert that every weight set sums to 100. Four weight
# sets, all must sum to 100."
AI_WEIGHTS = {"mention": 55, "cite": 25, "platform": 20}
GOOGLE_WEIGHTS = {"position": 40, "indexed": 35, "bing": 25}
LOCAL_WEIGHTS = {"pack": 32, "gbp": 24, "apple": 20, "nap": 24}
CHANNEL_WEIGHTS = {"ai": 40, "google": 25, "local": 25, "brand": 10}


def ai_risk(mention_rate, cite_rate, platform_rate):
    """Automated — from aiquery.business_rates()."""
    raw = mention_rate * AI_WEIGHTS["mention"] + cite_rate * AI_WEIGHTS["cite"] + platform_rate * AI_WEIGHTS["platform"]
    return max(0.0, min(100.0, 100 - raw))


def _manual_risk(weights, values):
    """values: {field: 0-3 or None}. Returns None if any field is None
    (not scored) rather than silently treating "unknown" as "worst case"."""
    if any(values.get(k) is None for k in weights):
        return None
    return sum(values[k] / 3 * w for k, w in weights.items())


def google_risk(position=None, indexed=None, bing=None):
    return _manual_risk(GOOGLE_WEIGHTS, {"position": position, "indexed": indexed, "bing": bing})


def local_risk(pack=None, gbp=None, apple=None, nap=None):
    return _manual_risk(LOCAL_WEIGHTS, {"pack": pack, "gbp": gbp, "apple": apple, "nap": nap})


def brand_risk(accuracy=None):
    return None if accuracy is None else accuracy / 3 * 100


def composite(ai, google, local, brand):
    """Weighted total. A None channel (not scored) is dropped from both the
    numerator and the weight total, so an unscored channel doesn't silently
    pull the score toward 0 — matches the "missing is not a zero" rule
    OPEN-ME.html states for the AI channel and applies here too."""
    parts = [(ai, CHANNEL_WEIGHTS["ai"]), (google, CHANNEL_WEIGHTS["google"]),
             (local, CHANNEL_WEIGHTS["local"]), (brand, CHANNEL_WEIGHTS["brand"])]
    scored = [(v, w) for v, w in parts if v is not None]
    if not scored:
        return None
    weight_total = sum(w for _, w in scored)
    return sum(v * w for v, w in scored) / weight_total


def demo():
    assert sum(AI_WEIGHTS.values()) == 100
    assert sum(GOOGLE_WEIGHTS.values()) == 100
    assert sum(LOCAL_WEIGHTS.values()) == 100
    assert sum(CHANNEL_WEIGHTS.values()) == 100

    ai = ai_risk(mention_rate=0.61, cite_rate=0.1, platform_rate=1.0)
    assert 0 <= ai <= 100
    assert google_risk(0, 0, 0) == 0
    assert google_risk(3, 3, 3) == 100
    assert google_risk(None, 0, 0) is None
    assert composite(ai, None, None, None) == ai  # only-scored-channel passthrough
    print("ai_risk:", round(ai, 1))
    print("composite (AI-only run):", round(composite(ai, None, None, None), 1))


if __name__ == "__main__":
    demo()

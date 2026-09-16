import scoring


def test_weight_sets_sum_to_100():
    assert sum(scoring.AI_WEIGHTS.values()) == 100
    assert sum(scoring.GOOGLE_WEIGHTS.values()) == 100
    assert sum(scoring.LOCAL_WEIGHTS.values()) == 100
    assert sum(scoring.CHANNEL_WEIGHTS.values()) == 100


def test_ai_risk_perfect_visibility_is_zero_risk():
    assert scoring.ai_risk(1.0, 1.0, 1.0) == 0.0


def test_ai_risk_zero_visibility_is_max_risk():
    assert scoring.ai_risk(0.0, 0.0, 0.0) == 100.0


def test_manual_channels_none_when_any_input_missing():
    assert scoring.google_risk(0, 0, None) is None
    assert scoring.local_risk(0, 0, 0, None) is None
    assert scoring.brand_risk(None) is None


def test_manual_channels_score_when_fully_given():
    assert scoring.google_risk(0, 0, 0) == 0
    assert scoring.google_risk(3, 3, 3) == 100
    assert scoring.brand_risk(3) == 100


def test_composite_drops_unscored_channels_not_zeros_them():
    ai_only = scoring.composite(ai=40, google=None, local=None, brand=None)
    assert ai_only == 40  # sole scored channel passes through, not diluted by missing ones


def test_composite_weights_scored_channels_by_their_share():
    # ai=40 (weight 40) and brand=0 (weight 10): weighted avg over just those two weights
    result = scoring.composite(ai=40, google=None, local=None, brand=0)
    assert result == (40 * 40 + 0 * 10) / (40 + 10)


def test_composite_all_none_returns_none():
    assert scoring.composite(None, None, None, None) is None

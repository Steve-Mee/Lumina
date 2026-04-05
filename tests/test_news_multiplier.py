from lumina_core.news_utils import build_news_key, resolve_news_multiplier


def test_news_key_building_is_stable():
    key = build_news_key({"impact": "high", "overall_sentiment": "bullish"})
    assert key == "high_bullish"


def test_news_multiplier_regression_mapping():
    multipliers = {
        "high_bullish": 1.3,
        "high_bearish": 0.6,
        "high_neutral": 0.9,
        "medium_bullish": 1.1,
        "medium_bearish": 0.9,
        "medium_neutral": 1.0,
    }
    assert resolve_news_multiplier({"impact": "high", "overall_sentiment": "bullish"}, multipliers) == 1.3
    assert resolve_news_multiplier({"impact": "high", "overall_sentiment": "bearish"}, multipliers) == 0.6
    assert resolve_news_multiplier({"impact": "medium", "overall_sentiment": "neutral"}, multipliers) == 1.0
    assert resolve_news_multiplier({"impact": "unknown", "overall_sentiment": "neutral"}, multipliers) == 1.0

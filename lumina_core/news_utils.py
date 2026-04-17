from typing import Mapping


def build_news_key(news_data: Mapping[str, str]) -> str:
    impact = news_data.get("impact", "medium")
    sentiment = news_data.get("overall_sentiment", "neutral")
    return f"{impact}_{sentiment}"


def resolve_news_multiplier(
    news_data: Mapping[str, str], multipliers: Mapping[str, float], default: float = 1.0
) -> float:
    key = build_news_key(news_data)
    return float(multipliers.get(key, default))

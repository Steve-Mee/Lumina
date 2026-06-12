"""Bible-derived observation features for Birth Phase v2 (4 dims)."""

from __future__ import annotations

from typing import Any

from lumina_bible.bible_engine import BibleEngine, DEFAULT_BIBLE


def _load_bible_layer(workspace_root: Any = None) -> dict[str, Any]:
    try:
        engine = BibleEngine(workspace_root=workspace_root)
        layer = engine.evolvable_layer
        return layer if isinstance(layer, dict) else dict(DEFAULT_BIBLE.get("evolvable_layer", {}))
    except Exception:
        return dict(DEFAULT_BIBLE.get("evolvable_layer", {}))


def bible_features_for_tick(
    tick: dict[str, Any],
    *,
    workspace_root: Any = None,
) -> tuple[float, float, float, float]:
    """Return (confluence_score, news_window_proximity, session_phase, mtf_bias)."""
    layer = _load_bible_layer(workspace_root)
    prob = layer.get("probability_model") if isinstance(layer.get("probability_model"), dict) else {}
    base_wr = float(prob.get("base_winrate", 0.55) or 0.55)
    confluence_bonus = float(prob.get("confluence_bonus", 0.15) or 0.15)

    regime = str(tick.get("regime", "NEUTRAL")).upper()
    imbalance = float(tick.get("imbalance", 1.0) or 1.0)
    confluence_score = base_wr
    if "TREND" in regime:
        confluence_score += confluence_bonus * 0.5
    if imbalance > 1.05 or imbalance < 0.95:
        confluence_score += confluence_bonus * 0.25
    confluence_score = max(0.0, min(1.0, confluence_score))

    news = layer.get("news_avoidance") if isinstance(layer.get("news_avoidance"), dict) else {}
    pre = float(news.get("pre_event_minutes", 10) or 10)
    post = float(news.get("post_event_minutes", 5) or 5)
    news_flag = float(tick.get("news_window_active", 0.0) or 0.0)
    news_proximity = 1.0 if news_flag > 0.5 else max(0.0, 1.0 - (pre + post) / 120.0)

    bar_index = int(tick.get("bar_index", 0) or 0)
    session_phase = 0.0 if bar_index < 120 else (0.5 if bar_index < 300 else 1.0)

    mtf = layer.get("mtf_matrix") if isinstance(layer.get("mtf_matrix"), dict) else {}
    dominant = str(mtf.get("dominant_tf", "240min") or "240min")
    mtf_bias = 1.0 if "240" in dominant else 0.5

    if "TREND_UP" in regime:
        mtf_bias *= 1.0
    elif "TREND_DOWN" in regime:
        mtf_bias *= -1.0
    else:
        mtf_bias *= 0.0

    return (
        round(confluence_score, 4),
        round(news_proximity, 4),
        round(session_phase, 4),
        round(mtf_bias, 4),
    )

"""News / reward / certificate threshold builders."""
from __future__ import annotations

from typing import Any

from lumina_core.birth.birth_certificate import BirthCertificateThresholds
from lumina_core.birth.config_curriculum import BirthNewsConfig, BirthRewardConfig
from lumina_core.birth.config_coercion_helpers import _coerce_float, _coerce_int

def build_news_config(news_raw: dict[str, Any]) -> BirthNewsConfig:
    return BirthNewsConfig(
        primary=str(news_raw.get("primary", "finnhub") or "finnhub"),
        enable_cache=bool(news_raw.get("enable_cache", True)),
        cache_path=str(news_raw.get("cache_path", "state/birth_news_cache.json") or "state/birth_news_cache.json"),
    )


def build_reward_config(reward_raw: dict[str, Any]) -> BirthRewardConfig:
    return BirthRewardConfig(
        enabled=bool(reward_raw.get("enabled", True)),
        expectancy_coeff=_coerce_float(reward_raw.get("expectancy_coeff"), 0.5),
        quality_win_bonus_coeff=_coerce_float(reward_raw.get("quality_win_bonus_coeff"), 0.25),
        loss_asymmetry_coeff=_coerce_float(reward_raw.get("loss_asymmetry_coeff"), 1.25),
        volatility_penalty_coeff=_coerce_float(reward_raw.get("volatility_penalty_coeff"), 0.15),
        atr_floor=_coerce_float(reward_raw.get("atr_floor"), 0.0005),
        trend_align_bonus_coeff=_coerce_float(reward_raw.get("trend_align_bonus_coeff"), 0.10),
        drawdown_penalty_coeff=_coerce_float(reward_raw.get("drawdown_penalty_coeff"), 0.20),
        sharpe_bonus_coeff=_coerce_float(reward_raw.get("sharpe_bonus_coeff"), 0.05),
        min_risk_usd=max(1.0, _coerce_float(reward_raw.get("min_risk_usd"), 25.0)),
        reward_clip=max(0.5, _coerce_float(reward_raw.get("reward_clip"), 5.0)),
        rolling_trade_window=max(5, _coerce_int(reward_raw.get("rolling_trade_window"), 50)),
        range_flat_bonus_coeff=max(
            0.0, _coerce_float(reward_raw.get("range_flat_bonus_coeff"), 0.003)
        ),
        range_churn_penalty_coeff=max(
            0.0, _coerce_float(reward_raw.get("range_churn_penalty_coeff"), 0.005)
        ),
        range_quality_boost_coeff=max(
            0.0, min(1.0, _coerce_float(reward_raw.get("range_quality_boost_coeff"), 0.15))
        ),
        s3_inband_hold_tax=max(
            0.0, _coerce_float(reward_raw.get("s3_inband_hold_tax"), 0.01)
        ),
        s3_inband_min_idle_hold_bars=max(
            1, _coerce_int(reward_raw.get("s3_inband_min_idle_hold_bars"), 32)
        ),
    )


def build_certificate_thresholds(thr_raw: dict[str, Any]) -> BirthCertificateThresholds:
    try:
        return BirthCertificateThresholds.model_validate(thr_raw or {})
    except Exception:
        return BirthCertificateThresholds()

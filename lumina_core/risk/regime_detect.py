"""RegimeDetectMixin (M5 extract)."""
from __future__ import annotations

from datetime import datetime
from typing import Any

import pandas as pd

from lumina_core.risk.regime_types import AdaptiveRegimePolicy, RegimeSnapshot


class RegimeDetectMixin:
    def __init__(self, config: dict[str, Any] | None = None, valuation_engine: Any | None = None):
        self.config = config if isinstance(config, dict) else {}
        self.valuation_engine = valuation_engine
        self.lookback_bars = int(self.config.get("lookback_bars", 120) or 120)
        self.trend_adx_threshold = float(self.config.get("trend_adx_threshold", 23.0) or 23.0)
        self.range_adx_threshold = float(self.config.get("range_adx_threshold", 18.0) or 18.0)
        self.high_vol_atr_ratio = float(self.config.get("high_vol_atr_ratio", 1.6) or 1.6)
        self.news_volume_ratio = float(self.config.get("news_volume_ratio", 2.2) or 2.2)
        self.low_liquidity_volume_ratio = float(self.config.get("low_liquidity_volume_ratio", 0.55) or 0.55)
        self.fast_path_weight_map = self._float_map(
            self.config.get("fast_path_weight_by_regime"),
            {
                "TRENDING": 0.35,
                "RANGING": 0.45,
                "HIGH_VOLATILITY": 0.72,
                "NEWS_DRIVEN": 0.82,
                "ROLLOVER": 0.8,
                "LOW_LIQUIDITY": 0.88,
                "NEUTRAL": 0.5,
            },
        )
        self.risk_multiplier_map = self._float_map(
            self.config.get("risk_multiplier_by_regime"),
            {
                "TRENDING": 1.15,
                "RANGING": 0.85,
                "HIGH_VOLATILITY": 0.55,
                "NEWS_DRIVEN": 0.45,
                "ROLLOVER": 0.5,
                "LOW_LIQUIDITY": 0.4,
                "NEUTRAL": 1.0,
            },
        )
        self.emotional_sensitivity_map = self._float_map(
            self.config.get("emotional_sensitivity_by_regime"),
            {
                "TRENDING": 0.9,
                "RANGING": 1.05,
                "HIGH_VOLATILITY": 1.2,
                "NEWS_DRIVEN": 1.35,
                "ROLLOVER": 1.15,
                "LOW_LIQUIDITY": 1.25,
                "NEUTRAL": 1.0,
            },
        )
        self.cooldown_minutes_map = self._int_map(
            self.config.get("cooldown_minutes_by_regime"),
            {
                "TRENDING": 20,
                "RANGING": 25,
                "HIGH_VOLATILITY": 45,
                "NEWS_DRIVEN": 60,
                "ROLLOVER": 50,
                "LOW_LIQUIDITY": 55,
                "NEUTRAL": 30,
            },
        )
        self.route_map = self._route_map(
            self.config.get("agent_route_by_regime"),
            {
                "TRENDING": ["swing", "scalper", "risk"],
                "RANGING": ["risk", "scalper", "swing"],
                "HIGH_VOLATILITY": ["risk", "scalper"],
                "NEWS_DRIVEN": ["risk", "scalper"],
                "ROLLOVER": ["risk"],
                "LOW_LIQUIDITY": ["risk"],
                "NEUTRAL": ["risk", "scalper", "swing"],
            },
        )
        configured_high_risk = self.config.get(
            "high_risk_regimes",
            ["HIGH_VOLATILITY", "NEWS_DRIVEN", "ROLLOVER", "LOW_LIQUIDITY"],
        )
        self.high_risk_regimes = {str(item).upper() for item in configured_high_risk}

    def detect(
        self,
        df: pd.DataFrame,
        *,
        instrument: str = "MES JUN26",
        confluence_score: float = 0.0,
        structure: dict[str, Any] | None = None,
        now: datetime | None = None,
    ) -> RegimeSnapshot:
        if not isinstance(df, pd.DataFrame) or df.empty:
            return self._neutral_snapshot("no_market_data")

        required = {"open", "high", "low", "close", "volume"}
        if not required.issubset(df.columns):
            return self._neutral_snapshot("missing_ohlcv_columns")

        rows = df.tail(max(60, self.lookback_bars)).copy()
        rows = rows.reset_index(drop=True)
        ts = self._resolve_timestamp(rows, now)
        features = self._extract_features(
            rows,
            instrument=instrument,
            confluence_score=confluence_score,
            structure=structure,
            now=ts,
        )
        label, evidence = self._classify(features)
        policy = self._policy_for(label)
        confidence = self._confidence_for(label, features)
        risk_state = "HIGH_RISK" if policy.high_risk else "NORMAL"
        return RegimeSnapshot(
            label=label,
            confidence=confidence,
            risk_state=risk_state,
            evidence=evidence,
            features=features,
            adaptive_policy=policy,
            timestamp=ts.isoformat(),
        )

    def _extract_features(
        self,
        rows: pd.DataFrame,
        *,
        instrument: str,
        confluence_score: float,
        structure: dict[str, Any] | None,
        now: datetime,
    ) -> dict[str, float]:
        close = self._numeric_series(rows, "close")
        high = self._numeric_series(rows, "high")
        low = self._numeric_series(rows, "low")
        volume = self._numeric_series(rows, "volume")

        tr = pd.concat([high - low, (high - close.shift()).abs(), (low - close.shift()).abs()], axis=1).max(axis=1)
        atr_fast = float(tr.rolling(14).mean().iloc[-1] or 0.0)
        atr_slow = float(tr.rolling(50).mean().iloc[-1] or atr_fast or 1e-9)
        up = (high - high.shift()).clip(lower=0)
        down = (low.shift() - low).clip(lower=0)
        if atr_fast > 0:
            plus_di = 100.0 * (up.ewm(alpha=1 / 14).mean() / atr_fast)
            minus_di = 100.0 * (down.ewm(alpha=1 / 14).mean() / atr_fast)
        else:
            plus_di = pd.Series(0.0, index=rows.index, dtype=float)
            minus_di = pd.Series(0.0, index=rows.index, dtype=float)
        dx_den = (plus_di + minus_di).astype(float)
        dx = 100.0 * (plus_di - minus_di).abs().div(dx_den.where(dx_den > 0.0))
        adx = float(dx.fillna(0.0).rolling(14).mean().fillna(0.0).iloc[-1] or 0.0)

        returns = close.pct_change().fillna(0.0)
        realized_fast = float(returns.tail(12).std() or 0.0)
        realized_slow = float(returns.tail(60).std() or realized_fast or 1e-9)
        atr_ratio = atr_fast / max(atr_slow, 1e-9)
        realized_vol_ratio = realized_fast / max(realized_slow, 1e-9)
        volume_ratio = float(volume.tail(5).mean() / max(volume.tail(40).mean(), 1e-9))
        recent_move = float(close.iloc[-1] - close.iloc[-20]) if len(close) >= 20 else 0.0
        path_length = float(close.diff().abs().tail(20).sum() or 0.0)
        price_efficiency = abs(recent_move) / max(path_length, 1e-9)
        range_compression = float(
            (high.tail(12) - low.tail(12)).mean() / max((high.tail(40) - low.tail(40)).mean(), 1e-9)
        )
        gap_score = float(abs(close.iloc[-1] - close.iloc[-2]) / max(atr_fast, 1e-9)) if len(close) >= 2 else 0.0
        slope_strength = self._slope_strength(close.tail(30))
        breakout_score = 0.0
        if structure:
            breakout_score += 0.45 if structure.get("bos") else 0.0
            breakout_score += 0.25 if structure.get("choch") else 0.0
            breakout_score += 0.15 if structure.get("fvg") else 0.0
        breakout_score += min(0.4, max(0.0, confluence_score - 0.6))

        spread_proxy = self._spread_proxy_ticks(rows, instrument)
        regular_session = 1.0 if self._is_regular_session(now) else 0.0
        rollover_score = self._rollover_score(instrument, now)
        session_liquidity = regular_session * volume_ratio

        return {
            "adx": max(0.0, adx),
            "atr_ratio": max(0.0, atr_ratio),
            "realized_vol_ratio": max(0.0, realized_vol_ratio),
            "volume_ratio": max(0.0, volume_ratio),
            "price_efficiency": max(0.0, min(1.0, price_efficiency)),
            "range_compression": max(0.0, range_compression),
            "gap_score": max(0.0, gap_score),
            "slope_strength": max(0.0, min(1.0, slope_strength)),
            "breakout_score": max(0.0, min(1.0, breakout_score)),
            "confluence_score": max(0.0, min(1.0, float(confluence_score or 0.0))),
            "spread_ticks": max(0.0, spread_proxy),
            "regular_session": regular_session,
            "session_liquidity": max(0.0, session_liquidity),
            "rollover_score": max(0.0, min(1.0, rollover_score)),
        }

    @staticmethod
    def _numeric_series(rows: pd.DataFrame, column: str) -> pd.Series:
        # Runtime feeds may provide nullable/object columns with pd.NA; normalize early for rolling math.
        return pd.to_numeric(rows[column], errors="coerce").ffill().fillna(0.0).astype(float)

    def _classify(self, features: dict[str, float]) -> tuple[str, list[str]]:
        evidence: list[str] = []
        if features["rollover_score"] >= 0.75:
            evidence.append("contract_in_rollover_window")
            return "ROLLOVER", evidence

        if (
            features["volume_ratio"] >= self.news_volume_ratio
            and features["gap_score"] >= 0.65
            and features["breakout_score"] >= 0.35
        ):
            evidence.extend(["volume_spike", "gap_impulse", "structure_break"])
            return "NEWS_DRIVEN", evidence

        if features["regular_session"] < 0.5 and (
            features["volume_ratio"] <= self.low_liquidity_volume_ratio or features["spread_ticks"] >= 3.0
        ):
            evidence.extend(["off_hours", "thin_book"])
            return "LOW_LIQUIDITY", evidence

        if (
            features["volume_ratio"] <= self.low_liquidity_volume_ratio
            and features["spread_ticks"] >= 2.0
            and features["session_liquidity"] < 0.8
        ):
            evidence.extend(["volume_drought", "wide_spread"])
            return "LOW_LIQUIDITY", evidence

        if (
            features["atr_ratio"] >= self.high_vol_atr_ratio
            or features["realized_vol_ratio"] >= 1.8
            or (
                features["range_compression"] >= 1.08
                and features["spread_ticks"] >= 1.5
                and features["price_efficiency"] >= 0.35
            )
        ):
            evidence.extend(["atr_expansion", "realized_vol_spike"])
            return "HIGH_VOLATILITY", evidence

        if (
            features["adx"] >= self.trend_adx_threshold
            and features["price_efficiency"] >= 0.58
            and (features["slope_strength"] >= 0.02 or features["price_efficiency"] >= 0.85)
        ):
            evidence.extend(["strong_adx", "directional_move"])
            return "TRENDING", evidence

        if (
            features["adx"] <= (self.range_adx_threshold + 7.0)
            and features["price_efficiency"] <= 0.38
            and features["range_compression"] <= 1.0
        ):
            evidence.extend(["weak_adx", "mean_reversion_path"])
            return "RANGING", evidence

        evidence.append("mixed_market_conditions")
        return "NEUTRAL", evidence



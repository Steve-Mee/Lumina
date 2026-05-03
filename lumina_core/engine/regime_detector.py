from __future__ import annotations

from dataclasses import asdict, dataclass, field
from datetime import datetime, timedelta, timezone
import logging
from typing import Any

import pandas as pd

logger = logging.getLogger(__name__)


_CONTRACT_MONTHS = {
    "F": 1,
    "G": 2,
    "H": 3,
    "J": 4,
    "K": 5,
    "M": 6,
    "N": 7,
    "Q": 8,
    "U": 9,
    "V": 10,
    "X": 11,
    "Z": 12,
}
_MONTH_NAMES = {
    "JAN": 1,
    "FEB": 2,
    "MAR": 3,
    "APR": 4,
    "MAY": 5,
    "JUN": 6,
    "JUL": 7,
    "AUG": 8,
    "SEP": 9,
    "OCT": 10,
    "NOV": 11,
    "DEC": 12,
}


@dataclass(slots=True)
class AdaptiveRegimePolicy:
    fast_path_weight: float
    agent_route: tuple[str, ...]
    risk_multiplier: float
    emotional_twin_sensitivity: float
    cooldown_minutes: int
    high_risk: bool
    nightly_evolution_focus: str

    def to_dict(self) -> dict[str, Any]:
        payload = asdict(self)
        payload["agent_route"] = list(self.agent_route)
        return payload


@dataclass(slots=True)
class RegimeSnapshot:
    label: str
    confidence: float
    risk_state: str
    evidence: list[str] = field(default_factory=list)
    features: dict[str, float] = field(default_factory=dict)
    adaptive_policy: AdaptiveRegimePolicy = field(
        default_factory=lambda: AdaptiveRegimePolicy(
            fast_path_weight=0.5,
            agent_route=("risk", "scalper", "swing"),
            risk_multiplier=1.0,
            emotional_twin_sensitivity=1.0,
            cooldown_minutes=30,
            high_risk=False,
            nightly_evolution_focus="balanced",
        )
    )
    timestamp: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())

    def to_dict(self) -> dict[str, Any]:
        return {
            "label": self.label,
            "confidence": round(float(self.confidence), 4),
            "risk_state": self.risk_state,
            "evidence": list(self.evidence),
            "features": {k: round(float(v), 6) for k, v in self.features.items()},
            "adaptive_policy": self.adaptive_policy.to_dict(),
            "timestamp": self.timestamp,
        }


class RegimeDetector:
    """Canonical regime detector for Lumina v50.

    Produces one normalized regime label plus the adaptive policy that other
    services use directly.
    """

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
        close = rows["close"].astype(float)
        high = rows["high"].astype(float)
        low = rows["low"].astype(float)
        volume = rows["volume"].astype(float)

        tr = pd.concat([high - low, (high - close.shift()).abs(), (low - close.shift()).abs()], axis=1).max(axis=1)
        atr_fast = float(tr.rolling(14).mean().iloc[-1] or 0.0)
        atr_slow = float(tr.rolling(50).mean().iloc[-1] or atr_fast or 1e-9)
        up = (high - high.shift()).clip(lower=0)
        down = (low.shift() - low).clip(lower=0)
        plus_di = 100.0 * (up.ewm(alpha=1 / 14).mean() / atr_fast) if atr_fast > 0 else pd.Series([0.0])
        minus_di = 100.0 * (down.ewm(alpha=1 / 14).mean() / atr_fast) if atr_fast > 0 else pd.Series([0.0])
        dx = 100.0 * (plus_di - minus_di).abs() / (plus_di + minus_di).replace(0, pd.NA)
        adx = float(dx.rolling(14).mean().fillna(0.0).iloc[-1])

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

    def _policy_for(self, label: str) -> AdaptiveRegimePolicy:
        route = tuple(self.route_map.get(label, self.route_map["NEUTRAL"]))
        high_risk = label in self.high_risk_regimes
        return AdaptiveRegimePolicy(
            fast_path_weight=float(self.fast_path_weight_map.get(label, self.fast_path_weight_map["NEUTRAL"])),
            agent_route=route,
            risk_multiplier=float(self.risk_multiplier_map.get(label, self.risk_multiplier_map["NEUTRAL"])),
            emotional_twin_sensitivity=float(
                self.emotional_sensitivity_map.get(label, self.emotional_sensitivity_map["NEUTRAL"])
            ),
            cooldown_minutes=int(self.cooldown_minutes_map.get(label, self.cooldown_minutes_map["NEUTRAL"])),
            high_risk=high_risk,
            nightly_evolution_focus=label.lower(),
        )

    def _confidence_for(self, label: str, features: dict[str, float]) -> float:
        if label == "TRENDING":
            score = (features["adx"] / 40.0 + features["price_efficiency"] + features["slope_strength"]) / 3.0
        elif label == "RANGING":
            score = ((1.0 - min(1.0, features["adx"] / 30.0)) + (1.0 - features["price_efficiency"])) / 2.0
        elif label == "HIGH_VOLATILITY":
            score = min(1.0, max(features["atr_ratio"], features["realized_vol_ratio"]) / 2.2)
        elif label == "NEWS_DRIVEN":
            score = min(
                1.0, (features["volume_ratio"] / 3.0 + features["gap_score"] / 2.0 + features["breakout_score"]) / 3.0
            )
        elif label == "ROLLOVER":
            score = features["rollover_score"]
        elif label == "LOW_LIQUIDITY":
            score = min(1.0, ((features["spread_ticks"] / 4.0) + (1.0 - min(1.0, features["volume_ratio"]))) / 2.0)
        else:
            score = 0.55
        return max(0.35, min(0.98, float(score)))

    def _spread_proxy_ticks(self, rows: pd.DataFrame, instrument: str) -> float:
        tick_size = 0.25
        if self.valuation_engine is not None:
            try:
                tick_size = float(self.valuation_engine.tick_size(instrument))
            except Exception:
                logging.exception("Unhandled broad exception fallback in lumina_core/engine/regime_detector.py:378")
                tick_size = 0.25

        last = rows.iloc[-1]
        explicit_spread = None
        for key in ("spread", "bid_ask_spread", "spread_points"):
            if key in rows.columns:
                try:
                    explicit_spread = float(last.get(key, 0.0) or 0.0)
                    break
                except Exception:
                    logging.exception("Unhandled broad exception fallback in lumina_core/engine/regime_detector.py:388")
                    explicit_spread = None
        if explicit_spread is None:
            explicit_spread = float((last.get("high", 0.0) - last.get("low", 0.0)) * 0.18)
        return explicit_spread / max(tick_size, 1e-9)

    @staticmethod
    def _slope_strength(series: pd.Series) -> float:
        if len(series) < 5:
            return 0.0
        values = [float(v) for v in series.tolist()]
        mean_x = (len(values) - 1) / 2.0
        mean_y = sum(values) / len(values)
        num = sum((idx - mean_x) * (val - mean_y) for idx, val in enumerate(values))
        den = sum((idx - mean_x) ** 2 for idx in range(len(values)))
        if den <= 0:
            return 0.0
        slope = num / den
        norm = abs(slope) / max(abs(mean_y), 1e-9) * len(values) * 12.0
        return max(0.0, min(1.0, norm))

    @staticmethod
    def _resolve_timestamp(rows: pd.DataFrame, now: datetime | None) -> datetime:
        if now is not None:
            return now if now.tzinfo is not None else now.replace(tzinfo=timezone.utc)
        if "timestamp" in rows.columns:
            try:
                ts = pd.to_datetime(rows["timestamp"].iloc[-1], utc=True)
                return ts.to_pydatetime()
            except Exception:
                logger.exception("RegimeDetector failed to parse latest timestamp; using current UTC time")
        return datetime.now(timezone.utc)

    @staticmethod
    def _is_regular_session(now: datetime) -> bool:
        hour = now.astimezone(timezone.utc).hour
        minute = now.astimezone(timezone.utc).minute
        session_minutes = hour * 60 + minute
        return 13 * 60 + 30 <= session_minutes <= 20 * 60 + 15

    def _rollover_score(self, instrument: str, now: datetime) -> float:
        month, year = self._parse_contract_month(instrument)
        if month is None or year is None:
            return 0.0
        expiry = self._third_friday(year, month)
        days = abs((expiry.date() - now.date()).days)
        if days <= 3:
            return 1.0
        if days <= 7:
            return 0.85
        if days <= 10:
            return 0.65
        return 0.0

    def _parse_contract_month(self, instrument: str) -> tuple[int | None, int | None]:
        text = str(instrument).upper().replace("-", " ")
        parts = [part for part in text.split() if part]
        for part in parts:
            if len(part) >= 5 and part[:3] in _MONTH_NAMES and part[-2:].isdigit():
                month = _MONTH_NAMES[part[:3]]
                year = 2000 + int(part[-2:])
                return month, year
            if len(part) >= 3 and part[0] in _CONTRACT_MONTHS and part[-2:].isdigit():
                month = _CONTRACT_MONTHS[part[0]]
                year = 2000 + int(part[-2:])
                return month, year
        return None, None

    @staticmethod
    def _third_friday(year: int, month: int) -> datetime:
        dt = datetime(year, month, 15, tzinfo=timezone.utc)
        while dt.weekday() != 4:
            dt += timedelta(days=1)
        return dt

    @staticmethod
    def _float_map(raw: Any, defaults: dict[str, float]) -> dict[str, float]:
        payload = dict(defaults)
        if isinstance(raw, dict):
            for key, value in raw.items():
                try:
                    payload[str(key).upper()] = float(value)
                except (TypeError, ValueError):
                    continue
        return payload

    @staticmethod
    def _int_map(raw: Any, defaults: dict[str, int]) -> dict[str, int]:
        payload = dict(defaults)
        if isinstance(raw, dict):
            for key, value in raw.items():
                try:
                    payload[str(key).upper()] = int(value)
                except (TypeError, ValueError):
                    continue
        return payload

    @staticmethod
    def _route_map(raw: Any, defaults: dict[str, list[str]]) -> dict[str, list[str]]:
        payload = {str(key).upper(): list(value) for key, value in defaults.items()}
        if isinstance(raw, dict):
            for key, value in raw.items():
                if isinstance(value, (list, tuple)):
                    payload[str(key).upper()] = [str(item) for item in value if str(item).strip()]
        return payload

    def _neutral_snapshot(self, reason: str) -> RegimeSnapshot:
        return RegimeSnapshot(
            label="NEUTRAL",
            confidence=0.35,
            risk_state="NORMAL",
            evidence=[reason],
            features={},
            adaptive_policy=self._policy_for("NEUTRAL"),
        )

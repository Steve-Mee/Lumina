"""Frozen continuity config. Runtime values may only tighten charter floors, never loosen them."""

from __future__ import annotations

import math
from dataclasses import dataclass
from functools import cache
from pathlib import Path
from typing import Mapping

import tomllib

from lumina_core.agent_orchestration.schemas_research import DecayMethod
from lumina_research.validation.thresholds import FLOOR_MIN_OOS_WINDOWS, FLOOR_PBO_HARD_REJECT, FLOOR_PBO_WARNING

_DEFAULT_PATH = Path(__file__).with_name("limits.toml")
_METHODS: frozenset[str] = frozenset({"ztest", "percentile", "cusum", "sprt", "combined"})
_ALLOWED = frozenset(
    {
        "window",
        "method",
        "z_deweight",
        "z_suspend",
        "z_retire",
        "percentile_deweight",
        "percentile_suspend",
        "percentile_retire",
        "cusum_k",
        "cusum_h_deweight",
        "cusum_h_suspend",
        "cusum_h_retire",
        "sprt_delta",
        "sprt_alpha",
        "sprt_beta",
        "deweight_multiplier",
        "min_observations",
        "max_signal_notional_pct",
        "max_instrument_notional_pct",
        "max_family_notional_pct",
        "max_cluster_notional_pct",
        "min_active_signals",
        "min_capacity_weight",
        "replenish_count",
        "pbo_promote_max",
        "pbo_reject_min",
        "min_oos_windows",
        "equity",
    }
)


class ContinuityConfigError(ValueError):
    """Invalid continuity configuration."""


@dataclass(frozen=True, slots=True)
class ContinuityConfig:
    window: int
    method: DecayMethod
    z_deweight: float
    z_suspend: float
    z_retire: float
    percentile_deweight: float
    percentile_suspend: float
    percentile_retire: float
    cusum_k: float
    cusum_h_deweight: float
    cusum_h_suspend: float
    cusum_h_retire: float
    sprt_delta: float
    sprt_alpha: float
    sprt_beta: float
    deweight_multiplier: float
    min_observations: int
    max_signal_notional_pct: float
    max_instrument_notional_pct: float
    max_family_notional_pct: float
    max_cluster_notional_pct: float
    min_active_signals: int
    min_capacity_weight: float
    replenish_count: int
    pbo_promote_max: float
    pbo_reject_min: float
    min_oos_windows: int
    equity: float

    def __post_init__(self) -> None:
        _validate(self)

    def __init_subclass__(cls) -> None:
        raise TypeError("ContinuityConfig cannot be subclassed")


def load_default_config(path: Path | None = None) -> ContinuityConfig:
    source = path if path is not None else _DEFAULT_PATH
    with source.open("rb") as handle:
        loaded = tomllib.load(handle)
    cfg = _parse_mapping({str(key): loaded[key] for key in loaded})
    if source.resolve() != _DEFAULT_PATH.resolve():
        _require_at_least_as_tight(cfg, packaged_config())
    return cfg


@cache
def packaged_config() -> ContinuityConfig:
    with _DEFAULT_PATH.open("rb") as handle:
        loaded = tomllib.load(handle)
    return _parse_mapping({str(key): loaded[key] for key in loaded})


def config_from_mapping(raw: Mapping[str, object]) -> ContinuityConfig:
    cfg = _parse_mapping(raw)
    _require_at_least_as_tight(cfg, packaged_config())
    return cfg


def _parse_mapping(raw: Mapping[str, object]) -> ContinuityConfig:
    extra = set(raw) - _ALLOWED
    missing = _ALLOWED - set(raw)
    if extra or missing:
        raise ContinuityConfigError(f"invalid continuity keys extra={sorted(extra)} missing={sorted(missing)}")
    return ContinuityConfig(
        window=_positive_int(raw["window"], "window"),
        method=_method(raw["method"]),
        z_deweight=_finite(raw["z_deweight"], "z_deweight"),
        z_suspend=_finite(raw["z_suspend"], "z_suspend"),
        z_retire=_finite(raw["z_retire"], "z_retire"),
        percentile_deweight=_unit(raw["percentile_deweight"], "percentile_deweight"),
        percentile_suspend=_unit(raw["percentile_suspend"], "percentile_suspend"),
        percentile_retire=_unit(raw["percentile_retire"], "percentile_retire"),
        cusum_k=_positive_float(raw["cusum_k"], "cusum_k"),
        cusum_h_deweight=_positive_float(raw["cusum_h_deweight"], "cusum_h_deweight"),
        cusum_h_suspend=_positive_float(raw["cusum_h_suspend"], "cusum_h_suspend"),
        cusum_h_retire=_positive_float(raw["cusum_h_retire"], "cusum_h_retire"),
        sprt_delta=_positive_float(raw["sprt_delta"], "sprt_delta"),
        sprt_alpha=_open_unit(raw["sprt_alpha"], "sprt_alpha"),
        sprt_beta=_open_unit(raw["sprt_beta"], "sprt_beta"),
        deweight_multiplier=_open_unit(raw["deweight_multiplier"], "deweight_multiplier"),
        min_observations=_positive_int(raw["min_observations"], "min_observations"),
        max_signal_notional_pct=_unit_positive(raw["max_signal_notional_pct"], "max_signal_notional_pct"),
        max_instrument_notional_pct=_unit_positive(
            raw["max_instrument_notional_pct"], "max_instrument_notional_pct"
        ),
        max_family_notional_pct=_unit_positive(raw["max_family_notional_pct"], "max_family_notional_pct"),
        max_cluster_notional_pct=_unit_positive(raw["max_cluster_notional_pct"], "max_cluster_notional_pct"),
        min_active_signals=_nonneg_int(raw["min_active_signals"], "min_active_signals"),
        min_capacity_weight=_nonneg_float(raw["min_capacity_weight"], "min_capacity_weight"),
        replenish_count=_positive_int(raw["replenish_count"], "replenish_count"),
        pbo_promote_max=_unit(raw["pbo_promote_max"], "pbo_promote_max"),
        pbo_reject_min=_unit(raw["pbo_reject_min"], "pbo_reject_min"),
        min_oos_windows=_positive_int(raw["min_oos_windows"], "min_oos_windows"),
        equity=_positive_float(raw["equity"], "equity"),
    )


def _require_at_least_as_tight(config: ContinuityConfig, packaged: ContinuityConfig) -> None:
    """Runtime overlays may only tighten packaged detection and capacity protection."""
    if config.window > packaged.window:
        raise ContinuityConfigError("window cannot be longer than the packaged 20-day rolling window")
    if config.z_deweight < packaged.z_deweight:
        raise ContinuityConfigError("z_deweight cannot be weaker than the packaged default")
    if config.z_suspend < packaged.z_suspend:
        raise ContinuityConfigError("z_suspend cannot be weaker than the packaged default")
    if config.z_retire < packaged.z_retire:
        raise ContinuityConfigError("z_retire cannot be weaker than the packaged default")
    if config.percentile_deweight < packaged.percentile_deweight:
        raise ContinuityConfigError("percentile_deweight cannot be weaker than the packaged default")
    if config.percentile_suspend < packaged.percentile_suspend:
        raise ContinuityConfigError("percentile_suspend cannot be weaker than the packaged default")
    if config.percentile_retire < packaged.percentile_retire:
        raise ContinuityConfigError("percentile_retire cannot be weaker than the packaged default")
    if config.cusum_k > packaged.cusum_k:
        raise ContinuityConfigError("cusum_k cannot be weaker than the packaged default")
    if config.cusum_h_deweight > packaged.cusum_h_deweight:
        raise ContinuityConfigError("cusum_h_deweight cannot be weaker than the packaged default")
    if config.cusum_h_suspend > packaged.cusum_h_suspend:
        raise ContinuityConfigError("cusum_h_suspend cannot be weaker than the packaged default")
    if config.cusum_h_retire > packaged.cusum_h_retire:
        raise ContinuityConfigError("cusum_h_retire cannot be weaker than the packaged default")
    if abs(config.sprt_delta - packaged.sprt_delta) > 1e-12:
        raise ContinuityConfigError("sprt_delta cannot be changed without an ADR")
    if abs(config.sprt_alpha - packaged.sprt_alpha) > 1e-12:
        raise ContinuityConfigError("sprt_alpha cannot be changed without an ADR")
    if abs(config.sprt_beta - packaged.sprt_beta) > 1e-12:
        raise ContinuityConfigError("sprt_beta cannot be changed without an ADR")
    if config.deweight_multiplier > packaged.deweight_multiplier:
        raise ContinuityConfigError("deweight_multiplier cannot be weaker than the packaged default")
    if config.max_signal_notional_pct > packaged.max_signal_notional_pct:
        raise ContinuityConfigError("max_signal_notional_pct cannot exceed the packaged cap")
    if config.max_instrument_notional_pct > packaged.max_instrument_notional_pct:
        raise ContinuityConfigError("max_instrument_notional_pct cannot exceed the packaged cap")
    if config.max_family_notional_pct > packaged.max_family_notional_pct:
        raise ContinuityConfigError("max_family_notional_pct cannot exceed the packaged cap")
    if config.max_cluster_notional_pct > packaged.max_cluster_notional_pct:
        raise ContinuityConfigError("max_cluster_notional_pct cannot exceed the packaged cap")
    if config.equity > packaged.equity + 1e-9:
        raise ContinuityConfigError("equity cannot exceed the packaged continuity equity")


def _validate(config: ContinuityConfig) -> None:
    if config.window < config.min_observations:
        raise ContinuityConfigError("window cannot be shorter than min_observations")
    if config.z_retire > config.z_suspend or config.z_suspend > config.z_deweight:
        raise ContinuityConfigError("z thresholds must satisfy retire <= suspend <= deweight")
    if config.percentile_retire > config.percentile_suspend or config.percentile_suspend > config.percentile_deweight:
        raise ContinuityConfigError("percentile thresholds must satisfy retire <= suspend <= deweight")
    if config.cusum_h_deweight > config.cusum_h_suspend or config.cusum_h_suspend > config.cusum_h_retire:
        raise ContinuityConfigError("CUSUM thresholds must satisfy deweight <= suspend <= retire")
    if config.pbo_promote_max > FLOOR_PBO_WARNING:
        raise ContinuityConfigError("pbo_promote_max cannot be weaker than the charter warning 0.25")
    if config.pbo_reject_min < FLOOR_PBO_HARD_REJECT:
        raise ContinuityConfigError("pbo_reject_min cannot be weaker than the charter hard reject 0.50")
    if config.min_oos_windows < FLOOR_MIN_OOS_WINDOWS:
        raise ContinuityConfigError("min_oos_windows cannot be weaker than the gate floor")


def _method(value: object) -> DecayMethod:
    if not isinstance(value, str) or value not in _METHODS:
        raise ContinuityConfigError("method must be ztest, percentile, cusum, sprt, or combined")
    if value == "ztest":
        return "ztest"
    if value == "percentile":
        return "percentile"
    if value == "cusum":
        return "cusum"
    if value == "sprt":
        return "sprt"
    return "combined"


def _finite(value: object, name: str) -> float:
    number = _as_float(value, name)
    if not math.isfinite(number):
        raise ContinuityConfigError(f"{name} must be finite")
    return number


def _positive_float(value: object, name: str) -> float:
    number = _finite(value, name)
    if number <= 0.0:
        raise ContinuityConfigError(f"{name} must be > 0")
    return number


def _nonneg_float(value: object, name: str) -> float:
    number = _finite(value, name)
    if number < 0.0:
        raise ContinuityConfigError(f"{name} must be >= 0")
    return number


def _unit(value: object, name: str) -> float:
    number = _finite(value, name)
    if number < 0.0 or number > 1.0:
        raise ContinuityConfigError(f"{name} must be in [0, 1]")
    return number


def _unit_positive(value: object, name: str) -> float:
    number = _unit(value, name)
    if number <= 0.0:
        raise ContinuityConfigError(f"{name} must be in (0, 1]")
    return number


def _open_unit(value: object, name: str) -> float:
    number = _finite(value, name)
    if number <= 0.0 or number >= 1.0:
        raise ContinuityConfigError(f"{name} must be in (0, 1)")
    return number


def _positive_int(value: object, name: str) -> int:
    if isinstance(value, bool) or not isinstance(value, int) or value < 1:
        raise ContinuityConfigError(f"{name} must be an int >= 1")
    return value


def _nonneg_int(value: object, name: str) -> int:
    if isinstance(value, bool) or not isinstance(value, int) or value < 0:
        raise ContinuityConfigError(f"{name} must be an int >= 0")
    return value


def _as_float(value: object, name: str) -> float:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise ContinuityConfigError(f"{name} must be a number")
    return float(value)

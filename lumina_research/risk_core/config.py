"""Immutable Risk Core config. Frozen dataclass, no setters, extra keys rejected."""

from __future__ import annotations

import math
from dataclasses import dataclass
from pathlib import Path
from typing import Mapping

import tomllib

_DEFAULT_PATH = Path(__file__).with_name("limits.toml")
_ALLOWED = frozenset(
    {
        "max_position_pct",
        "max_daily_loss_pct",
        "max_total_drawdown_pct",
        "leverage_cap",
        "correlation_cluster_limit_pct",
        "heartbeat_timeout_sec",
        "min_quantity",
    }
)


class RiskConfigError(ValueError):
    """Invalid research Risk Core configuration."""


@dataclass(frozen=True, slots=True)
class RiskConfig:
    max_position_pct: float
    max_daily_loss_pct: float
    max_total_drawdown_pct: float
    leverage_cap: float
    correlation_cluster_limit_pct: float
    heartbeat_timeout_sec: float
    min_quantity: float

    def __post_init__(self) -> None:
        for name, value in (
            ("max_position_pct", self.max_position_pct),
            ("max_daily_loss_pct", self.max_daily_loss_pct),
            ("max_total_drawdown_pct", self.max_total_drawdown_pct),
            ("leverage_cap", self.leverage_cap),
            ("correlation_cluster_limit_pct", self.correlation_cluster_limit_pct),
            ("heartbeat_timeout_sec", self.heartbeat_timeout_sec),
            ("min_quantity", self.min_quantity),
        ):
            if not math.isfinite(value) or value <= 0.0:
                raise RiskConfigError(f"{name} must be a finite number > 0")
        if self.max_position_pct > 1.0:
            raise RiskConfigError("max_position_pct cannot exceed 1")
        if self.max_daily_loss_pct > 1.0 or self.max_total_drawdown_pct > 1.0:
            raise RiskConfigError("loss and drawdown caps are fractions of equity and cannot exceed 1")
        if self.correlation_cluster_limit_pct > 1.0:
            raise RiskConfigError("correlation_cluster_limit_pct cannot exceed 1")

    def __init_subclass__(cls) -> None:
        raise TypeError("RiskConfig cannot be subclassed")

    @staticmethod
    def from_mapping(raw: Mapping[str, object]) -> RiskConfig:
        extra = set(raw) - _ALLOWED
        missing = _ALLOWED - set(raw)
        if extra or missing:
            raise RiskConfigError(f"invalid risk config keys extra={sorted(extra)} missing={sorted(missing)}")
        return RiskConfig(
            max_position_pct=_positive_float(raw["max_position_pct"], "max_position_pct"),
            max_daily_loss_pct=_positive_float(raw["max_daily_loss_pct"], "max_daily_loss_pct"),
            max_total_drawdown_pct=_positive_float(raw["max_total_drawdown_pct"], "max_total_drawdown_pct"),
            leverage_cap=_positive_float(raw["leverage_cap"], "leverage_cap"),
            correlation_cluster_limit_pct=_positive_float(
                raw["correlation_cluster_limit_pct"],
                "correlation_cluster_limit_pct",
            ),
            heartbeat_timeout_sec=_positive_float(raw["heartbeat_timeout_sec"], "heartbeat_timeout_sec"),
            min_quantity=_positive_float(raw["min_quantity"], "min_quantity"),
        )


def load_default_config(path: Path | None = None) -> RiskConfig:
    source = path if path is not None else _DEFAULT_PATH
    with source.open("rb") as handle:
        loaded = tomllib.load(handle)
    present = {str(key) for key in loaded}
    extra = present - _ALLOWED
    missing = _ALLOWED - present
    if extra or missing:
        raise RiskConfigError(f"invalid risk config keys extra={sorted(extra)} missing={sorted(missing)}")
    return RiskConfig.from_mapping(
        {
            "max_position_pct": loaded["max_position_pct"],
            "max_daily_loss_pct": loaded["max_daily_loss_pct"],
            "max_total_drawdown_pct": loaded["max_total_drawdown_pct"],
            "leverage_cap": loaded["leverage_cap"],
            "correlation_cluster_limit_pct": loaded["correlation_cluster_limit_pct"],
            "heartbeat_timeout_sec": loaded["heartbeat_timeout_sec"],
            "min_quantity": loaded["min_quantity"],
        }
    )


def _positive_float(value: object, name: str) -> float:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise RiskConfigError(f"{name} must be a number")
    number = float(value)
    if not math.isfinite(number) or number <= 0.0:
        raise RiskConfigError(f"{name} must be a finite number > 0")
    return number

"""Single threshold file for the Validation Gate. Frozen after load."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Mapping

import tomllib

from lumina_research.validation.types import Thresholds

_DEFAULT_PATH = Path(__file__).with_name("gate_thresholds.toml")

# Hard floors. Runtime config may only tighten these; the gate also re-applies them.
FLOOR_DSR_PROBABILITY_MIN = 0.95
FLOOR_WFE_MIN = 0.5
FLOOR_PBO_HARD_REJECT = 0.50
FLOOR_PBO_WARNING = 0.25
FLOOR_MIN_OOS_WINDOWS = 6
_ALLOWED_KEYS = frozenset(
    {
        "dsr_probability_min",
        "wfe_min",
        "pbo_hard_reject",
        "pbo_warning",
        "min_oos_windows",
    }
)


class ThresholdConfigError(ValueError):
    """The threshold file is missing keys, has extras, or violates fail-closed bounds."""


@dataclass(frozen=True, slots=True)
class FrozenThresholds:
    values: Thresholds
    source: str

    def as_thresholds(self) -> Thresholds:
        return self.values


def default_thresholds() -> Thresholds:
    return Thresholds(
        dsr_probability_min=FLOOR_DSR_PROBABILITY_MIN,
        wfe_min=FLOOR_WFE_MIN,
        pbo_hard_reject=FLOOR_PBO_HARD_REJECT,
        pbo_warning=FLOOR_PBO_WARNING,
        min_oos_windows=FLOOR_MIN_OOS_WINDOWS,
    )


def enforce_floors(thresholds: Thresholds) -> Thresholds:
    """Config may only tighten floors. Weaker values are replaced, not accepted."""
    pbo_hard = min(thresholds.pbo_hard_reject, FLOOR_PBO_HARD_REJECT)
    pbo_warn = min(thresholds.pbo_warning, FLOOR_PBO_WARNING, pbo_hard)
    return Thresholds(
        dsr_probability_min=max(thresholds.dsr_probability_min, FLOOR_DSR_PROBABILITY_MIN),
        wfe_min=max(thresholds.wfe_min, FLOOR_WFE_MIN),
        pbo_hard_reject=pbo_hard,
        pbo_warning=pbo_warn,
        min_oos_windows=max(thresholds.min_oos_windows, FLOOR_MIN_OOS_WINDOWS),
    )


def load_thresholds(path: Path | None = None) -> FrozenThresholds:
    source = path if path is not None else _DEFAULT_PATH
    with source.open("rb") as handle:
        loaded = tomllib.load(handle)
    present = {str(key) for key in loaded}
    extra = present - _ALLOWED_KEYS
    missing = _ALLOWED_KEYS - present
    if extra or missing:
        raise ThresholdConfigError(f"invalid threshold keys extra={sorted(extra)} missing={sorted(missing)}")
    mapping = {
        "dsr_probability_min": loaded["dsr_probability_min"],
        "wfe_min": loaded["wfe_min"],
        "pbo_hard_reject": loaded["pbo_hard_reject"],
        "pbo_warning": loaded["pbo_warning"],
        "min_oos_windows": loaded["min_oos_windows"],
    }
    return FrozenThresholds(values=_parse_mapping(mapping), source=str(source))


def _parse_mapping(raw: Mapping[str, object]) -> Thresholds:
    extra = set(raw) - _ALLOWED_KEYS
    missing = _ALLOWED_KEYS - set(raw)
    if extra or missing:
        raise ThresholdConfigError(f"invalid threshold keys extra={sorted(extra)} missing={sorted(missing)}")
    values = default_thresholds()
    parsed = Thresholds(
        dsr_probability_min=_unit_interval(raw["dsr_probability_min"], "dsr_probability_min"),
        wfe_min=_non_negative(raw["wfe_min"], "wfe_min"),
        pbo_hard_reject=_unit_interval(raw["pbo_hard_reject"], "pbo_hard_reject"),
        pbo_warning=_unit_interval(raw["pbo_warning"], "pbo_warning"),
        min_oos_windows=_min_windows(raw["min_oos_windows"]),
    )
    if parsed.pbo_warning > parsed.pbo_hard_reject:
        raise ThresholdConfigError("pbo_warning must be <= pbo_hard_reject")
    if parsed.dsr_probability_min < values.dsr_probability_min:
        raise ThresholdConfigError("dsr_probability_min cannot be weaker than 0.95")
    if parsed.wfe_min < values.wfe_min:
        raise ThresholdConfigError("wfe_min cannot be weaker than 0.5")
    if parsed.min_oos_windows < values.min_oos_windows:
        raise ThresholdConfigError("min_oos_windows cannot be weaker than 6")
    if parsed.pbo_hard_reject > FLOOR_PBO_HARD_REJECT:
        raise ThresholdConfigError("pbo_hard_reject cannot be weaker than 0.50")
    if parsed.pbo_warning > FLOOR_PBO_WARNING:
        raise ThresholdConfigError("pbo_warning cannot be weaker than 0.25")
    return enforce_floors(parsed)


def _unit_interval(value: object, name: str) -> float:
    number = _as_float(value, name)
    if number < 0.0 or number > 1.0:
        raise ThresholdConfigError(f"{name} must be in [0, 1]")
    return number


def _non_negative(value: object, name: str) -> float:
    number = _as_float(value, name)
    if number < 0.0:
        raise ThresholdConfigError(f"{name} must be >= 0")
    return number


def _min_windows(value: object) -> int:
    if isinstance(value, bool) or not isinstance(value, int):
        raise ThresholdConfigError("min_oos_windows must be an int")
    if value < 6:
        raise ThresholdConfigError("min_oos_windows cannot be weaker than 6")
    return value


def _as_float(value: object, name: str) -> float:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise ThresholdConfigError(f"{name} must be a number")
    return float(value)

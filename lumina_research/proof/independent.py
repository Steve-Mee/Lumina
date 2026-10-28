"""Independent synthetic generators. Seeds and processes are not the Phase 4 tuning set."""

from __future__ import annotations

import math
import random
from typing import Literal

from lumina_research.monitoring.acceptance import MEANINGFUL_RAMP_DAYS
from lumina_research.monitoring.campaign import DEFAULT_CAMPAIGN_SEEDS
from lumina_research.monitoring.types import ContinuityRefused, Instrument

# Tuning used (20261028, 7, 13, 21, 42, 99, 123, 256, 1024, 4096) and Gaussian paths.
INDEPENDENT_SEEDS: tuple[int, ...] = (314159, 271828, 161803, 141421, 173205, 223606, 264575, 331662, 577215, 618033)
INDEPENDENT_INSTRUMENTS: tuple[Instrument, ...] = (
    "ES",
    "NQ",
    "MES",
    "MNQ",
    "ES",
    "NQ",
    "MES",
    "MNQ",
    "ES",
    "NQ",
)
INDEPENDENT_OOS: tuple[float, ...] = (0.68, 0.74, 0.81, 0.77, 0.84, 0.79)
FLOOR_KINDS: tuple[str, ...] = (
    "healthy_laplace",
    "abrupt_student",
    "gradual_smooth",
    "high_vol_mixture",
    "regime_laplace",
    "material_break",
)
SHORT_DECAY_KINDS: frozenset[str] = frozenset(
    {"abrupt_student", "gradual_smooth", "regime_laplace", "material_break"}
)
SLOW_KINDS: tuple[str, ...] = ("slow_gradual_30", "slow_gradual_45", "slow_gradual_60")
SLOW_RAMPS: dict[str, int] = {"slow_gradual_30": 30, "slow_gradual_45": 45, "slow_gradual_60": 60}
_INSTRUMENTS: dict[str, Instrument] = {"ES": "ES", "NQ": "NQ", "MES": "MES", "MNQ": "MNQ"}


def assert_independent_seeds(seeds: tuple[int, ...]) -> None:
    overlap = set(seeds) & set(DEFAULT_CAMPAIGN_SEEDS)
    if overlap:
        raise ContinuityRefused(f"independent seeds overlap Phase 4 tuning seeds: {sorted(overlap)}")
    if len(set(seeds)) != len(seeds):
        raise ContinuityRefused("independent seeds must be unique")


def map_instrument(root: str) -> Instrument:
    mapped = _INSTRUMENTS.get(root.strip().upper())
    if mapped is None:
        raise ContinuityRefused(f"unknown instrument {root!r}")
    return mapped


def laplace(rng: random.Random, *, scale: float) -> float:
    unit = rng.random() - 0.5
    return -scale * math.copysign(math.log(max(1.0 - 2.0 * abs(unit), 1e-12)), unit)


def student_t(rng: random.Random, *, df: int) -> float:
    if df < 2:
        raise ContinuityRefused("student-t df must be >= 2")
    zed = rng.gauss(0.0, 1.0)
    chi = sum(rng.gauss(0.0, 1.0) ** 2 for _ in range(df))
    return zed / math.sqrt(max(chi, 1e-12) / float(df))


def healthy_laplace(rng: random.Random, *, oos_mean: float, oos_stdev: float, n: int) -> tuple[float, ...]:
    scale = max(oos_stdev * 0.45, 1e-6) / math.sqrt(2.0)
    return tuple(oos_mean + laplace(rng, scale=scale) for _ in range(n))


def abrupt_student(
    rng: random.Random, *, oos_mean: float, oos_stdev: float, n: int, decay_start: int
) -> tuple[float, ...]:
    sigma = max(oos_stdev * 0.45, 1e-6)
    shift = oos_mean - 2.8 * max(oos_stdev, 1e-6)
    scale = sigma * math.sqrt(3.0 / 5.0)
    out: list[float] = []
    for index in range(n):
        mu = oos_mean if index < decay_start else shift
        out.append(mu + scale * student_t(rng, df=5))
    return tuple(out)


def gradual_smooth(
    rng: random.Random, *, oos_mean: float, oos_stdev: float, n: int, decay_start: int
) -> tuple[float, ...]:
    sigma = max(oos_stdev * 0.45, 1e-6)
    depth = 2.8 * max(oos_stdev, 1e-6)
    ramp = min(MEANINGFUL_RAMP_DAYS, max(n - 1 - decay_start, 1))
    out: list[float] = []
    for index in range(n):
        if index < decay_start:
            mu = oos_mean
        else:
            progress = min(float(index - decay_start) / float(ramp), 1.0)
            mu = oos_mean - depth * (0.5 - 0.5 * math.cos(math.pi * progress))
        out.append(mu + laplace(rng, scale=sigma / math.sqrt(2.0)))
    return tuple(out)


def material_break(
    rng: random.Random, *, oos_mean: float, oos_stdev: float, n: int, decay_start: int
) -> tuple[float, ...]:
    """Fast material break: IC halved, Sharpe collapse, 1.5x drawdown shock."""
    sigma = max(oos_stdev * 0.45, 1e-6)
    halved = 0.5 * oos_mean
    shock = 1.5 * 2.0 * max(oos_stdev, 1e-6)
    out: list[float] = []
    for index in range(n):
        if index < decay_start:
            out.append(oos_mean + laplace(rng, scale=sigma / math.sqrt(2.0)))
        elif index == decay_start:
            out.append(halved - shock + laplace(rng, scale=sigma / math.sqrt(2.0)))
        else:
            out.append(halved + laplace(rng, scale=sigma / math.sqrt(2.0)))
    return tuple(out)


def high_vol_mixture(rng: random.Random, *, oos_mean: float, oos_stdev: float, n: int) -> tuple[float, ...]:
    quiet = max(oos_stdev * 0.70, 1e-6)
    loud = max(oos_stdev * 1.60, 1e-6)
    out: list[float] = []
    for _ in range(n):
        sigma = loud if rng.random() < 0.40 else quiet
        out.append(rng.gauss(oos_mean, sigma))
    return tuple(out)


def regime_laplace(
    rng: random.Random, *, oos_mean: float, oos_stdev: float, n: int, decay_start: int
) -> tuple[float, ...]:
    quiet = max(oos_stdev * 0.45, 1e-6) / math.sqrt(2.0)
    loud = max(oos_stdev, 1e-6) / math.sqrt(2.0)
    shift = oos_mean - 2.4 * max(oos_stdev, 1e-6)
    out: list[float] = []
    for index in range(n):
        if index < decay_start:
            out.append(oos_mean + laplace(rng, scale=quiet))
        else:
            out.append(shift + laplace(rng, scale=loud))
    return tuple(out)


def slow_gradual(
    rng: random.Random,
    *,
    oos_mean: float,
    oos_stdev: float,
    n: int,
    decay_start: int,
    ramp_days: int,
) -> tuple[float, ...]:
    if ramp_days < 30:
        raise ContinuityRefused("slow decay ramp must be >= 30 trading days")
    sigma = max(oos_stdev * 0.45, 1e-6)
    depth = 2.8 * max(oos_stdev, 1e-6)
    ramp = min(ramp_days, max(n - 1 - decay_start, 1))
    scale = sigma * math.sqrt(3.0 / 5.0)
    out: list[float] = []
    for index in range(n):
        if index < decay_start:
            mu = oos_mean
        else:
            mu = oos_mean - depth * min(float(index - decay_start) / float(ramp), 1.0)
        out.append(mu + scale * student_t(rng, df=5))
    return tuple(out)


def path_for(
    kind: str,
    rng: random.Random,
    *,
    oos_mean: float,
    oos_stdev: float,
    n: int,
    decay_start: int,
) -> tuple[float, ...]:
    if kind == "healthy_laplace":
        return healthy_laplace(rng, oos_mean=oos_mean, oos_stdev=oos_stdev, n=n)
    if kind == "abrupt_student":
        return abrupt_student(rng, oos_mean=oos_mean, oos_stdev=oos_stdev, n=n, decay_start=decay_start)
    if kind == "gradual_smooth":
        return gradual_smooth(rng, oos_mean=oos_mean, oos_stdev=oos_stdev, n=n, decay_start=decay_start)
    if kind == "high_vol_mixture":
        return high_vol_mixture(rng, oos_mean=oos_mean, oos_stdev=oos_stdev, n=n)
    if kind == "regime_laplace":
        return regime_laplace(rng, oos_mean=oos_mean, oos_stdev=oos_stdev, n=n, decay_start=decay_start)
    if kind == "material_break":
        return material_break(rng, oos_mean=oos_mean, oos_stdev=oos_stdev, n=n, decay_start=decay_start)
    ramp = SLOW_RAMPS.get(kind)
    if ramp is not None:
        return slow_gradual(
            rng, oos_mean=oos_mean, oos_stdev=oos_stdev, n=n, decay_start=decay_start, ramp_days=ramp
        )
    raise ContinuityRefused(f"unknown independent kind {kind!r}")


def decaying_kind(kind: str) -> bool:
    if kind in {"healthy_laplace", "high_vol_mixture"}:
        return False
    if kind in SHORT_DECAY_KINDS or kind in SLOW_KINDS:
        return True
    raise ContinuityRefused(f"unknown independent kind {kind!r}")


def healthy_kind(kind: str) -> Literal["healthy", "high_vol", "none"]:
    if kind == "healthy_laplace":
        return "healthy"
    if kind == "high_vol_mixture":
        return "high_vol"
    return "none"

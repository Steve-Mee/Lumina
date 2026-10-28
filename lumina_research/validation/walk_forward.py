"""Rolling and expanding walk-forward. Minimum 6 non-overlapping OOS periods."""

from __future__ import annotations

import math
import statistics
from dataclasses import dataclass
from typing import Literal, Mapping, Protocol, Sequence

from lumina_research.validation.metrics import annualized_sharpe
from lumina_research.validation.purge import purge_train_indices
from lumina_research.validation.types import WFESnapshot, freeze_params


class WalkForwardError(ValueError):
    """Fewer than the required OOS windows, or WFE cannot be formed."""


@dataclass(frozen=True, slots=True)
class WalkForwardWindow:
    is_start: int
    is_end: int
    oos_start: int
    oos_end: int
    is_index: tuple[int, ...]
    oos_index: tuple[int, ...]


@dataclass(frozen=True, slots=True)
class WindowScore:
    is_returns: tuple[float, ...]
    oos_returns: tuple[float, ...]
    parameters: Mapping[str, float]


class WindowScorer(Protocol):
    def __call__(self, window: WalkForwardWindow) -> WindowScore: ...


@dataclass(frozen=True, slots=True)
class WalkForwardConfig:
    is_size: int
    oos_size: int
    mode: Literal["rolling", "expanding"]
    embargo: int = 0
    label_horizon: int = 0
    min_oos_windows: int = 6
    periods_per_year: float = 252.0

    def __post_init__(self) -> None:
        if self.is_size < 2 or self.oos_size < 2:
            raise WalkForwardError("is_size and oos_size must be >= 2")
        if self.mode not in ("rolling", "expanding"):
            raise WalkForwardError("mode must be rolling or expanding")
        if self.embargo < 0 or self.label_horizon < 0:
            raise WalkForwardError("embargo and label_horizon must be >= 0")
        if self.min_oos_windows < 6:
            raise WalkForwardError("min_oos_windows cannot be below 6")


@dataclass(frozen=True, slots=True)
class WalkForwardResult:
    windows: tuple[WalkForwardWindow, ...]
    is_sharpes: tuple[float, ...]
    oos_sharpes: tuple[float, ...]
    oos_means: tuple[float, ...]
    wfe: WFESnapshot
    parameter_rows: tuple[Mapping[str, float], ...]


def split_walk_forward(
    n_obs: int, config: WalkForwardConfig, t1: Sequence[int] | None = None
) -> tuple[WalkForwardWindow, ...]:
    if n_obs < config.is_size + config.min_oos_windows * config.oos_size:
        raise WalkForwardError(
            f"need at least {config.is_size + config.min_oos_windows * config.oos_size} observations "
            f"for {config.min_oos_windows} non-overlapping OOS windows; got {n_obs}"
        )
    horizons = _t1(n_obs, config.label_horizon, t1)
    windows: list[WalkForwardWindow] = []
    oos_start = config.is_size + config.embargo
    while oos_start + config.oos_size <= n_obs:
        oos_end = oos_start + config.oos_size
        if config.mode == "rolling":
            is_end = oos_start - config.embargo
            is_start = is_end - config.is_size
        else:
            is_start = 0
            is_end = oos_start - config.embargo
        if is_start < 0 or is_end <= is_start:
            raise WalkForwardError("invalid IS bounds")
        oos_index = tuple(range(oos_start, oos_end))
        is_index = purge_train_indices(
            range(is_start, is_end),
            oos_index,
            horizons,
            config.embargo,
            n_obs,
        )
        if len(is_index) < 2 or len(oos_index) < 2:
            raise WalkForwardError("purge/embargo left an empty IS or OOS window")
        windows.append(
            WalkForwardWindow(
                is_start=is_start,
                is_end=is_end,
                oos_start=oos_start,
                oos_end=oos_end,
                is_index=is_index,
                oos_index=oos_index,
            )
        )
        oos_start += config.oos_size
    if len(windows) < config.min_oos_windows:
        raise WalkForwardError(
            f"formed {len(windows)} non-overlapping OOS windows; minimum is {config.min_oos_windows}"
        )
    return tuple(windows)


def run_walk_forward(
    n_obs: int,
    config: WalkForwardConfig,
    scorer: WindowScorer,
    t1: Sequence[int] | None = None,
) -> WalkForwardResult:
    windows = split_walk_forward(n_obs, config, t1=t1)
    is_sharpes: list[float] = []
    oos_sharpes: list[float] = []
    oos_means: list[float] = []
    param_rows: list[Mapping[str, float]] = []
    for window in windows:
        score = scorer(window)
        is_sharpes.append(annualized_sharpe(score.is_returns, periods_per_year=config.periods_per_year))
        oos_sharpes.append(annualized_sharpe(score.oos_returns, periods_per_year=config.periods_per_year))
        if score.oos_returns:
            oos_means.append(float(statistics.fmean(score.oos_returns)))
        else:
            oos_means.append(math.nan)
        param_rows.append(freeze_params(score.parameters))
    wfe = _wfe(
        is_sharpes=is_sharpes,
        oos_sharpes=oos_sharpes,
        mode=config.mode,
        parameter_rows=param_rows,
    )
    return WalkForwardResult(
        windows=windows,
        is_sharpes=tuple(is_sharpes),
        oos_sharpes=tuple(oos_sharpes),
        oos_means=tuple(oos_means),
        wfe=wfe,
        parameter_rows=tuple(param_rows),
    )


def static_return_scorer(returns: Sequence[float], parameters: Mapping[str, float] | None = None) -> WindowScorer:
    series = tuple(float(item) for item in returns)
    frozen = freeze_params(parameters or {})

    def _score(window: WalkForwardWindow) -> WindowScore:
        return WindowScore(
            is_returns=tuple(series[index] for index in window.is_index),
            oos_returns=tuple(series[index] for index in window.oos_index),
            parameters=frozen,
        )

    return _score


def parameter_stability(parameter_rows: Sequence[Mapping[str, float]]) -> float:
    if len(parameter_rows) < 2:
        return math.nan
    keys = set(parameter_rows[0])
    if not keys or any(set(row) != keys for row in parameter_rows):
        return math.nan
    cvs: list[float] = []
    for key in sorted(keys):
        vals = [float(row[key]) for row in parameter_rows]
        mean = float(statistics.fmean(vals))
        stdev = float(statistics.pstdev(vals)) if len(vals) >= 2 else 0.0
        if abs(mean) <= 1e-12:
            cvs.append(0.0 if stdev <= 1e-12 else 1e6)
        else:
            cvs.append(stdev / abs(mean))
    return 1.0 / (1.0 + float(statistics.fmean(cvs)))


def _wfe(
    *,
    is_sharpes: Sequence[float],
    oos_sharpes: Sequence[float],
    mode: str,
    parameter_rows: Sequence[Mapping[str, float]],
) -> WFESnapshot:
    if not is_sharpes or len(is_sharpes) != len(oos_sharpes):
        return WFESnapshot.missing()
    if any(not math.isfinite(value) for value in (*is_sharpes, *oos_sharpes)):
        return WFESnapshot(
            wfe=math.nan,
            mean_is_sharpe=float(statistics.fmean(is_sharpes)) if is_sharpes else math.nan,
            mean_oos_sharpe=float(statistics.fmean(oos_sharpes)) if oos_sharpes else math.nan,
            n_windows=len(oos_sharpes),
            mode=mode,
            parameter_stability=parameter_stability(parameter_rows),
        )
    mean_is = float(statistics.fmean(is_sharpes))
    mean_oos = float(statistics.fmean(oos_sharpes))
    if mean_is <= 0.0:
        wfe = math.nan
    else:
        wfe = mean_oos / mean_is
    return WFESnapshot(
        wfe=float(wfe) if math.isfinite(wfe) else math.nan,
        mean_is_sharpe=mean_is,
        mean_oos_sharpe=mean_oos,
        n_windows=len(oos_sharpes),
        mode=mode,
        parameter_stability=parameter_stability(parameter_rows),
    )


def _t1(n_obs: int, horizon: int, t1: Sequence[int] | None) -> tuple[int, ...]:
    if t1 is None:
        return tuple(min(n_obs, index + horizon) for index in range(n_obs))
    if len(t1) != n_obs:
        raise WalkForwardError("t1 must match n_obs")
    return tuple(int(value) for value in t1)

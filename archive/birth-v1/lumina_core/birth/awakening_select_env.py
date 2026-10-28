"""Birth-gym train env for Awakening selection: same fill/envelope/chatter functions.

Does not grow sim_runner.py. Wrapper calls the live decide/chatter/fill path so
PPO.learn() hits process-R, MES $5, clip, qty=1, envelope, refractory.
"""

from __future__ import annotations

import json
from collections.abc import Callable
from pathlib import Path
from types import SimpleNamespace
from typing import Any

import gymnasium as gym
import numpy as np

from lumina_core.birth.awakening_grind_run import occupancy_seed_kwargs, s5_envelope_kwargs
from lumina_core.birth.awakening_train_reward import (
    LIFT_WIN_BONUS_MIN_CLOSES,
    PARENT_WR_PROBE_CLOSES,
    day_mean_residual,
    median_win_r,
    resolve_entry_day,
    train_winrate,
)
from lumina_core.birth.control_plane_yield import release_control_plane
from lumina_core.logging_utils import get_logger
from lumina_core.birth.bible_observation import bible_features_for_tick
from lumina_core.birth.birth_constitution_guard import BirthConstitutionGuard
from lumina_core.birth.birth_trade_geometry import calibrate_birth_stops
from lumina_core.birth.config_curriculum import BirthCurriculumConfig
from lumina_core.birth.curriculum_types import CurriculumStage
from lumina_core.birth.force_open_plant import (
    ForceOpenChatterBound,
    apply_force_open_side,
    apply_force_open_stop,
)
from lumina_core.birth.awakening_grind import ADR0026_MIN_TRADES
from lumina_core.birth.foundation_metrics import S3_OCCUPANCY_MAX, S3_OCCUPANCY_MIN
from lumina_core.birth.foundation_occupancy_envelope import foundation_cumulative_in_band_passthrough
from lumina_core.birth.stage2_participation_envelope import (
    MODE_FORCE_EXIT,
    MODE_FORCE_OPEN,
    decide_stage2_participation,
)
from lumina_core.birth.stage3_inband_idle import (
    S3_INBAND_DEFAULT_MIN_IDLE_HOLD_BARS,
    S3InbandIdleState,
    maybe_s3_passthrough_mask,
    plant_tag_for_entry,
)
from lumina_core.rl.gym_environment import RLConfig, RLTradingEnvironment
from lumina_core.rl.gym_stop_fill import birth_force_qty_one

S5_STAGE = CurriculumStage.STAGE5_PROBE_HANDOFF
POLICY_PARTICIPATION_BONUS_R = 0.05
OVERHOLD_TAX_R = 0.01
TAPE_A_MIN_START = 60
PARENT_TAPE_A_WR_NAME = "awakening_parent_tape_a_wr.json"
PARENT_TAPE_A_WR_SCHEMA = "awakening_parent_tape_a_wr_v1"
BIRTH_TAPE_A_BOOK_NAME = "awakening_birth_tape_a_book.json"
BIRTH_TAPE_A_BOOK_SCHEMA = "awakening_birth_tape_a_book_v1"
BIRTH_TAPE_A_DAYS_NAME = "awakening_birth_tape_a_days.json"
BIRTH_TAPE_A_DAYS_SCHEMA = "awakening_birth_tape_a_days_v1"

logger = get_logger("lumina.birth.awakening_select_env")


def select_runtime() -> SimpleNamespace:
    return SimpleNamespace(
        detect_market_regime=lambda _df: "NEUTRAL",
        market_data=SimpleNamespace(get_tape_snapshot=lambda: {}),
        get_current_dream_snapshot=lambda: {},
        AI_DRAWN_FIBS={},
        world_model={},
        config=SimpleNamespace(trade_mode="birth", instrument="MES", risk_controller={}),
    )


def _enrich(data: list[dict[str, Any]], workspace_root: Any) -> list[dict[str, Any]]:
    out: list[dict[str, Any]] = []
    for row in data:
        tick = dict(row)
        c, n, s, m = bible_features_for_tick(tick, workspace_root=workspace_root)
        tick["bible_confluence"] = c
        tick["bible_news_proximity"] = n
        tick["bible_session_phase"] = s
        tick["bible_mtf_bias"] = m
        out.append(tick)
    return out


class SelectPhysicsEnv(gym.Env):
    """Gymnasium-compatible wrapper: envelope + chatter then Birth gym step."""

    metadata = {"render_modes": ["human"]}

    def __init__(
        self,
        inner: RLTradingEnvironment,
        *,
        geometry: Any,
        envelope: dict[str, Any],
        enriched: list[dict[str, Any]],
        tax_r: float = 0.0,
        train_reward_fn: Any | None = None,
    ) -> None:
        super().__init__()
        self.env = inner
        self.observation_space = inner.observation_space
        self.action_space = inner.action_space
        self.geometry = geometry
        self.envelope = envelope
        self.enriched = enriched
        # tax_r=0 keeps PR #20 path: no train-time hole tax. Exam dollars never taxed.
        self.tax_r = float(tax_r)
        self.train_reward_fn = train_reward_fn
        self.chatter = ForceOpenChatterBound()
        self.s3_idle = S3InbandIdleState()
        self.force_open_step = 0
        self.bars_in_position = 0
        self.range_flat_bars = int(envelope.get("stage_range_flat_bars") or 0)
        self.range_total_signals = int(envelope.get("stage_range_total_signals") or 0)
        self.occupancy_in_band_seen = bool(envelope.get("occupancy_in_band_seen"))
        self.entry_is_plant = False
        self.policy_trades = 0
        self.parent_tape_a_wr: float | None = None
        self.birth_median_win_r: float | None = None
        self.birth_day_means: dict[str, float] | None = None
        self._entry_day: str | None = None
        self._policy_rs: list[float] = []
        self._policy_day_closes: list[tuple[str, float]] = []
        self._policy_pnl_usd: list[float] = []
        self.record_policy_days = False
        seed_win = envelope.get("occupancy_control_window")
        self._occ_win: list[int] = list(seed_win) if isinstance(seed_win, list) else []

    def reset(self, **kwargs: Any) -> Any:
        self.chatter = ForceOpenChatterBound()
        self.s3_idle = S3InbandIdleState()
        self.force_open_step = 0
        self.bars_in_position = 0
        self.entry_is_plant = False
        self._entry_day = None
        return self.env.reset(**kwargs)

    def render(self) -> None:
        return None

    def close(self) -> None:
        close = getattr(self.env, "close", None)
        if callable(close):
            close()

    def step(self, action: Any) -> Any:
        action = np.asarray(action, dtype=np.float32)
        env = self.env
        kw = self.envelope
        part_stop = float(kw["participation_stop_pct"])
        part_target = float(kw["participation_target_pct"])
        min_dwell = int(kw["participation_min_dwell_bars"])
        band_lo = float(kw["participation_band_lo"])
        band_hi = float(kw["participation_band_hi"])
        envelope_signals = max(1, self.range_total_signals)
        envelope_flat_ratio = float(self.range_flat_bars) / float(envelope_signals)
        if band_lo - 1e-12 <= envelope_flat_ratio <= band_hi + 1e-12:
            self.occupancy_in_band_seen = True
        pos_now = int(getattr(env, "_position", 0) or 0)
        self.bars_in_position = self.bars_in_position + 1 if pos_now != 0 else 0
        occ_cap = max(50, int(kw.get("occupancy_control_window_bars") or 500))
        rolling_flat = None
        if len(self._occ_win) >= min(50, occ_cap):
            sl = self._occ_win[-occ_cap:]
            rolling_flat = float(sum(sl)) / float(max(1, len(sl)))
        decision = decide_stage2_participation(
            enabled=bool(kw["participation_envelope_enabled"]) and bool(kw["range_patience_active"]),
            range_flat_ratio=envelope_flat_ratio,
            range_total_signals=envelope_signals,
            position=pos_now,
            bars_in_position=self.bars_in_position,
            force_open_step=self.force_open_step,
            min_signals=int(kw["participation_min_signals"]),
            min_dwell_bars=min_dwell,
            band_lo=band_lo,
            band_hi=band_hi,
            hysteresis=float(kw["participation_hysteresis"]),
            under_band_release_hysteresis=float(kw.get("participation_under_band_release_hysteresis") or 0.0),
            stop_pct=part_stop,
            target_pct=part_target,
            qty_frac=0.15,
            max_hold_bars=max(20, int(getattr(self.geometry, "hold_bars", 120) or 120)),
            expectancy_gap=0.0,
            force_exit_on_sticky_under=True,
            force_exit_on_expectancy_gap=False,
            rolling_flat_ratio=rolling_flat,
            cumulative_in_band_passthrough=foundation_cumulative_in_band_passthrough(S5_STAGE.value),
            force_open_refractory=self.chatter.blocks(min_dwell),
            in_band_seen=bool(self.occupancy_in_band_seen),
            geometry_max_hold_in_band=False,
        )
        force_open_this_step = False
        idx_sel = min(int(getattr(env, "_idx", 0) or 0), len(self.enriched) - 1)
        row_sel = self.enriched[idx_sel]
        if decision.action_override is not None:
            action = np.array(decision.action_override, dtype=np.float32)
            if decision.mode == MODE_FORCE_OPEN:
                force_open_this_step = True
                self.force_open_step += 1
                action = apply_force_open_side(action, row_sel)
                action, _stop = apply_force_open_stop(
                    action,
                    row_sel,
                    self.geometry,
                    min_dwell_bars=min_dwell,
                    equity=float(getattr(env, "_equity", 0.0) or 0.0),
                )
            elif decision.mode == MODE_FORCE_EXIT:
                action = np.array([0.0, 0.5, part_stop, part_target], dtype=np.float32)
        else:
            action = maybe_s3_passthrough_mask(
                state=self.s3_idle,
                action=action,
                participation_mode=decision.mode,
                action_override=decision.action_override,
                curriculum_regime=S5_STAGE.value,
                position=pos_now,
                cumulative_flat=float(envelope_flat_ratio),
                band_lo=band_lo,
                band_hi=band_hi,
                policy_trades=self.policy_trades,
                min_idle_hold_bars=S3_INBAND_DEFAULT_MIN_IDLE_HOLD_BARS,
                policy_edge_min_trades=int(ADR0026_MIN_TRADES),
                geometry=self.geometry,
                row=row_sel,
                equity=float(getattr(env, "_equity", 0.0) or 0.0),
                min_dwell_bars=min_dwell,
                resample_hold=lambda: action,
            )
        env.config.suppress_random_flatten = bool(decision.suppress_flatten)
        env.config.participation_min_dwell_bars = min_dwell if decision.suppress_flatten else 0
        env.config.force_flatten_this_step = bool(getattr(decision, "force_flatten", False))
        env.config.force_time_stop_this_step = bool(getattr(decision, "force_time_stop", False))
        env.config.soft_prior_stops = False if force_open_this_step else True
        env.config.participation_mode = str(decision.mode)
        pos_before = int(getattr(env, "_position", 0) or 0)
        obs, reward, terminated, truncated, info = env.step(action)
        env.config.force_flatten_this_step = False
        env.config.force_time_stop_this_step = False
        env.config.soft_prior_stops = True
        pos_after = int(getattr(env, "_position", 0) or 0)
        closed = bool(info.get("trade_closed"))
        opened = pos_after != 0 or closed
        if pos_before == 0 and opened:
            self.entry_is_plant = plant_tag_for_entry(force_open_this_step=force_open_this_step)
        self._entry_day = resolve_entry_day(
            self._entry_day,
            row_sel,
            flat_before=(pos_before == 0),
            opened=opened,
        )
        if closed:
            reason = str(info.get("close_reason") or "")
            regime = str(info.get("regime") or row_sel.get("regime") or "NEUTRAL")
            info["close_reason"] = reason
            info["regime"] = regime
            process_r = float(reward)
            if self.train_reward_fn is not None:
                reward = float(self.train_reward_fn(process_r, reason, regime))
            elif abs(self.tax_r) > 0.0:
                from lumina_core.birth.awakening_hole_tax import apply_hole_tax

                reward = apply_hole_tax(process_r, reason, regime)
            plant_close = bool(self.entry_is_plant)
            entry_day = self._entry_day
            trade_r = _optional_float(info.get("trade_r"))
            if not plant_close:
                parent_mean = _parent_day_mean(self.birth_day_means, entry_day)
                residual = (
                    day_mean_residual(trade_r, parent_mean)
                    if trade_r is not None
                    else None
                )
                if residual is not None:
                    reward = residual
                reward = float(reward) + policy_participation_bonus(envelope_flat_ratio)
                if self.record_policy_days and trade_r is not None and entry_day:
                    self._policy_day_closes.append((entry_day, float(trade_r)))
                self._policy_rs.append(process_r)
            self._entry_day = None
            info["select_step_r"] = float(reward)
        hold_cap = max(20, int(getattr(self.geometry, "hold_bars", 90) or 90))
        if not bool(self.entry_is_plant):
            reward = float(reward) + overhold_train_tax(
                plant=False,
                bars_in_position=int(self.bars_in_position),
                hold_bars=hold_cap,
            )
        closed_was_plant = bool(self.entry_is_plant) if closed else False
        if closed:
            if not closed_was_plant:
                self.policy_trades += 1
            self.entry_is_plant = False
        self.chatter.on_bar(trade_closed=closed, closed_was_plant=closed_was_plant)
        tick_regime = str(row_sel.get("regime", "NEUTRAL")).upper()
        occupancy_tick = tick_regime in {"NEUTRAL", "RANGING"} or "RANGE" in tick_regime
        if occupancy_tick:
            self.range_total_signals += 1
            if pos_after == 0:
                self.range_flat_bars += 1
            self._occ_win.append(1 if pos_after == 0 else 0)
            if len(self._occ_win) > occ_cap:
                del self._occ_win[:-occ_cap]
        if pos_after == 0:
            self.bars_in_position = 0
        return obs, reward, terminated, truncated, info


def overhold_train_tax(*, plant: bool, bars_in_position: int, hold_bars: int) -> float:
    """Train-only: tax policy holds longer than geometry. Never plant. Eval untouched."""
    if plant:
        return 0.0
    cap = max(20, int(hold_bars or 90))
    if int(bars_in_position) <= cap:
        return 0.0
    return -abs(float(OVERHOLD_TAX_R))


def policy_participation_bonus(occupancy: float | None) -> float:
    """Train-only process bonus for policy closes in the exam band. Never plant."""
    if occupancy is None:
        return 0.0
    occ = float(occupancy)
    if S3_OCCUPANCY_MIN - 1e-12 <= occ <= S3_OCCUPANCY_MAX + 1e-12:
        return float(POLICY_PARTICIPATION_BONUS_R)
    return 0.0


def _optional_float(value: Any) -> float | None:
    if value is None or value == "":
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def _parent_day_mean(book: dict[str, float] | None, day: str | None) -> float | None:
    """Unknown book or unknown day stays unknown. A stored mean of 0 is real."""
    if book is None or not day:
        return None
    if day not in book:
        return None
    return float(book[day])


def parent_tape_a_wr_path(reports_dir: Path | str) -> Path:
    return Path(reports_dir) / PARENT_TAPE_A_WR_NAME


def birth_tape_a_book_path(reports_dir: Path | str) -> Path:
    return Path(reports_dir) / BIRTH_TAPE_A_BOOK_NAME


def birth_tape_a_days_path(reports_dir: Path | str) -> Path:
    return Path(reports_dir) / BIRTH_TAPE_A_DAYS_NAME


def bind_parent_tape_a_wr(
    env: Any,
    model: Any,
    *,
    parent_path: Path,
    reports_dir: Path,
    should_stop: Callable[[], bool] | None = None,
    on_step: Callable[[int], None] | None = None,
) -> tuple[float | None, bool]:
    """Freeze the parent's tape-A winrate onto ``env``. Holdout is not an argument.

    One measurement per parent sha. A cache hit does not step. ``stopped`` means
    the caller asked to halt before the probe finished; that result is not cached.
    """
    from lumina_core.birth.birth_exit_policy_export import file_sha256

    sha = file_sha256(Path(parent_path)) if Path(parent_path).is_file() else ""
    cached = _read_parent_wr_cache(parent_tape_a_wr_path(reports_dir), sha)
    if cached is not None:
        env.parent_tape_a_wr = cached[0]
        logger.info(
            "awakening.parent_tape_a_wr cache wr=%s n=%s sha=%s",
            cached[0],
            cached[1],
            sha[:12],
        )
        return cached[0], False
    series, _days, stopped = _probe_parent_tape_a_series(
        env,
        model,
        should_stop=should_stop,
        on_step=on_step,
    )
    if stopped:
        env.parent_tape_a_wr = None
        return None, True
    n_closes = len(series)
    wr = train_winrate(series) if n_closes >= int(LIFT_WIN_BONUS_MIN_CLOSES) else None
    _write_parent_wr_cache(
        parent_tape_a_wr_path(reports_dir),
        sha=sha,
        wr=wr,
        n_closes=n_closes,
    )
    env.parent_tape_a_wr = wr
    logger.info(
        "awakening.parent_tape_a_wr probed wr=%s n=%s sha=%s",
        wr,
        n_closes,
        sha[:12],
    )
    return wr, False


def bind_birth_tape_a_median(
    env: Any,
    model: Any,
    *,
    parent_path: Path,
    reports_dir: Path,
    should_stop: Callable[[], bool] | None = None,
    on_step: Callable[[int], None] | None = None,
) -> tuple[float | None, bool]:
    """Predict-only median win of frozen Birth on tape A. Does not call ``learn``.

    Cached by the pin zip sha. A missing or short book leaves the median unknown
    and the train tax off. Holdout B is not an argument.
    """
    from lumina_core.birth.birth_exit_policy_export import file_sha256

    sha = file_sha256(Path(parent_path)) if Path(parent_path).is_file() else ""
    cached = _read_birth_book_cache(birth_tape_a_book_path(reports_dir), sha)
    if cached is not None:
        env.birth_median_win_r = cached[0]
        logger.info(
            "awakening.birth_tape_a_median cache median=%s sha=%s",
            cached[0],
            sha[:12],
        )
        return cached[0], False
    series, _days, stopped = _probe_parent_tape_a_series(
        env,
        model,
        should_stop=should_stop,
        on_step=on_step,
    )
    if stopped:
        env.birth_median_win_r = None
        return None, True
    median = _median_if_known(series)
    _write_birth_book_cache(
        birth_tape_a_book_path(reports_dir),
        sha=sha,
        median_win_r=median,
        n_closes=len(series),
        n_wins=sum(1 for r in series if float(r) > 0.0),
    )
    env.birth_median_win_r = median
    logger.info(
        "awakening.birth_tape_a_median probed median=%s n=%s sha=%s",
        median,
        len(series),
        sha[:12],
    )
    return median, False


def bind_birth_tape_a_days(
    env: Any,
    model: Any,
    *,
    parent_path: Path,
    reports_dir: Path,
    should_stop: Callable[[], bool] | None = None,
    on_step: Callable[[int], None] | None = None,
    step_cap: int | None = None,
) -> tuple[dict[str, float] | None, bool]:
    """Predict-only Birth trade_R by session day on tape A. Does not call ``learn``.

    Cached by the pin zip sha. A stopped walk is not cached. A day with no
    parent close stays absent. Holdout B is not an argument.
    """
    from lumina_core.birth.birth_exit_policy_export import file_sha256

    sha = file_sha256(Path(parent_path)) if Path(parent_path).is_file() else ""
    cached = _read_birth_days_cache(birth_tape_a_days_path(reports_dir), sha)
    if cached is not None:
        env.birth_day_means = cached
        logger.info(
            "awakening.birth_tape_a_days cache days=%s sha=%s",
            len(cached),
            sha[:12],
        )
        return cached, False
    # PPO learns `step_cap` bars from the reset. Day means outside that window
    # never meet a child close. None still walks the whole tape.
    _series, closes, stopped = _probe_parent_tape_a_series(
        env,
        model,
        should_stop=should_stop,
        on_step=on_step,
        close_cap=0,
        step_cap=0 if step_cap is None else int(step_cap),
        start_index=0,
    )
    if stopped:
        env.birth_day_means = None
        return None, True
    means = _day_means(closes)
    _write_birth_days_cache(
        birth_tape_a_days_path(reports_dir),
        sha=sha,
        means=means,
        n_closes=len(closes),
    )
    env.birth_day_means = means
    logger.info(
        "awakening.birth_tape_a_days probed days=%s closes=%s sha=%s",
        len(means),
        len(closes),
        sha[:12],
    )
    return means, False


def _day_means(closes: list[tuple[str, float]]) -> dict[str, float]:
    buckets: dict[str, list[float]] = {}
    for day, trade_r in closes:
        if not day:
            continue
        buckets.setdefault(str(day), []).append(float(trade_r))
    return {day: sum(values) / len(values) for day, values in buckets.items() if values}


def _median_if_known(series: list[float]) -> float | None:
    from lumina_core.birth.awakening_train_reward import MEDIAN_WIN_TAX_MIN_CLOSES, MEDIAN_WIN_TAX_MIN_WINS

    if len(series) < int(MEDIAN_WIN_TAX_MIN_CLOSES):
        return None
    if sum(1 for r in series if float(r) > 0.0) < int(MEDIAN_WIN_TAX_MIN_WINS):
        return None
    return median_win_r(series)


def _read_parent_wr_cache(path: Path, sha: str) -> tuple[float | None, int] | None:
    if not sha or not path.is_file():
        return None
    try:
        raw = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError, TypeError):
        return None
    if not isinstance(raw, dict) or str(raw.get("parent_sha256") or "") != sha:
        return None
    if raw.get("schema") != PARENT_TAPE_A_WR_SCHEMA or "wr" not in raw:
        return None
    n_closes = int(raw.get("n_closes") or 0)
    wr_raw = raw.get("wr")
    if wr_raw is None:
        return None, n_closes
    try:
        return float(wr_raw), n_closes
    except (TypeError, ValueError):
        return None


def _write_parent_wr_cache(
    path: Path,
    *,
    sha: str,
    wr: float | None,
    n_closes: int,
) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    payload = {
        "schema": PARENT_TAPE_A_WR_SCHEMA,
        "parent_sha256": sha,
        "wr": wr,
        "n_closes": int(n_closes),
    }
    path.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")


def _read_birth_days_cache(path: Path, sha: str) -> dict[str, float] | None:
    """``None`` is a miss. An empty dict is a probed book with no dated closes."""
    if not sha or not path.is_file():
        return None
    try:
        raw = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError, TypeError):
        return None
    if not isinstance(raw, dict) or str(raw.get("parent_sha256") or "") != sha:
        return None
    if raw.get("schema") != BIRTH_TAPE_A_DAYS_SCHEMA or not isinstance(raw.get("days"), dict):
        return None
    means: dict[str, float] = {}
    for day, value in raw["days"].items():
        if not isinstance(day, str) or len(day) < 10:
            continue
        try:
            means[day[:10]] = float(value)
        except (TypeError, ValueError):
            return None
    return means


def _write_birth_days_cache(
    path: Path,
    *,
    sha: str,
    means: dict[str, float],
    n_closes: int,
) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    payload = {
        "schema": BIRTH_TAPE_A_DAYS_SCHEMA,
        "parent_sha256": sha,
        "n_closes": int(n_closes),
        "days": {day: float(mean) for day, mean in sorted(means.items())},
    }
    path.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")


def _read_birth_book_cache(path: Path, sha: str) -> tuple[float | None] | None:
    """``None`` is a miss. A tuple holds the cached median, which may itself be unknown."""
    if not sha or not path.is_file():
        return None
    try:
        raw = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError, TypeError):
        return None
    if not isinstance(raw, dict) or str(raw.get("parent_sha256") or "") != sha:
        return None
    if raw.get("schema") != BIRTH_TAPE_A_BOOK_SCHEMA or "median_win_r" not in raw:
        return None
    median_raw = raw.get("median_win_r")
    if median_raw is None:
        return (None,)
    try:
        return (float(median_raw),)
    except (TypeError, ValueError):
        return None


def _write_birth_book_cache(
    path: Path,
    *,
    sha: str,
    median_win_r: float | None,
    n_closes: int,
    n_wins: int,
) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    payload = {
        "schema": BIRTH_TAPE_A_BOOK_SCHEMA,
        "parent_sha256": sha,
        "median_win_r": median_win_r,
        "n_closes": int(n_closes),
        "n_wins": int(n_wins),
    }
    path.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")


def _capture_train_counters(env: Any) -> dict[str, Any]:
    snap: dict[str, Any] = {}
    for name in (
        "policy_trades",
        "range_flat_bars",
        "range_total_signals",
        "occupancy_in_band_seen",
    ):
        if hasattr(env, name):
            snap[name] = getattr(env, name)
    if hasattr(env, "_occ_win"):
        snap["_occ_win"] = list(env._occ_win)
    if hasattr(env, "_policy_rs"):
        snap["_policy_rs"] = list(env._policy_rs)
    if hasattr(env, "_policy_day_closes"):
        snap["_policy_day_closes"] = list(env._policy_day_closes)
    if hasattr(env, "_policy_pnl_usd"):
        snap["_policy_pnl_usd"] = list(env._policy_pnl_usd)
    if hasattr(env, "record_policy_days"):
        snap["record_policy_days"] = bool(env.record_policy_days)
    if hasattr(env, "_entry_day"):
        snap["_entry_day"] = env._entry_day
    return snap


def _restore_train_counters(env: Any, snap: dict[str, Any]) -> None:
    for name, value in snap.items():
        if name in {"_occ_win", "_policy_rs", "_policy_pnl_usd", "_policy_day_closes"}:
            setattr(env, name, list(value))
        else:
            setattr(env, name, value)


def _probe_parent_tape_a_series(
    env: Any,
    model: Any,
    *,
    should_stop: Callable[[], bool] | None,
    on_step: Callable[[int], None] | None,
    close_cap: int | None = None,
    step_cap: int = 0,
    start_index: int | None = None,
) -> tuple[list[float], list[tuple[str, float]], bool]:
    """Predict-only walk on the train env. Does not call ``learn``.

    The second list is ``(session_day, trade_r)`` when the env records it.
    A shaped gym reward is not that trade_R.
    """
    snap = _capture_train_counters(env)
    stopped = False
    if hasattr(env, "record_policy_days"):
        env.record_policy_days = True
    try:
        reset_out = env.reset()
        if hasattr(env, "_policy_day_closes"):
            env._policy_day_closes = []
        obs = reset_out[0] if isinstance(reset_out, tuple) else reset_out
        enriched = getattr(env, "enriched", None)
        n_bars = len(enriched) if isinstance(enriched, list) else 0
        inner = getattr(env, "env", None)
        if inner is not None and hasattr(inner, "_idx") and n_bars > 0:
            start = TAPE_A_MIN_START if start_index is None else int(start_index)
            inner._idx = min(max(0, start), n_bars - 1)
        limit = max(1, n_bars)
        cap = int(PARENT_WR_PROBE_CLOSES if close_cap is None else close_cap)
        bar_cap = int(step_cap)
        steps = 0
        while (
            steps < limit
            and (cap <= 0 or len(getattr(env, "_policy_rs", [])) < cap)
            and (bar_cap <= 0 or steps < bar_cap)
        ):
            if should_stop is not None and should_stop():
                stopped = True
                break
            predicted = model.predict(obs, deterministic=True)
            action = predicted[0] if isinstance(predicted, tuple) else predicted
            stepped = env.step(action)
            obs = stepped[0]
            terminated = bool(stepped[2]) if len(stepped) > 2 else False
            truncated = bool(stepped[3]) if len(stepped) > 3 else False
            steps += 1
            release_control_plane(steps)
            if on_step is not None and (steps == 1 or steps % 1024 == 0):
                on_step(steps)
            if terminated or truncated:
                break
        closes = list(getattr(env, "_policy_day_closes", []))
        return list(getattr(env, "_policy_rs", [])), closes, stopped
    finally:
        _restore_train_counters(env, snap)
        reset = getattr(env, "reset", None)
        if callable(reset):
            reset()


def make_select_train_env(
    data: list[dict[str, Any]],
    *,
    workspace_root: Any,
    reports_dir: Any,
    max_steps: int,
    tax_r: float = 0.0,
    train_reward_fn: Any | None = None,
) -> SelectPhysicsEnv:
    if not data:
        raise RuntimeError("select train tape empty")
    enriched = _enrich(data, workspace_root)
    geometry = calibrate_birth_stops(enriched)
    cfg_cur = BirthCurriculumConfig()
    envelope = s5_envelope_kwargs(cfg_cur, geometry)
    envelope.update(occupancy_seed_kwargs(reports_dir, workspace_root=workspace_root))
    rl_cfg = RLConfig(
        trade_mode="birth",
        max_steps=int(max_steps),
        range_patience_active=True,
        default_stop_pct=float(geometry.stop_pct),
        default_target_pct=float(geometry.target_pct),
        soft_prior_stops=True,
        curriculum_regime=S5_STAGE.value,
        force_qty_one=bool(birth_force_qty_one(S5_STAGE.value)),
        participation_band_lo=float(envelope["participation_band_lo"]),
        participation_band_hi=float(envelope["participation_band_hi"]),
    )
    inner = RLTradingEnvironment(select_runtime(), enriched, config=rl_cfg)
    inner.set_birth_context(workspace_root=workspace_root, constitution_guard=BirthConstitutionGuard())
    return SelectPhysicsEnv(
        inner,
        geometry=geometry,
        envelope=envelope,
        enriched=enriched,
        tax_r=float(tax_r),
        train_reward_fn=train_reward_fn,
    )


__all__ = [
    "OVERHOLD_TAX_R",
    "POLICY_PARTICIPATION_BONUS_R",
    "SelectPhysicsEnv",
    "bind_birth_tape_a_days",
    "bind_birth_tape_a_median",
    "bind_parent_tape_a_wr",
    "make_select_train_env",
    "overhold_train_tax",
    "policy_participation_bonus",
    "select_runtime",
]

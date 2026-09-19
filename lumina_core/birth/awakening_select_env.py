"""Birth-gym train env for Awakening selection: same fill/envelope/chatter functions.

Does not grow sim_runner.py. Wrapper calls the live decide/chatter/fill path so
PPO.learn() hits process-R, MES $5, clip, qty=1, envelope, refractory.
"""

from __future__ import annotations

from types import SimpleNamespace
from typing import Any

import gymnasium as gym
import numpy as np

from lumina_core.birth.awakening_grind_run import occupancy_seed_kwargs, s5_envelope_kwargs
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
        seed_win = envelope.get("occupancy_control_window")
        self._occ_win: list[int] = list(seed_win) if isinstance(seed_win, list) else []

    def reset(self, **kwargs: Any) -> Any:
        self.chatter = ForceOpenChatterBound()
        self.s3_idle = S3InbandIdleState()
        self.force_open_step = 0
        self.bars_in_position = 0
        self.entry_is_plant = False
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
        if pos_before == 0 and pos_after != 0:
            self.entry_is_plant = plant_tag_for_entry(force_open_this_step=force_open_this_step)
        closed = bool(info.get("trade_closed"))
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
            if not plant_close:
                reward = float(reward) + policy_participation_bonus(envelope_flat_ratio)
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
    "make_select_train_env",
    "overhold_train_tax",
    "policy_participation_bonus",
    "select_runtime",
]

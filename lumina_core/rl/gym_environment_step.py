"""step() mixin for RLTradingEnvironment (M5)."""
from __future__ import annotations


import numpy as np

from lumina_core.rl.reward_shaper import (
    TradeCloseContext,
    compute_expectancy_reward,
    compute_legacy_reward,
    hold_action_penalty,
    range_patience_step_reward,
    trend_features_from_tick,
    update_trade_stats,
)


class RLTradingEnvironmentStepMixin:
    """Gymnasium step transition (extracted for LOC hygiene)."""

    def step(self, action):
        reward = 0.0
        action_arr = np.asarray(action, dtype=np.float32)
        if self._idx >= len(self.data) - 1:
            return self._get_observation(), 0.0, True, False, {}

        row = self.data[self._idx]
        price = float(row.get("close", row.get("last", 0.0)))
        if price <= 0.0:
            self._idx += 1
            return self._get_observation(), -0.01, False, False, {"skip": "invalid_price"}

        side_bucket = int(np.clip(np.round(action_arr[0]), 0, 2))
        side = 0 if side_bucket == 0 else (1 if side_bucket == 1 else -1)
        qty = max(1, int(1 + np.clip(action_arr[1], 0.0, 1.0) * 9))
        stop_pct = float(np.clip(action_arr[2], 0.001, 0.02))
        target_pct = float(np.clip(action_arr[3], 0.001, 0.05))

        realized_pnl = 0.0
        slippage_cost = 0.0
        fees_cost = 0.0
        blocked_by_capital_preservation = False
        block_reason = ""

        if self._position == 0 and side != 0:
            # Birth SIM: clip stop/target into 1% band then check — policy learns
            # the action that actually executes (prepare_entry preferred path).
            if self.trade_mode == "birth" and self._birth_constitution_guard is not None:
                tick_row = self.data[min(self._idx, len(self.data) - 1)]
                prepare = getattr(self._birth_constitution_guard, "prepare_entry", None)
                if callable(prepare):
                    allowed, _reason, stop_pct, target_pct = prepare(
                        tick=tick_row,
                        side=side,
                        stop_pct=stop_pct,
                        target_pct=target_pct,
                        equity=self._equity,
                    )
                else:
                    allowed, _reason = self._birth_constitution_guard.check_entry(
                        tick=tick_row,
                        side=side,
                        stop_pct=stop_pct,
                        equity=self._equity,
                    )
                if not allowed:
                    blocked_by_capital_preservation = True
                    block_reason = "birth_constitution_blocked"
                    reward -= 2.0
                    self._idx += 1
                    return self._get_observation(), reward, False, False, {
                        "blocked_by_birth_constitution": True,
                        "block_reason": block_reason,
                    }

            slippage_points = self._stochastic_slippage_points(price)
            entry_ticks = max(0.0, float(slippage_points) / max(self.valuation_engine.tick_size(self.instrument), 1e-9))
            fill = self.valuation_engine.apply_entry_fill(
                symbol=self.instrument,
                price=price,
                side=side,
                slippage_ticks=entry_ticks,
            )
            entry_slippage_cost = abs(fill - price) * qty * self.valuation_engine.point_value(self.instrument)
            entry_fees = self._fees_usd(quantity=qty, sides=1)

            if self.trade_mode == "real":
                safety_floor = max(
                    float(self.config.real_safety_threshold_usd),
                    float(self._initial_equity * float(self.config.real_safety_threshold_ratio)),
                )
                projected_equity = float(self._equity - entry_slippage_cost - entry_fees)
                if projected_equity < safety_floor:
                    blocked_by_capital_preservation = True
                    block_reason = (
                        "REAL fail-closed: projected net below safety threshold "
                        f"({projected_equity:.2f} < {safety_floor:.2f})"
                    )
                else:
                    self._position = side
                    self._qty = qty
                    self._entry_price = fill
                    slippage_cost += entry_slippage_cost
                    fees_cost += entry_fees
                    self._entry_stop_pct = stop_pct
                    self._entry_target_pct = target_pct
                    self._entry_side = side
                    self._bars_held = 0
            else:
                self._position = side
                self._qty = qty
                self._entry_price = fill
                slippage_cost += entry_slippage_cost
                fees_cost += entry_fees
                self._entry_stop_pct = stop_pct
                self._entry_target_pct = target_pct
                self._entry_side = side
                self._bars_held = 0

        trade_closed = False
        close_side = 0
        close_stop_pct = self._entry_stop_pct
        if self._position != 0:
            # Exit levels MUST use entry stops — live action stop was collapsing
            # holds immediately and drove Stage-2 position_flat to ~95%+.
            entry_stop = float(getattr(self, "_entry_stop_pct", 0.0) or stop_pct or 0.0075)
            entry_target = float(
                getattr(self, "_entry_target_pct", 0.0) or target_pct or max(entry_stop * 2.0, 0.01)
            )
            stop = self._entry_price * (
                1.0 - entry_stop if self._position > 0 else 1.0 + entry_stop
            )
            target = self._entry_price * (
                1.0 + entry_target if self._position > 0 else 1.0 - entry_target
            )

            hit_stop = (self._position > 0 and price <= stop) or (self._position < 0 and price >= stop)
            hit_target = (self._position > 0 and price >= target) or (self._position < 0 and price <= target)
            # Random flatten only when not fighting under-activity (over-flat band).
            flat_ratio_now = 0.5
            if int(getattr(self, "_range_total_bars", 0) or 0) > 0:
                flat_ratio_now = float(self._range_flat_bars) / float(
                    max(1, self._range_total_bars)
                )
            flatten_p = 0.05
            if self.config.range_patience_active and flat_ratio_now > 0.70:
                flatten_p = 0.0
            if bool(getattr(self.config, "suppress_random_flatten", False)):
                flatten_p = 0.0
            flatten = side == 0 and np.random.random() < flatten_p

            # Stage2 Participation Envelope occupancy law: while correcting
            # over-flat, force min dwell so stop/slippage cannot wipe FORCE_OPEN
            # in the same bar (live forensics: force_open≫0, force_hold=0, flat≈95%).
            min_dwell = max(0, int(getattr(self.config, "participation_min_dwell_bars", 0) or 0))
            bars_held = max(0, int(getattr(self, "_bars_held", 0) or 0))
            if (
                bool(getattr(self.config, "suppress_random_flatten", False))
                and min_dwell > 0
                and bars_held < min_dwell
            ):
                hit_stop = False
                hit_target = False
                flatten = False

            if hit_stop or hit_target or flatten:
                close_side = self._entry_side
                close_stop_pct = self._entry_stop_pct
                trade_closed = True
                exit_ticks = max(
                    0.0,
                    float(self._stochastic_slippage_points(price))
                    / max(self.valuation_engine.tick_size(self.instrument), 1e-9),
                )
                exit_fill = self.valuation_engine.apply_exit_fill(
                    symbol=self.instrument,
                    price=price,
                    side=self._position,
                    slippage_ticks=exit_ticks,
                )
                slippage_cost += abs(exit_fill - price) * self._qty * self.valuation_engine.point_value(self.instrument)
                fees_cost += self._fees_usd(quantity=self._qty, sides=1)
                realized_pnl = self.valuation_engine.pnl_dollars(
                    symbol=self.instrument,
                    entry_price=self._entry_price,
                    exit_price=exit_fill,
                    side=self._position,
                    quantity=self._qty,
                )
                self._position = 0
                self._qty = 0
                self._entry_price = 0.0
                self._entry_stop_pct = 0.0075
                self._entry_target_pct = 0.015
                self._bars_held = 0
            else:
                # Completed a bar in position (for envelope min-dwell protect).
                self._bars_held = max(0, int(getattr(self, "_bars_held", 0) or 0)) + 1

        prev_equity = self._equity
        self._equity += realized_pnl - slippage_cost - fees_cost
        # Birth SIM plant floor: prevent equity death-spiral that soft-blocks all
        # entries via inverted risk checks and freezes occupancy recovery.
        if self.trade_mode == "birth":
            floor_ratio = float(getattr(self.config, "birth_equity_floor_ratio", 0.10) or 0.10)
            floor_ratio = max(0.01, min(0.50, floor_ratio))
            equity_floor = float(self._initial_equity) * floor_ratio
            if self._equity < equity_floor:
                self._equity = equity_floor
        self._equity_curve.append(self._equity)

        ret = (self._equity - prev_equity) / max(prev_equity, 1e-6)
        self._returns.append(ret)

        var_es_penalty = 0.0
        risk_controller = getattr(self.engine, "risk_controller", None)
        if self.trade_mode == "sim" and risk_controller is not None and hasattr(risk_controller, "get_var_es_snapshot"):
            snapshot = risk_controller.get_var_es_snapshot(proposed_risk=0.0)
            limits = getattr(risk_controller, "_active_limits", None)
            var_limit = max(float(getattr(limits, "var_95_limit_usd", 1.0) or 1.0), 1.0)
            es_limit = max(float(getattr(limits, "es_95_limit_usd", 1.0) or 1.0), 1.0)
            var_ratio = float(snapshot.get("var_95_usd", 0.0) or 0.0) / var_limit
            es_ratio = float(snapshot.get("es_95_usd", 0.0) or 0.0) / es_limit
            var_es_penalty = float(self.config.sim_var_penalty_coeff) * max(0.0, var_ratio) + float(
                self.config.sim_es_penalty_coeff
            ) * max(0.0, es_ratio)

        rl_close_accounting_net_usd = float(realized_pnl - slippage_cost - fees_cost)
        reward_components: dict[str, float] = {}

        if self._uses_expectancy_reward():
            if trade_closed:
                trend_strength, atr_norm = trend_features_from_tick(row)
                self._reward_state.drawdown = self._drawdown()
                self._reward_state.sharpe = self._rolling_sharpe()
                ctx = TradeCloseContext(
                    net_pnl=rl_close_accounting_net_usd,
                    equity=prev_equity,
                    stop_pct=close_stop_pct,
                    side=close_side,
                    trend_regime_strength=trend_strength,
                    trend_atr_norm=atr_norm,
                    var_es_penalty=var_es_penalty,
                )
                reward, reward_components = compute_expectancy_reward(
                    ctx,
                    self._reward_state,
                    self._reward_cfg(),
                )
                update_trade_stats(
                    self._reward_state,
                    rl_close_accounting_net_usd,
                    window=self._reward_cfg().rolling_trade_window,
                )
            else:
                reward = -var_es_penalty if var_es_penalty > 0 else 0.0
        else:
            reward_cfg = self._reward_cfg()
            reward = compute_legacy_reward(
                net_pnl=rl_close_accounting_net_usd,
                drawdown=self._drawdown(),
                sharpe=self._rolling_sharpe(),
                drawdown_penalty_coeff=reward_cfg.drawdown_penalty_coeff,
                sharpe_bonus_coeff=reward_cfg.sharpe_bonus_coeff,
                var_es_penalty=var_es_penalty,
            )

        if blocked_by_capital_preservation:
            reward -= 5.0

        if side_bucket == 0 and self.config.plateau_active:
            tick_regime = str(row.get("regime", "NEUTRAL"))
            reward += hold_action_penalty(
                is_hold=True,
                regime=tick_regime,
                plateau_active=True,
                coeff=float(self.config.hold_penalty_coeff),
            )

        if self.config.range_patience_active and self.trade_mode == "birth":
            tick_regime = str(row.get("regime", "NEUTRAL"))
            is_range_tick = (
                str(tick_regime).upper() in {"NEUTRAL", "RANGING"}
                or "RANGE" in str(tick_regime).upper()
            )
            if is_range_tick:
                self._range_total_bars = int(getattr(self, "_range_total_bars", 0) or 0) + 1
                if int(self._position) == 0:
                    self._range_flat_bars = int(getattr(self, "_range_flat_bars", 0) or 0) + 1
            stage_flat_ratio = None
            if int(getattr(self, "_range_total_bars", 0) or 0) >= 20:
                stage_flat_ratio = float(self._range_flat_bars) / float(
                    max(1, self._range_total_bars)
                )
            # Expectancy gap (WR−0.50 vs floor): prefer stage seed from sim_runner,
            # else estimate from recent closed trades in this episode.
            reward_cfg = self._reward_cfg()
            exp_floor = float(getattr(self.config, "stage2_expectancy_floor", -0.15) or -0.15)
            exp_gap = float(getattr(self.config, "expectancy_gap", 0.0) or 0.0)
            recent = list(getattr(self._reward_state, "recent_pnls", []) or [])
            if len(recent) >= 20:
                wr = float(sum(1 for p in recent if float(p) > 0.0)) / float(len(recent))
                live_exp = wr - 0.50
                exp_gap = max(exp_gap, max(0.0, exp_floor - live_exp))
            trade_r = None
            if trade_closed:
                risk_usd = max(
                    float(reward_cfg.min_risk_usd),
                    float(prev_equity) * max(float(close_stop_pct), 1e-6),
                )
                trade_r = float(rl_close_accounting_net_usd) / max(risk_usd, 1e-6)
            reward += range_patience_step_reward(
                regime=tick_regime,
                position_flat=int(self._position) == 0,
                trade_closed=bool(trade_closed),
                cfg=reward_cfg,
                stage_flat_ratio=stage_flat_ratio,
                expectancy_gap=exp_gap,
                trade_r_multiple=trade_r,
            )

        self._idx += 1
        terminated = self._idx >= min(len(self.data) - 1, self.config.max_steps)

        training_reward = float(reward)
        info = {
            "model_close_gross_pnl_usd": realized_pnl,
            "rl_close_accounting_net_usd": rl_close_accounting_net_usd,
            "training_reward": training_reward,
            "slippage_cost": slippage_cost,
            "fees_cost": fees_cost,
            "equity": self._equity,
            "drawdown": self._drawdown(),
            "sharpe": self._rolling_sharpe(),
            "var_es_penalty": var_es_penalty,
            "reward_components": reward_components,
            "trade_closed": trade_closed,
            "blocked_by_capital_preservation": blocked_by_capital_preservation,
            "block_reason": block_reason,
        }
        return self._get_observation(), reward, terminated, False, info


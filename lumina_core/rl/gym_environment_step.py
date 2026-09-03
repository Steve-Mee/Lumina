"""step() mixin for RLTradingEnvironment (M5)."""
from __future__ import annotations


import numpy as np

from lumina_core.rl.reward_shaper import (
    TradeCloseContext,
    compute_expectancy_reward,
    compute_legacy_reward,
    hold_action_penalty,
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
        is_birth = str(self.trade_mode or "").lower() == "birth"
        if not is_birth:
            is_birth = str(getattr(self.config, "trade_mode", "") or "").lower() == "birth"
        close_gap = False
        qty = max(1, int(1 + np.clip(action_arr[1], 0.0, 1.0) * 9))
        if is_birth and bool(getattr(self.config, "force_qty_one", False)):
            qty = 1
        try:
            from lumina_core.birth.birth_constitution_guard import BIRTH_MIN_STOP_PCT

            _stop_lo = float(BIRTH_MIN_STOP_PCT)
        except Exception:
            _stop_lo = 0.0004
        stop_pct = float(np.clip(action_arr[2], _stop_lo, 0.02))
        target_pct = float(np.clip(action_arr[3], _stop_lo * 1.25, 0.05))
        # Birth soft-prior: pull macro stops toward calibrated default geometry.
        if (
            self.trade_mode == "birth"
            and bool(getattr(self.config, "soft_prior_stops", True))
            and side != 0
        ):
            try:
                from lumina_core.birth.birth_trade_geometry import (
                    SOFT_PRIOR_DEFAULT_MULTIPLE,
                )

                _soft_mult = float(SOFT_PRIOR_DEFAULT_MULTIPLE)
            except Exception:
                _soft_mult = 2.5
            cal_s = float(getattr(self.config, "default_stop_pct", 0.0012) or 0.0012)
            cal_t = float(getattr(self.config, "default_target_pct", 0.0020) or 0.0020)
            if stop_pct > cal_s * _soft_mult:
                stop_pct = min(stop_pct, cal_s * _soft_mult)
            if stop_pct < max(_stop_lo, cal_s / _soft_mult):
                stop_pct = max(_stop_lo, cal_s / _soft_mult)
            if target_pct < stop_pct * 1.25:
                target_pct = stop_pct * 1.25
            if target_pct > cal_t * _soft_mult * 1.5:
                target_pct = cal_t * _soft_mult

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
                allowed = False
                _reason = "birth_constitution_unresolved"
                prepare = getattr(self._birth_constitution_guard, "prepare_entry", None)
                if callable(prepare):
                    prepared = prepare(
                        tick=tick_row,
                        side=side,
                        stop_pct=stop_pct,
                        target_pct=target_pct,
                        equity=self._equity,
                        qty=qty,
                    )
                    if isinstance(prepared, tuple) and len(prepared) >= 4:
                        allowed = bool(prepared[0])
                        _reason = str(prepared[1] or "")
                        stop_pct = float(prepared[2])
                        target_pct = float(prepared[3])
                    else:
                        allowed, _reason = self._birth_constitution_guard.check_entry(
                            tick=tick_row,
                            side=side,
                            stop_pct=stop_pct,
                            equity=self._equity,
                            qty=qty,
                        )
                else:
                    allowed, _reason = self._birth_constitution_guard.check_entry(
                        tick=tick_row,
                        side=side,
                        stop_pct=stop_pct,
                        equity=self._equity,
                        qty=qty,
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
        close_reason = ""
        if self._position != 0:
            # Exit levels MUST use entry stops — live action stop was collapsing
            # holds immediately and drove Stage-2 position_flat to ~95%+.
            def_stop = float(getattr(self.config, "default_stop_pct", 0.0012) or 0.0012)
            def_target = float(getattr(self.config, "default_target_pct", 0.0020) or 0.0020)
            entry_stop = float(getattr(self, "_entry_stop_pct", 0.0) or stop_pct or def_stop)
            entry_target = float(
                getattr(self, "_entry_target_pct", 0.0)
                or target_pct
                or max(entry_stop * 1.25, def_target)
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
            # Birth SIM: never RNG-exit. Live forensics 2026-08-13: 5%/HOLD-bar
            # made mean hold ~17 bars vs geometry 120; WR measured MTM theater.
            flat_ratio_now = 0.5
            if int(getattr(self, "_range_total_bars", 0) or 0) > 0:
                flat_ratio_now = float(self._range_flat_bars) / float(
                    max(1, self._range_total_bars)
                )
            flatten_p = 0.0 if is_birth else 0.05
            if self.config.range_patience_active and flat_ratio_now > 0.70:
                flatten_p = 0.0
            if bool(getattr(self.config, "suppress_random_flatten", False)):
                flatten_p = 0.0
            # Occupancy plant flatten (legacy) vs geometry time-stop (honest PnL).
            force_flat_now = bool(getattr(self.config, "force_flatten_this_step", False))
            force_time_now = bool(getattr(self.config, "force_time_stop_this_step", False))
            flatten = (
                force_flat_now
                or force_time_now
                or (side == 0 and np.random.random() < flatten_p)
            )

            # Occupancy min-dwell may suppress RNG flatten — never the stop/target.
            min_dwell = max(0, int(getattr(self.config, "participation_min_dwell_bars", 0) or 0))
            bars_held = max(0, int(getattr(self, "_bars_held", 0) or 0))
            if (
                not force_flat_now
                and not force_time_now
                and bool(getattr(self.config, "suppress_random_flatten", False))
                and min_dwell > 0
                and bars_held < min_dwell
            ):
                flatten = False

            if hit_stop or hit_target or flatten:
                close_side = self._entry_side
                close_stop_pct = self._entry_stop_pct
                close_qty = max(1, int(self._qty or qty or 1))
                close_entry = float(self._entry_price)
                trade_closed = True
                from lumina_core.rl.gym_stop_fill import (
                    plan_birth_exit_fill,
                    row_is_segment_gap,
                )

                is_birth_fill = is_birth
                fill_plan = None
                close_gap = False
                if is_birth_fill:
                    fill_plan = plan_birth_exit_fill(
                        hit_stop=bool(hit_stop),
                        hit_target=bool(hit_target),
                        flatten=bool(flatten),
                        force_time=bool(force_time_now),
                        force_flat=bool(force_flat_now),
                        close_price=price,
                        stop_price=float(stop),
                        target_price=float(target),
                        is_gap=row_is_segment_gap(row),
                    )
                if fill_plan is not None:
                    close_reason = fill_plan.reason
                    mark = float(fill_plan.mark_price)
                    exit_ticks = float(fill_plan.slippage_ticks)
                    close_gap = bool(fill_plan.gap)
                else:
                    if hit_stop:
                        close_reason = "stop"
                    elif hit_target:
                        close_reason = "target"
                    elif force_time_now:
                        close_reason = "time_stop"
                    elif force_flat_now:
                        close_reason = "force_exit"
                    else:
                        close_reason = "flatten"
                    mark = price
                    exit_ticks = max(
                        0.0,
                        float(self._stochastic_slippage_points(price))
                        / max(self.valuation_engine.tick_size(self.instrument), 1e-9),
                    )
                exit_fill = self.valuation_engine.apply_exit_fill(
                    symbol=self.instrument,
                    price=mark,
                    side=self._position,
                    slippage_ticks=exit_ticks,
                )
                slippage_cost += abs(exit_fill - mark) * close_qty * self.valuation_engine.point_value(
                    self.instrument
                )
                fees_cost += self._fees_usd(quantity=close_qty, sides=1)
                realized_pnl = self.valuation_engine.pnl_dollars(
                    symbol=self.instrument,
                    entry_price=close_entry,
                    exit_price=exit_fill,
                    side=self._position,
                    quantity=close_qty,
                )
                self._close_qty = close_qty
                self._close_entry_price = close_entry
                try:
                    from lumina_core.birth.foundation_metrics import intended_risk_usd

                    self._close_risk_usd = intended_risk_usd(
                        stop_pct=float(close_stop_pct),
                        entry_price=float(close_entry),
                        qty=int(close_qty),
                        point_value=float(self.valuation_engine.point_value(self.instrument)),
                    )
                except Exception:
                    self._close_risk_usd = abs(float(close_stop_pct)) * abs(float(close_entry)) * float(close_qty) * 5.0
                self._position = 0
                self._qty = 0
                self._entry_price = 0.0
                self._entry_stop_pct = float(
                    getattr(self.config, "default_stop_pct", 0.0012) or 0.0012
                )
                self._entry_target_pct = float(
                    getattr(self.config, "default_target_pct", 0.0020) or 0.0020
                )
                self._bars_held = 0
            else:
                # Completed a bar in position (for envelope min-dwell protect).
                self._bars_held = max(0, int(getattr(self, "_bars_held", 0) or 0)) + 1

        prev_equity = self._equity
        from lumina_core.rl.gym_birth_close import book_birth_close_net_usd

        booked_net, close_cap_usd = book_birth_close_net_usd(
            float(realized_pnl - slippage_cost - fees_cost),
            is_birth=is_birth,
            trade_closed=bool(trade_closed),
            entry_price=float(getattr(self, "_close_entry_price", 0.0) or 0.0),
            qty=int(getattr(self, "_close_qty", 0) or 1),
        )
        self._equity += booked_net
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

        rl_close_accounting_net_usd = float(booked_net)
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
                    curriculum_regime=str(
                        getattr(self.config, "curriculum_regime", "") or ""
                    ),
                    expectancy_gap=float(
                        getattr(self.config, "expectancy_gap", 0.0) or 0.0
                    ),
                    tick_regime=str(row.get("regime", "NEUTRAL") or "NEUTRAL"),
                    risk_usd=float(getattr(self, "_close_risk_usd", 0.0) or 0.0) or None,
                    qty=int(getattr(self, "_close_qty", 0) or 0) or None,
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
            from lumina_core.birth.stage3_inband_gym import apply_gym_birth_occupancy_reward

            reward += apply_gym_birth_occupancy_reward(
                self,
                row=row,
                side_bucket=int(side_bucket),
                trade_closed=bool(trade_closed),
                close_stop_pct=float(close_stop_pct),
                close_net=float(rl_close_accounting_net_usd),
            )

        self._idx += 1
        terminated = self._idx >= min(len(self.data) - 1, self.config.max_steps)

        from lumina_core.rl.gym_birth_close import gym_step_info

        close_qty_info = int(getattr(self, "_close_qty", 0) or 0) if trade_closed else 0
        close_risk = float(getattr(self, "_close_risk_usd", 0.0) or 0.0) if trade_closed else 0.0
        info = gym_step_info(
            realized_pnl=realized_pnl,
            booked_net=rl_close_accounting_net_usd,
            training_reward=float(reward),
            slippage_cost=slippage_cost,
            fees_cost=fees_cost,
            equity=self._equity,
            drawdown=self._drawdown(),
            sharpe=self._rolling_sharpe(),
            var_es_penalty=var_es_penalty,
            reward_components=reward_components,
            trade_closed=trade_closed,
            close_reason=close_reason,
            entry_stop_pct=float(getattr(self, "_entry_stop_pct", 0.0) or 0.0),
            entry_target_pct=float(getattr(self, "_entry_target_pct", 0.0) or 0.0),
            blocked_by_capital_preservation=blocked_by_capital_preservation,
            block_reason=block_reason,
            qty=close_qty_info,
            risk_usd=close_risk if trade_closed else 0.0,
            cap_usd=float(close_cap_usd) if trade_closed else 0.0,
            gap=bool(close_gap) if trade_closed else False,
            entry_price=float(getattr(self, "_close_entry_price", 0.0) or 0.0) if trade_closed else 0.0,
            point_value=float(self.valuation_engine.point_value(self.instrument)),
        )
        return self._get_observation(), reward, terminated, False, info


"""Stage-pass evaluation + receipt for stage-loop iteration."""
from __future__ import annotations

import time
from typing import Any

from lumina_core.birth.curriculum import CurriculumStage, evaluate_stage_pass, stage_pass_trades
from lumina_core.birth.runway import risk_metrics_from_pnl
from lumina_core.birth.stage_loop_iteration_helpers import LoopAction, stage_pass_event_data, stage_winrate
from lumina_core.birth.stage_pass_receipt import receipt_from_stage_result
from lumina_core.logging_utils import get_logger

logger = get_logger("lumina.birth.stage_loop_iteration.pass")


class StageLoopIterationPassMixin:
    """Evaluate stage pass; build receipt when passed (exit_stage)."""

    def _iteration_evaluate_and_handle_stage_pass(self) -> tuple[LoopAction, dict[str, Any] | None]:
        stage_val_sharpe = 0.0
        stage_val_max_dd = 100.0
        if self.stage_val_pnl:
            stage_val_sharpe, stage_val_max_dd = risk_metrics_from_pnl(self.stage_val_pnl)
        rolling_wr: float | None = None
        rolling_src: str | None = None
        rolling_cov: int = 0
        rolling_display: float | None = None
        # Stage-2 MUST feed rolling into EdgeScore (forensics: peak ~34.7% WR was
        # invisible to pass because rolling was never passed for stage2_range).
        if self.stage in (
            CurriculumStage.STAGE1_TREND,
            CurriculumStage.STAGE2_RANGE,
            CurriculumStage.STAGE3_MIXED,
        ):
            try:
                from lumina_core.birth.starship_birth import gate_rolling_winrate

                wr, source, covered = self._rolling_winrate_meta()
                rolling_display = float(wr)
                rolling_src = str(source)
                rolling_cov = int(covered)
                if self.stage == CurriculumStage.STAGE2_RANGE:
                    from lumina_core.birth.plateau_rolling import (
                        stage_rolling_pass_min_covered,
                        stage_rolling_pass_window,
                    )

                    window = stage_rolling_pass_window(self.cur_cfg, self.stage)
                    # Peak capture: allow shorter honest windows (min 80 covered).
                    min_cov = stage_rolling_pass_min_covered(self.cur_cfg, self.stage)
                    src = str(rolling_src or "").strip().lower()
                    if src in ("true_window", "partial_window") and rolling_cov >= min_cov:
                        rolling_wr = float(rolling_display)
                    else:
                        rolling_wr = None
                    # Durable streak A: consecutive windows at/above floor-equiv WR.
                    try:
                        from lumina_core.birth.starship_edgescore_stage2 import (
                            stage2_expectancy_floor,
                        )

                        wr_need = float(stage2_expectancy_floor(self.cur_cfg)) + 0.50
                    except Exception:
                        wr_need = 0.35
                    streak = int(
                        getattr(self, "_stage2_rolling_pass_streak", 0) or 0
                    )
                    if rolling_wr is not None and float(rolling_wr) + 1e-12 >= wr_need:
                        streak += 1
                    else:
                        streak = 0
                    self._stage2_rolling_pass_streak = streak
                elif self.stage == CurriculumStage.STAGE3_MIXED:
                    from lumina_core.birth.plateau_rolling import stage_rolling_pass_window

                    window = stage_rolling_pass_window(self.cur_cfg, self.stage)
                    rolling_wr = gate_rolling_winrate(
                        rolling_wr=rolling_display,
                        source=rolling_src,
                        covered=rolling_cov,
                        window=window,
                    )
                    wr_need = float(
                        getattr(self.cur_cfg, "stage3_winrate_floor", 0.35) or 0.35
                    )
                    streak = int(getattr(self, "_stage2_rolling_pass_streak", 0) or 0)
                    if rolling_wr is not None and float(rolling_wr) + 1e-12 >= wr_need:
                        streak += 1
                    else:
                        streak = 0
                    self._stage2_rolling_pass_streak = streak
                else:
                    from lumina_core.birth.plateau_rolling import stage_rolling_pass_window

                    window = stage_rolling_pass_window(self.cur_cfg, self.stage)
                    rolling_wr = gate_rolling_winrate(
                        rolling_wr=rolling_display,
                        source=rolling_src,
                        covered=rolling_cov,
                        window=window,
                    )
            except Exception:
                rolling_wr = None
        stage_pnl = (
            float(sum(self.stage_val_pnl)) if getattr(self, "stage_val_pnl", None) else None
        )
        geo = getattr(self, "_birth_trade_geometry", None)
        from lumina_core.birth.history_loader import session_unique_calendar_days

        unique_days = session_unique_calendar_days(
            cached=int(getattr(self, "_unique_calendar_days", 0) or 0),
            host=self.host,
            ticks=self.stage_ticks,
        )
        if unique_days > 0:
            self._unique_calendar_days = unique_days
        p_ft = None
        net_rr = None
        stop_pct = None
        ref_price = None
        if geo is not None:
            stop_pct = float(getattr(geo, "stop_pct", 0.0) or 0.0)
            ref_price = float(getattr(geo, "ref_price", 0.0) or 0.0)
            net_rr = float(getattr(geo, "net_rr_after_cost", 0.0) or 0.0)
            try:
                from lumina_core.birth.birth_trade_geometry import first_touch_target_hit_rate

                p_ft = first_touch_target_hit_rate(
                    list(self.stage_ticks or []),
                    stop_pct=stop_pct,
                    target_pct=float(getattr(geo, "target_pct", 0.0) or 0.0),
                    max_hold_bars=int(getattr(geo, "hold_bars", 90) or 90),
                )
            except Exception:
                p_ft = None
        stage_result = evaluate_stage_pass(
            self.stage,
            trades=self.stage_trades,
            wins=self.stage_wins,
            hold_signals=self.stage_hold_signals,
            total_signals=self.stage_total_signals,
            range_hold_signals=self.stage_range_hold_signals,
            range_total_signals=self.stage_range_total_signals,
            range_flat_bars=self.stage_range_flat_bars,
            range_round_trips=self.stage_range_round_trips,
            constitution_violations=self.host._constitution_guard.violations,
            target_trades=self.target,
            cfg=self.cur_cfg,
            provisional=False,
            allow_provisional=False,
            oracle_patterns=self.patterns_mined,
            buffer_size=len(self.host.buffer),
            stage_val_sharpe=stage_val_sharpe,
            stage_val_max_drawdown_pct=stage_val_max_dd,
            rolling_winrate=rolling_wr,
            policy_entropy=self._resolve_policy_entropy(),
            stage_total_pnl=stage_pnl,
            ppo_steps=int(getattr(self.host, "ppo_steps", 0) or 0),
            policy_trades=int(getattr(self, "stage_policy_trades", 0) or 0),
            policy_wins=int(getattr(self, "stage_policy_wins", 0) or 0),
            plant_trades=int(getattr(self, "stage_plant_trades", 0) or 0),
            plant_wins=int(getattr(self, "stage_plant_wins", 0) or 0),
            consecutive_rolling_pass_windows=int(
                getattr(self, "_stage2_rolling_pass_streak", 0) or 0
            ),
            closes_stop=int(getattr(self, "stage_closes_stop_cum", 0) or 0),
            closes_target=int(getattr(self, "stage_closes_target_cum", 0) or 0),
            closes_time_stop=int(getattr(self, "stage_closes_time_stop_cum", 0) or 0),
            closes_flatten=int(getattr(self, "stage_closes_flatten_cum", 0) or 0),
            closes_unknown=int(getattr(self, "stage_closes_unknown_cum", 0) or 0),
            pnl_series=list(self.stage_val_pnl or []),
            r_series=list(getattr(self, "stage_val_r", None) or []) or None,
            stop_pct=stop_pct,
            ref_price=ref_price,
            geometry_net_rr=net_rr,
            first_touch_hit_rate=p_ft,
            unique_calendar_days=unique_days,
            oos_sharpe=(
                stage_val_sharpe
                if self.stage == CurriculumStage.STAGE5_PROBE_HANDOFF
                else None
            ),
            oos_dd_pct=(
                stage_val_max_dd
                if self.stage == CurriculumStage.STAGE5_PROBE_HANDOFF
                else None
            ),
        )
        if not stage_result.passed:
            now = time.time()
            last = float(getattr(self, "_last_not_passed_log_at", 0.0) or 0.0)
            if now - last >= 30.0:
                self._last_not_passed_log_at = now
                logger.warning(
                    "birth.stage.not_passed stage=%s trades=%s blockers=%s "
                    "median_loss_r=%s net_rr=%s",
                    self.stage.value,
                    self.stage_trades,
                    stage_result.message,
                    stage_result.median_loss_r,
                    stage_result.net_rr,
                )
            return "fallthrough", None

        self.required = stage_pass_trades(self.stage, self.cur_cfg)
        pass_winrate = stage_winrate(self.stage_wins, self.stage_trades)
        logger.info(
            "birth.stage.passed stage=%s trades=%s wins=%s required=%s "
            "winrate=%.2f%% provisional=%s reason=%s",
            self.stage.value,
            self.stage_trades,
            self.stage_wins,
            self.required,
            pass_winrate * 100.0,
            bool(stage_result.provisional),
            stage_result.message,
            extra={
                "event_data": stage_pass_event_data(
                    stage_value=self.stage.value,
                    trades=self.stage_trades,
                    wins=self.stage_wins,
                    required=self.required,
                    winrate=pass_winrate,
                    patterns_mined=self.patterns_mined,
                    attempts=self.attempt,
                    pass_reason=stage_result.message,
                    provisional=bool(stage_result.provisional),
                )
            },
        )
        pass_edgescore = None
        edgescore_any = bool(
            getattr(self.cur_cfg, "stage1_edgescore_enabled", False)
            or getattr(self.cur_cfg, "stage2_edgescore_enabled", False)
            or getattr(self.cur_cfg, "stage3_edgescore_enabled", False)
        )
        if edgescore_any:
            try:
                pass_edgescore = float(self._current_edgescore())
            except Exception:
                pass_edgescore = float(getattr(self, "best_edgescore", 0.0) or 0.0)
        hygiene_source: str | None = None
        if self.stage in (CurriculumStage.STAGE1_TREND, CurriculumStage.STAGE3_MIXED):
            from lumina_core.birth.starship_birth import hygiene_wr_telemetry

            floor = (
                float(getattr(self.cur_cfg, "stage3_winrate_floor", 0.35))
                if self.stage == CurriculumStage.STAGE3_MIXED
                else (
                    float(getattr(self.cur_cfg, "birth_survival_wr_floor", 0.20) or 0.20)
                    if bool(getattr(self.cur_cfg, "birth_survival_pass_enabled", True))
                    else float(getattr(self.cur_cfg, "stage1_winrate_pass_floor", 0.35))
                )
            )
            hygiene_source = str(
                hygiene_wr_telemetry(
                    lifetime_wr=pass_winrate,
                    rolling_wr=rolling_display,
                    rolling_source=rolling_src,
                    rolling_covered=rolling_cov,
                    floor=floor,
                    window=int(getattr(self.cur_cfg, "stage1_rolling_pass_window", 500) or 500),
                ).get("hygiene_wr_source")
                or "neither"
            )
        self.host._pending_stage_pass_receipt = receipt_from_stage_result(
            self.stage,
            stage_result,
            cfg=self.cur_cfg,
            hold_signals=self.stage_hold_signals,
            total_signals=self.stage_total_signals,
            range_hold_signals=self.stage_range_hold_signals,
            range_total_signals=self.stage_range_total_signals,
            range_flat_bars=self.stage_range_flat_bars,
            edgescore=pass_edgescore,
            policy_entropy=self._resolve_policy_entropy(),
            stage_total_pnl=stage_pnl,
            rolling_winrate=rolling_display,
            rolling_winrate_source=rolling_src,
            rolling_window_trades_covered=rolling_cov,
            hygiene_wr_source=hygiene_source,
            policy_trades=int(getattr(self, "stage_policy_trades", 0) or 0),
            policy_wins=int(getattr(self, "stage_policy_wins", 0) or 0),
            plant_trades=int(getattr(self, "stage_plant_trades", 0) or 0),
            plant_wins=int(getattr(self, "stage_plant_wins", 0) or 0),
            geometry_net_rr=net_rr,
            unique_calendar_days=unique_days,
        )
        return "exit_stage", None

"""Stage-pass evaluation + receipt for stage-loop iteration."""
from __future__ import annotations

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
        if self.stage in (CurriculumStage.STAGE1_TREND, CurriculumStage.STAGE3_MIXED):
            try:
                from lumina_core.birth.starship_birth import gate_rolling_winrate

                wr, source, covered = self._rolling_winrate_meta()
                rolling_display = float(wr)
                rolling_src = str(source)
                rolling_cov = int(covered)
                window = int(getattr(self.cur_cfg, "stage1_rolling_pass_window", 500) or 500)
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
            provisional=self.gen0_provisional,
            allow_provisional=self.allow_provisional,
            oracle_patterns=self.patterns_mined,
            buffer_size=len(self.host.buffer),
            stage_val_sharpe=stage_val_sharpe,
            stage_val_max_drawdown_pct=stage_val_max_dd,
            rolling_winrate=rolling_wr,
            policy_entropy=self._resolve_policy_entropy(),
            stage_total_pnl=stage_pnl,
            ppo_steps=int(getattr(self.host, "ppo_steps", 0) or 0),
        )
        if not stage_result.passed:
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
                else float(getattr(self.cur_cfg, "stage1_winrate_pass_floor", 0.35))
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
        )
        return "exit_stage", None

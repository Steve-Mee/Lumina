"""Stage-loop progress write path (M5 slim orchestrator).

Scorecard enrichment: ``stage_loop_progress_write_enrich``.
Starship fields: ``stage_loop_progress_write_starship``.
"""
from __future__ import annotations

import time

from lumina_core.birth.foundation_metrics import FOUNDATION_STAGE_COUNT
from lumina_core.birth.progress import merge_birth_progress_extra
from lumina_core.birth.stage_scorecard import build_scorecard_payload
from lumina_core.birth.stage_loop_progress_write_enrich import StageLoopProgressWriteEnrichMixin
from lumina_core.birth.stage_loop_progress_write_starship import (
    StageLoopProgressStarshipMixin,
)
from lumina_core.logging_utils import get_logger

logger = get_logger("lumina.birth.stage_loop_mixin")


class StageLoopProgressWriteMixin(
    StageLoopProgressWriteEnrichMixin,
    StageLoopProgressStarshipMixin,
):
    """Writes birth progress scorecard fields."""

    def _write_progress(
        self,
        *,
        phase: str,
        message: str,
        chunk_trades: int = 0,
        rollout_steps: int = 0,
        exploration_active: bool = False,
        hold_ratio: float = 0.0,
    ) -> None:
        current_stage_trades = self.stage_trades + chunk_trades
        elapsed_snapshot = max(0.0, time.time() - self.scorecard_snapshot_at)
        constitution_fields = self.host._constitution_progress_fields()
        rolling_for_scorecard: float | None = None
        rolling_source = "lifetime_fallback"
        rolling_covered = 0
        try:
            rolling_for_scorecard, rolling_source, rolling_covered = self._rolling_winrate_meta()
        except Exception:
            try:
                rolling_for_scorecard = float(self._rolling_winrate_500())
            except Exception:
                rolling_for_scorecard = None
        from lumina_core.birth.starship_birth import (
            gate_rolling_winrate,
            hygiene_wr_telemetry,
            rolling_wr_pass_eligible,
        )

        from lumina_core.birth.plateau_rolling import stage_rolling_pass_window

        roll_window = stage_rolling_pass_window(self.cur_cfg, self.stage)
        rolling_for_blocker = gate_rolling_winrate(
            rolling_wr=rolling_for_scorecard,
            source=rolling_source,
            covered=rolling_covered,
            window=roll_window,
        )
        rolling_eligible = rolling_wr_pass_eligible(
            source=rolling_source,
            covered=rolling_covered,
            window=roll_window,
        )
        entropy_for_blocker = self._resolve_policy_entropy()
        geo = getattr(self, "_birth_trade_geometry", None)
        stop_pct: float | None = None
        ref_price: float | None = None
        net_rr: float | None = None
        if geo is not None:
            stop_pct = float(getattr(geo, "stop_pct", 0.0) or 0.0)
            ref_price = float(getattr(geo, "ref_price", 0.0) or 0.0)
            net_rr = float(getattr(geo, "net_rr_after_cost", 0.0) or 0.0)
        p_ft_raw = getattr(self, "_first_touch_target_hit_rate", None)
        p_ft: float | None = None
        try:
            if p_ft_raw is not None and float(p_ft_raw) > 0.0:
                p_ft = float(p_ft_raw)
        except (TypeError, ValueError):
            p_ft = None
        from lumina_core.birth.history_loader import session_unique_calendar_days

        unique_days = session_unique_calendar_days(
            cached=int(getattr(self, "_unique_calendar_days", 0) or 0),
            host=self.host,
            ticks=self.stage_ticks,
        )
        if unique_days > 0:
            self._unique_calendar_days = unique_days
        scorecard = build_scorecard_payload(
            stage=self.stage,
            curriculum_index=self.stage_index + 1,
            stages_passed=list(self.host._stages_passed),
            stage_trades=current_stage_trades,
            stage_wins=self.stage_wins,
            stage_hold_signals=self.stage_hold_signals,
            stage_total_signals=self.stage_total_signals,
            constitution_violations=int(constitution_fields["constitution_violations_session"]),
            target_trades=self.target,
            phase=phase,
            patterns_mined=self.patterns_mined,
            learning_attempt=self.attempt + 1,
            prev_stage_trades=self.scorecard_snapshot_trades,
            prev_patterns_mined=self.scorecard_snapshot_patterns,
            snapshot_elapsed_sec=elapsed_snapshot,
            stage_range_flat_bars=self.stage_range_flat_bars,
            stage_range_total_signals=self.stage_range_total_signals,
            stage_range_round_trips=self.stage_range_round_trips,
            provisional_pass=self.gen0_provisional,
            cfg=self.cur_cfg,
            rolling_winrate=rolling_for_blocker,
            rolling_winrate_display=rolling_for_scorecard,
            rolling_wr_eligible=rolling_eligible,
            policy_entropy=entropy_for_blocker,
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
        )
        self._enrich_progress_scorecard(
            scorecard,
            phase=phase,
            current_stage_trades=current_stage_trades,
            constitution_fields=constitution_fields,
            rollout_steps=rollout_steps,
            rolling_for_scorecard=rolling_for_scorecard,
            rolling_for_blocker=rolling_for_blocker,
            rolling_source=rolling_source,
            rolling_covered=rolling_covered,
            roll_window=roll_window,
            hygiene_wr_telemetry=hygiene_wr_telemetry,
        )
        # Preserve active terminal freeze on every progress write (anti hollow rewrite).
        try:
            from lumina_core.birth.terminal_freeze import (
                extract_terminal_freeze,
                freeze_attention_fields,
                freeze_is_active,
            )

            _freeze = extract_terminal_freeze(
                scorecard,
                getattr(self.host, "_terminal_freeze", None),
                getattr(self.host, "_active_stage_metrics", None),
            )
            if freeze_is_active(_freeze) and _freeze is not None:
                scorecard["terminal_freeze"] = dict(_freeze)
                for k, v in freeze_attention_fields(_freeze).items():
                    if k == "terminal_freeze":
                        continue
                    if k in {"curriculum_stage", "stages_passed"} and scorecard.get(k):
                        # Prefer freeze identity when live stages_passed hollow.
                        if k == "stages_passed" and not list(scorecard.get("stages_passed") or []):
                            scorecard[k] = v
                        elif k == "curriculum_stage" and (
                            not scorecard.get(k)
                            or (
                                scorecard.get(k) == "stage1_trend"
                                and str((_freeze or {}).get("curriculum_stage") or "")
                                != "stage1_trend"
                            )
                        ):
                            scorecard[k] = v
                        continue
                    if not scorecard.get(k):
                        scorecard[k] = v
                self.host._terminal_freeze = dict(_freeze)
        except Exception:
            pass
        # C2: attention SSOT after enrich (recovery compress / terminal_stall_reason)
        _swarm_attn = bool(
            (
                getattr(self, "swarm_rejected_no_lift", False)
                or getattr(self.swarm_state, "rejected_no_lift", False)
            )
            and not bool(
                getattr(self, "swarm_champion_accepted", False)
                or getattr(self.swarm_state, "champion_accepted", False)
            )
        )
        _terminal_reason = str(scorecard.get("terminal_stall_reason") or "").strip()
        _rec = scorecard.get("recovery") if isinstance(scorecard.get("recovery"), dict) else {}
        _rec_flags = _rec.get("flags") if isinstance(_rec.get("flags"), dict) else {}
        try:
            from lumina_core.birth.curriculum import CurriculumStage
            from lumina_core.birth.foundation_metrics import process_r_ok

            if (
                self.stage == CurriculumStage.STAGE1_TREND
                and int(current_stage_trades) >= int(self.required)
                and not process_r_ok(scorecard.get("median_loss_r"))
            ):
                scorecard["needs_attention"] = True
                if not str(scorecard.get("attention_reason_code") or "").strip():
                    scorecard["attention_reason_code"] = "process_r_plant"
                if not str(scorecard.get("attention_summary") or "").strip():
                    scorecard["attention_summary"] = (
                        "Stage-1 process-R plant fail: median_loss_r above 1.5R "
                        "after volume gate — HOLD, do not explore_reduce."
                    )
                if not scorecard.get("attention_recommended_actions"):
                    scorecard["attention_recommended_actions"] = [
                        "fix_stop_fill_physics",
                        "human_review",
                    ]
        except Exception:
            logger.debug("birth.progress.process_r_attention_failed", exc_info=True)
        _needs_attention = bool(
            _swarm_attn
            or scorecard.get("needs_attention")
            or _rec_flags.get("needs_attention")
            or _rec.get("active") == "terminal_stall"
            or bool(_terminal_reason)
            or bool(scorecard.get("terminal_freeze"))
        )
        if _needs_attention:
            scorecard["needs_attention"] = True
            if not str(scorecard.get("attention_reason_code") or "").strip():
                scorecard["attention_reason_code"] = (
                    (
                        str(getattr(self, "swarm_fail_reason_code", "") or "").strip()
                        or "swarm_no_tournament_lift"
                    )
                    if _swarm_attn
                    else (_terminal_reason or "terminal_stall")
                )
            if not str(scorecard.get("attention_summary") or "").strip():
                scorecard["attention_summary"] = (
                    "Swarm tournament produced no tournament lift — champion frozen; accept or wipe."
                    if _swarm_attn
                    else (
                        f"Terminal stall: {scorecard.get('attention_reason_code')} — "
                        f"next_action={_rec.get('next_action', 'expand_data_or_wipe_genesis')}"
                    )
                )
            if not scorecard.get("attention_recommended_actions"):
                scorecard["attention_recommended_actions"] = (
                    ["accept_champion", "wipe_and_retry"]
                    if _swarm_attn
                    else ["expand_data", "wipe_and_retry", "human_review"]
                )
        elapsed_stage_sec = max(0.0, time.time() - self.stage_started_at)
        # P4: honest progress — advance within stage (was frozen at stage base e.g. 27%).
        base_pct = float(self.stage_progress_pct)
        stage_span = 53.0 / float(FOUNDATION_STAGE_COUNT)
        pass_gate = max(
            50,
            int(
                scorecard.get("stage_pass_gate_trades")
                or scorecard.get("stage_target_trades")
                or getattr(self, "target", 0)
                or 200
            ),
        )
        within = min(1.0, float(current_stage_trades) / float(pass_gate))
        honest_pct = round(min(79.5, base_pct + stage_span * within), 2)
        progress_extra = merge_birth_progress_extra(constitution_fields, scorecard)
        self.host._emit_birth_progress(
            stage="training_running",
            phase=phase,
            message=message,
            progress_pct=honest_pct,
            cumulative_trades=self.host.cumulative_trades + chunk_trades,
            target_trades=self.trade_budget_cap,
            ppo_steps=self.host.ppo_steps,
            birth_start_time=self.host.birth_start_time,
            curriculum_stage=self.stage.value,
            stage_trades=current_stage_trades,
            stage_hold_signals=self.stage_hold_signals,
            stage_total_signals=self.stage_total_signals,
            stage_range_hold_signals=self.stage_range_hold_signals,
            stage_range_total_signals=self.stage_range_total_signals,
            stage_range_flat_bars=self.stage_range_flat_bars,
            stage_range_round_trips=self.stage_range_round_trips,
            stage_range_flat_ratio=round(
                float(self.stage_range_flat_bars) / float(max(1, self.stage_range_total_signals)),
                4,
            ),
            rollout_trades=chunk_trades,
            rollout_steps=rollout_steps,
            hold_ratio=round(hold_ratio, 4),
            exploration_active=exploration_active,
            learning_attempt=self.attempt + 1,
            escalation_level=self.escalation_level,
            gen0_provisional=self.gen0_provisional,
            patterns_mined=self.patterns_mined,
            oracle_wins=self.oracle_wins,
            oracle_last_scanned=int(getattr(self, "oracle_last_scanned", 0) or 0),
            oracle_last_patterns=int(getattr(self, "oracle_last_patterns", 0) or 0),
            oracle_last_stop_pct=round(float(getattr(self, "oracle_last_stop_pct", 0.0) or 0.0), 6),
            oracle_last_target_pct=round(
                float(getattr(self, "oracle_last_target_pct", 0.0) or 0.0), 6
            ),
            oracle_last_reason=str(getattr(self, "oracle_last_reason", "") or ""),
            display_winrate_scope="stage_current",
            training_mode=str(self.training_mode),
            allow_provisional=bool(self.allow_provisional),
            data_days_loaded=self.data_days_loaded,
            requested_days=int(self.host._data_manifest.get("requested_days", 0) or 0) or None,
            actual_calendar_days=int(
                self.host._data_manifest.get("actual_calendar_days", 0) or 0
            )
            or None,
            requested_instrument=str(
                self.host._data_manifest.get("requested_instrument", "") or ""
            )
            or None,
            resolved_instrument=str(
                self.host._data_manifest.get("resolved_instrument", "") or ""
            )
            or None,
            rolled=self.host._data_manifest.get("rolled"),
            stitched=self.host._data_manifest.get("stitched"),
            instruments=self.host._data_manifest.get("instruments"),
            stitched_from=self.host._data_manifest.get("stitched_from"),
            expansion_step=self.expansion_step,
            stage_wall_remaining_sec=max(
                0, int(self.cur_cfg.max_stage_wall_sec) - int(elapsed_stage_sec)
            ),
            quality_score=float(self.host._data_manifest.get("quality_score", 0.0) or 0.0),
            intra_hard_pct=round(float(self.intra_state.hard_pct), 4) if self.intra_state else None,
            intra_easy_winrate=round(
                float(self.intra_state.easy_wins) / float(max(1, self.intra_state.easy_trades)),
                4,
            )
            if self.intra_state and self.intra_state.easy_trades > 0
            else None,
            needs_attention=_needs_attention,
            attention_summary=str(scorecard.get("attention_summary") or ""),
            attention_reason_code=str(scorecard.get("attention_reason_code") or ""),
            attention_recommended_actions=list(
                scorecard.get("attention_recommended_actions") or []
            ),
            user_initiated_stop=False,
            extra_parts=(progress_extra,),
        )
        if (
            current_stage_trades > self.scorecard_snapshot_trades
            or self.patterns_mined > self.scorecard_snapshot_patterns
        ):
            self.scorecard_snapshot_trades = current_stage_trades
            self.scorecard_snapshot_patterns = self.patterns_mined
            self.scorecard_snapshot_at = time.time()
        self.last_progress_write_at = time.time()


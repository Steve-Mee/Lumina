from __future__ import annotations

import logging
from typing import Any, Protocol

from lumina_core.config_loader import ConfigLoader

from .approval_twin_agent import ApprovalTwinAgent
from .dna_registry import PolicyDNA
from .fitness_evaluator import utcnow
from .multi_day_sim_runner import MultiDaySimRunner
from .rollout import EvolutionRolloutFramework
from .shadow_run_storage import load_shadow_runs, save_shadow_runs
from .veto_window import VetoWindow


class PromotionPolicyProtocol(Protocol):
    def run_shadow_validation_gate(
        self,
        *,
        dna: PolicyDNA,
        winner_fitness: float,
        nightly_report: dict[str, Any],
        signed: bool,
        generation_ok: bool,
        shadow_runner: MultiDaySimRunner,
    ) -> dict[str, Any]:
        ...

    def mark_shadow_promoted(self, *, dna_hash: str) -> None:
        ...

    def load_shadow_runs(self) -> dict[str, Any]:
        ...

    def save_shadow_runs(self, payload: dict[str, Any]) -> None:
        ...


class _OrchestratorContext(Protocol):
    _guard: Any
    _approval_twin: ApprovalTwinAgent
    _telegram_notifier: Any
    _notification_scheduler: Any
    _veto_registry: Any
    _shadow_state_path: Any


class PromotionPolicy:
    def __init__(self, owner: _OrchestratorContext, logger: logging.Logger | None = None) -> None:
        self._owner = owner
        self._logger = logger or logging.getLogger(__name__)

    def send_shadow_status_telegram(self, message: str) -> None:
        def _send() -> bool:
            return self._owner._telegram_notifier._send_telegram_message(message)

        try:
            self._owner._notification_scheduler.schedule_notification(
                callback=_send,
                description=f"shadow_status:{message[:50]}",
            )
        except Exception as exc:
            self._logger.warning("[SHADOWTWIN] Telegram notification failed: %s", exc)

    def send_promotion_status_telegram(self, *, dna_hash: str, promoted: bool) -> None:
        status = "PROMOTED" if promoted else "VETOED"
        self.send_shadow_status_telegram(f"{status}\nDNA: {str(dna_hash)[:12]}")

    def resolve_shadow_day_bounds(self) -> tuple[int, int]:
        evolution_cfg = ConfigLoader.section("evolution", default={})
        if not isinstance(evolution_cfg, dict):
            return 3, 7
        shadow_cfg = evolution_cfg.get("shadow_validation", {})
        if not isinstance(shadow_cfg, dict):
            return 3, 7
        min_days = max(1, int(shadow_cfg.get("min_days", 3) or 3))
        max_days = max(min_days, int(shadow_cfg.get("max_days", 7) or 7))
        return min_days, max_days

    def veto_window_for_days(self, days: int) -> VetoWindow:
        return VetoWindow(
            veto_registry=self._owner._veto_registry,
            window_seconds=max(1, int(days)) * 24 * 60 * 60,
        )

    def load_shadow_runs(self) -> dict[str, Any]:
        return load_shadow_runs(self._owner._shadow_state_path)

    def save_shadow_runs(self, payload: dict[str, Any]) -> None:
        save_shadow_runs(self._owner._shadow_state_path, payload)

    def mark_shadow_promoted(self, *, dna_hash: str) -> None:
        shadow_runs = self.load_shadow_runs()
        record = dict(shadow_runs.get(dna_hash, {}) or {})
        if not record:
            return
        record["status"] = "promoted"
        record["updated_at"] = utcnow()
        shadow_runs[dna_hash] = record
        self.save_shadow_runs(shadow_runs)

    def run_shadow_validation_gate(
        self,
        *,
        dna: PolicyDNA,
        winner_fitness: float,
        nightly_report: dict[str, Any],
        signed: bool,
        generation_ok: bool,
        shadow_runner: MultiDaySimRunner,
    ) -> dict[str, Any]:
        if not signed or not generation_ok:
            return {
                "promote_now": False,
                "veto_blocked": False,
                "veto_check": {"is_blocked": False, "reason": "guard_not_satisfied", "active_veto_records": []},
                "shadow_status": "guard_blocked",
                "shadow_passed": False,
                "shadow_days_completed": 0,
                "shadow_days_target": 0,
                "shadow_total_pnl": 0.0,
            }

        shadow_runs = self.load_shadow_runs()
        record = dict(shadow_runs.get(dna.hash, {}) or {})
        if not record:
            min_days, max_days = self.resolve_shadow_day_bounds()
            target_days = self._owner._guard.resolve_shadow_days(minimum_days=min_days, maximum_days=max_days)
            record = {
                "dna_hash": dna.hash,
                "lineage_hash": str(dna.lineage_hash),
                "started_at": utcnow(),
                "updated_at": utcnow(),
                "target_days": target_days,
                "status": "pending",
                "winner_fitness": float(winner_fitness),
                "daily_pnl": [],
                "daily_fill_count": [],
                "shadow_total_pnl": 0.0,
            }
            shadow_runs[dna.hash] = record
            self.save_shadow_runs(shadow_runs)
            return {
                "promote_now": False,
                "veto_blocked": False,
                "veto_check": {"is_blocked": False, "reason": "shadow_started", "active_veto_records": []},
                "shadow_status": "pending",
                "shadow_passed": False,
                "shadow_days_completed": 0,
                "shadow_days_target": int(target_days),
                "shadow_total_pnl": 0.0,
            }

        status = str(record.get("status", "pending")).strip().lower()
        if status == "promoted":
            return {
                "promote_now": False,
                "veto_blocked": False,
                "veto_check": {"is_blocked": False, "reason": "already_promoted", "active_veto_records": []},
                "shadow_status": "promoted",
                "shadow_passed": True,
                "shadow_days_completed": len(list(record.get("daily_pnl", []) or [])),
                "shadow_days_target": int(record.get("target_days", 0) or 0),
                "shadow_total_pnl": float(record.get("shadow_total_pnl", 0.0) or 0.0),
            }
        if status in {"failed", "vetoed"}:
            vetoed = status == "vetoed"
            return {
                "promote_now": False,
                "veto_blocked": vetoed,
                "veto_check": {
                    "is_blocked": vetoed,
                    "reason": "shadow_failed_or_vetoed",
                    "active_veto_records": [],
                },
                "shadow_status": status,
                "shadow_passed": False,
                "shadow_days_completed": len(list(record.get("daily_pnl", []) or [])),
                "shadow_days_target": int(record.get("target_days", 0) or 0),
                "shadow_total_pnl": float(record.get("shadow_total_pnl", 0.0) or 0.0),
            }

        target_days = max(1, int(record.get("target_days", 3) or 3))
        daily_pnl = [float(item) for item in list(record.get("daily_pnl", []) or [])]
        daily_fill_count = [int(item) for item in list(record.get("daily_fill_count", []) or [])]

        if len(daily_pnl) < target_days:
            try:
                self._owner._telegram_notifier.poll_for_replies()
            except Exception as exc:
                self._logger.warning("[SHADOWTWIN] Telegram poll failed: %s", exc)
            if self._owner._telegram_notifier.is_vetoed_or_expired(dna.hash):
                record["status"] = "vetoed"
                record["updated_at"] = utcnow()
                shadow_runs[dna.hash] = record
                self.save_shadow_runs(shadow_runs)
                return {
                    "promote_now": False,
                    "veto_blocked": True,
                    "veto_check": {"is_blocked": True, "reason": "telegram_veto", "active_veto_records": []},
                    "shadow_status": "vetoed",
                    "shadow_passed": False,
                    "shadow_days_completed": len(daily_pnl),
                    "shadow_days_target": target_days,
                    "shadow_total_pnl": float(sum(daily_pnl)),
                }

            shadow_results = shadow_runner.evaluate_variants(
                [dna],
                days=1,
                nightly_report=nightly_report,
                **EvolutionRolloutFramework.shadow_runtime_flags(),
            )
            latest = shadow_results[0] if shadow_results else None
            day_pnl = float(latest.avg_pnl) if latest is not None else 0.0
            fill_count = len(list(latest.hypothetical_fills or [])) if latest is not None else 0
            daily_pnl.append(day_pnl)
            daily_fill_count.append(fill_count)
            record["daily_pnl"] = daily_pnl
            record["daily_fill_count"] = daily_fill_count
            record["shadow_total_pnl"] = float(sum(daily_pnl))
            record["updated_at"] = utcnow()
            shadow_runs[dna.hash] = record
            self.save_shadow_runs(shadow_runs)

        shadow_total_pnl = float(sum(daily_pnl))
        veto_check = self.veto_window_for_days(target_days).check_with_details(dna_id=dna.hash)
        veto_blocked = bool(veto_check.get("is_blocked", False))
        if len(daily_pnl) < target_days:
            return {
                "promote_now": False,
                "veto_blocked": veto_blocked,
                "veto_check": veto_check,
                "shadow_status": "pending",
                "shadow_passed": False,
                "shadow_days_completed": len(daily_pnl),
                "shadow_days_target": target_days,
                "shadow_total_pnl": shadow_total_pnl,
            }

        shadow_twin = self._owner._approval_twin.evaluate_shadow_promotion(
            dna=dna,
            shadow_total_pnl=shadow_total_pnl,
            veto_blocked=veto_blocked,
        )
        risk_flags = list(shadow_twin.get("risk_flags", []) or [])
        shadow_passed = self._owner._guard.shadow_validation_passed(
            shadow_total_pnl=shadow_total_pnl,
            veto_blocked=veto_blocked,
            risk_flags=risk_flags,
        )
        record["status"] = "passed" if shadow_passed else ("vetoed" if veto_blocked else "failed")
        record["shadow_total_pnl"] = shadow_total_pnl
        record["updated_at"] = utcnow()
        record["shadow_decision"] = {
            "recommendation": bool(shadow_twin.get("recommendation", False)),
            "confidence": float(shadow_twin.get("confidence", 0.0) or 0.0),
            "risk_flags": risk_flags,
            "explanation": str(shadow_twin.get("explanation", "")),
        }
        shadow_runs[dna.hash] = record
        self.save_shadow_runs(shadow_runs)
        return {
            "promote_now": shadow_passed,
            "veto_blocked": veto_blocked,
            "veto_check": veto_check,
            "shadow_status": str(record.get("status", "pending")),
            "shadow_passed": shadow_passed,
            "shadow_days_completed": len(daily_pnl),
            "shadow_days_target": target_days,
            "shadow_total_pnl": shadow_total_pnl,
        }

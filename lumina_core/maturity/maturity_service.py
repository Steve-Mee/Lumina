"""Maturity continuum service — start phase runners + hub orchestration."""
from __future__ import annotations

import threading
from pathlib import Path
from typing import Any

from lumina_core.logging_utils import get_logger
from lumina_core.maturity.advance_policy import confirm_telegram_advance, on_phase_complete
from lumina_core.maturity.continuum import (
    load_continuum,
    mark_phase_completed,
    set_advance_mode,
)
from lumina_core.maturity.phase_runners import run_phase
from lumina_core.maturity.phase_specs import can_start_phase, hub_payload
from lumina_core.maturity.wipe import wipe_all_maturation, wipe_phase

logger = get_logger("lumina.maturity.service")


class MaturityService:
    _instance: MaturityService | None = None

    def __init__(self) -> None:
        self.workspace_root = Path.cwd()
        self._thread: threading.Thread | None = None
        self._lock = threading.Lock()
        self._last_result: dict[str, Any] | None = None
        self._error: str | None = None
        self._stop_requested = threading.Event()

    @classmethod
    def instance(cls) -> MaturityService:
        if cls._instance is None:
            cls._instance = MaturityService()
        return cls._instance

    def configure_workspace(self, workspace_root: Path | str) -> Path:
        self.workspace_root = Path(workspace_root)
        return self.workspace_root

    def is_running(self) -> bool:
        return self._thread is not None and self._thread.is_alive()

    def get_hub(self) -> dict[str, Any]:
        # Ensure continuum exists / migrated
        load_continuum(self.workspace_root)
        hub = hub_payload(self.workspace_root)
        hub["runner_active"] = self.is_running()
        hub["last_result"] = self._last_result
        hub["error"] = self._error
        return hub

    def set_preferences(self, *, advance_mode: str) -> dict[str, Any]:
        data = set_advance_mode(self.workspace_root, advance_mode)  # type: ignore[arg-type]
        return {"ok": True, "advance_mode": data.get("advance_mode")}

    def start_phase(self, phase: str, *, explicit_user_start: bool = True) -> dict[str, Any]:
        if not explicit_user_start:
            return {"ok": False, "error": "explicit_user_start required"}
        phase = str(phase or "").strip().lower()
        ok, reason = can_start_phase(self.workspace_root, phase)
        if not ok and reason != "re-run_allowed":
            return {"ok": False, "error": reason}
        if phase == "birth":
            return {
                "ok": False,
                "error": "Use /api/birth/start for Birth phase",
                "redirect": "/api/birth/start",
            }
        if phase == "real":
            return {
                "ok": False,
                "error": "REAL requires approve-real + mode switch",
                "redirect": "/api/maturity/approve-real",
            }
        with self._lock:
            if self.is_running():
                return {"ok": False, "error": "phase_runner_already_active"}
            self._error = None
            self._last_result = None
            self._stop_requested.clear()

            def _run() -> None:
                try:
                    result = run_phase(self.workspace_root, phase)
                    if self._stop_requested.is_set():
                        result = {**result, "stopped": True}
                    self._last_result = result
                    if result.get("ok"):
                        adv = on_phase_complete(self.workspace_root, phase)
                        self._last_result = {**result, "advance": adv}
                        if (
                            not self._stop_requested.is_set()
                            and adv.get("action") == "auto_start"
                            and adv.get("start_phase")
                        ):
                            # Chain next phase automatically (not REAL)
                            nxt = str(adv["start_phase"])
                            if nxt not in ("real", "birth"):
                                logger.info("maturity.auto_evolve.start phase=%s", nxt)
                                nested = run_phase(self.workspace_root, nxt)
                                self._last_result = {
                                    "ok": bool(nested.get("ok")),
                                    "chained": [phase, nxt],
                                    "results": [result, nested],
                                    "advance": on_phase_complete(self.workspace_root, nxt)
                                    if nested.get("ok")
                                    else {},
                                }
                    else:
                        self._error = str(
                            result.get("error")
                            or result.get("missing")
                            or result.get("next_step")
                            or "failed"
                        )
                except Exception as exc:
                    logger.exception("maturity.runner_failed phase=%s", phase)
                    self._error = str(exc)
                    self._last_result = {"ok": False, "error": str(exc)}

            self._thread = threading.Thread(
                target=_run, daemon=True, name=f"MaturityPhase-{phase}"
            )
            self._thread.start()
        return {"ok": True, "status": "started", "phase": phase}

    def stop_phase(self) -> dict[str, Any]:
        self._stop_requested.set()
        return {
            "ok": True,
            "running": self.is_running(),
            "stop_requested": True,
            "message": "Stop requested; active runner finishes current step then halts chaining",
        }

    def wipe_phase(self, phase: str, *, confirm: bool) -> dict[str, Any]:
        return wipe_phase(self.workspace_root, phase, confirm=confirm)

    def wipe_all(self, *, confirm: bool) -> dict[str, Any]:
        return wipe_all_maturation(self.workspace_root, confirm=confirm)

    def advance(self, *, confirm: bool = True, telegram_token: str | None = None) -> dict[str, Any]:
        if telegram_token:
            conf = confirm_telegram_advance(self.workspace_root, token=telegram_token)
            if not conf.get("ok"):
                return conf
            phase = str(conf.get("start_phase") or "")
            return self.start_phase(phase, explicit_user_start=True)
        if not confirm:
            return {"ok": False, "error": "confirm required"}
        hub = self.get_hub()
        nxt = hub.get("next_phase")
        if not nxt:
            return {"ok": False, "error": "no_next_phase"}
        return self.start_phase(str(nxt), explicit_user_start=True)

    def mark_birth_complete_from_artifacts(self) -> dict[str, Any]:
        """Called when birth finishes successfully — durable hub checkpoint.

        H7 / ADR-0036: marks Birth exit (survival). Does not require Perfect Birth,
        promotion gate, or READY_FOR_REAL.
        """
        from lumina_core.maturity.birth_exit import evaluate_birth_exit
        from lumina_core.maturity.continuum import _birth_learned_snapshot

        data = load_continuum(self.workspace_root)
        completed = set(data.get("completed_phases") or [])
        if "genesis" not in completed:
            mark_phase_completed(
                self.workspace_root,
                "genesis",
                learned={"note": "setup"},
                exit_proofs=["setup"],
            )
        already = "birth" in completed
        learned = _birth_learned_snapshot(self.workspace_root)
        exit_decision = evaluate_birth_exit(self.workspace_root)
        learned["birth_exit"] = exit_decision.to_dict()
        exit_proofs = list(exit_decision.proofs) or ["birth_complete"]
        if already:
            return {
                "ok": True,
                "already_complete": True,
                "birth_exit": exit_decision.to_dict(),
                "continuum": load_continuum(self.workspace_root),
                "advance": {"action": "hub"},
            }
        mark_phase_completed(
            self.workspace_root,
            "birth",
            learned=learned,
            exit_proofs=exit_proofs,
        )
        adv = on_phase_complete(self.workspace_root, "birth")
        if adv.get("action") == "auto_start" and adv.get("start_phase"):
            self.start_phase(str(adv["start_phase"]), explicit_user_start=True)
        return {
            "ok": True,
            "birth_exit": exit_decision.to_dict(),
            "continuum": load_continuum(self.workspace_root),
            "advance": adv,
        }

    def birth_exit_status(self) -> dict[str, Any]:
        """H7: Birth exit vs maturation panel for hub/API."""
        from lumina_core.maturity.birth_exit import birth_exit_status_payload

        return birth_exit_status_payload(self.workspace_root)

    def honesty_status(self) -> dict[str, Any]:
        """M6: continuum / READY / REAL eligibility honesty board."""
        from lumina_core.maturity.continuum_honesty import continuum_honesty_snapshot

        return continuum_honesty_snapshot(self.workspace_root)


maturity_service = MaturityService.instance()

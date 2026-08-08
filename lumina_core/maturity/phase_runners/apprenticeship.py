"""Apprenticeship runner — multi-day SIM stability (real MultiDaySimRunner bridge)."""
from __future__ import annotations

import os
from pathlib import Path
from typing import Any

from lumina_core.logging_utils import get_logger
from lumina_core.maturity.continuum import mark_phase_failed, mark_phase_running
from lumina_core.maturity.phase_runners.common import cfg, finish_from_exit_eval, write_phase_progress

logger = get_logger("lumina.maturity.runners.apprenticeship")


def run_apprenticeship(workspace_root: Path | str) -> dict[str, Any]:
    root = Path(workspace_root).resolve()
    mark_phase_running(root, "apprenticeship", learned={"status": "stability_check"})
    write_phase_progress(root, "apprenticeship", progress_pct=5.0, message="Loading SIM stability report")
    previous_cwd = Path.cwd()
    try:
        os.chdir(root)
        report: dict[str, Any] = {}
        try:
            from lumina_core.maturity.maturation_progress import sync_stability_milestone

            sync_stability_milestone(root)
        except Exception as exc:
            logger.debug("apprenticeship.stability_sync: %s", exc)

        write_phase_progress(root, "apprenticeship", progress_pct=25.0, message="Generating stability report")
        try:
            from lumina_core.engine.sim_stability_checker import generate_stability_report

            report = generate_stability_report() or {}
        except Exception as exc:
            logger.debug("apprenticeship.report: %s", exc)
            report = {"error": str(exc)}

        ready = bool(report.get("READY_FOR_REAL"))
        green = int(report.get("consecutive_green_days", 0) or 0)
        min_green = cfg().apprenticeship_min_green_days
        multi_day: dict[str, Any] = {}

        write_phase_progress(
            root,
            "apprenticeship",
            progress_pct=35.0 if not ready else 95.0,
            message="READY_FOR_REAL" if ready else f"Green days {green}/{min_green}",
            learned={
                "ready_for_real": ready,
                "consecutive_green_days": green,
                "min_green_days": min_green,
                "note": "Apprenticeship: multi-day SIM stability (strict)",
            },
        )

        if not ready:
            sim_days = cfg().apprenticeship_sim_days
            if sim_days > 0:
                write_phase_progress(
                    root,
                    "apprenticeship",
                    progress_pct=50.0,
                    message=f"Running multi-day SIM ({sim_days} days)",
                )
                from lumina_core.maturity.apprenticeship_sim import run_apprenticeship_multi_day_sim

                multi_day = run_apprenticeship_multi_day_sim(root, days=sim_days)
                write_phase_progress(
                    root,
                    "apprenticeship",
                    progress_pct=80.0,
                    message="Multi-day SIM finished — re-evaluating stability",
                    learned={"multi_day_sim": multi_day},
                    extra={"multi_day_sim": multi_day},
                )
                try:
                    from lumina_core.maturity.maturation_progress import sync_stability_milestone

                    sync_stability_milestone(root)
                    from lumina_core.engine.sim_stability_checker import generate_stability_report

                    report = generate_stability_report() or report
                    ready = bool(report.get("READY_FOR_REAL"))
                    green = int(report.get("consecutive_green_days", 0) or 0)
                except Exception as exc:
                    logger.debug("apprenticeship.post_sim_report: %s", exc)

        if ready:
            try:
                from lumina_core.maturity.milestone_hooks import hook_sim_real_guard_stable

                hook_sim_real_guard_stable(
                    root, consecutive_green_days=green, source="apprenticeship_runner"
                )
            except Exception:
                from lumina_core.maturity.maturation_progress import record_maturation_milestone

                record_maturation_milestone(
                    root,
                    "sim_real_guard_stable",
                    metadata={"consecutive_green_days": green, "source": "apprenticeship_runner"},
                )

        write_phase_progress(
            root,
            "apprenticeship",
            progress_pct=95.0,
            message="Evaluating exit proofs",
            learned={
                "ready_for_real": ready,
                "consecutive_green_days": green,
                "stability_failures": report.get("failures") if isinstance(report, dict) else None,
                "multi_day_sim": multi_day or None,
            },
        )

        result = finish_from_exit_eval(
            root,
            "apprenticeship",
            default_proofs=["sim_real_guard_stable"],
        )
        if result.get("ok"):
            write_phase_progress(root, "apprenticeship", progress_pct=100.0, message="Apprenticeship complete")
        else:
            failures = report.get("failures") if isinstance(report, dict) else []
            fail_txt = f" Remaining criteria: {failures}." if failures else ""
            sim_note = ""
            if multi_day:
                sim_note = (
                    f" Multi-day wrote {multi_day.get('days_written', 0)}/"
                    f"{multi_day.get('days_requested', 0)} day files."
                )
            result["next_step"] = (
                f"Need READY_FOR_REAL / ≥{min_green} consecutive green SIM days "
                f"(now {green}).{sim_note}{fail_txt} Resume this phase after more SIM evidence."
            )
            result["status"] = "incomplete"
            result["multi_day_sim"] = multi_day
            result["stability_report"] = {
                "READY_FOR_REAL": ready,
                "consecutive_green_days": green,
                "failures": failures,
            }
        return result
    except Exception as exc:
        logger.exception("apprenticeship.failed")
        mark_phase_failed(root, "apprenticeship", error=str(exc))
        return {"ok": False, "error": str(exc)}
    finally:
        try:
            os.chdir(previous_cwd)
        except Exception:
            pass

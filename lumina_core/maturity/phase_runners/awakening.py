"""Awakening runner — evolution proof + twin observability (strict)."""
from __future__ import annotations

from pathlib import Path
from typing import Any

from lumina_core.logging_utils import get_logger
from lumina_core.maturity.continuum import mark_phase_failed, mark_phase_running
from lumina_core.maturity.maturation_progress import record_maturation_milestone
from lumina_core.maturity.phase_runners.common import cfg, finish_from_exit_eval, write_phase_progress

logger = get_logger("lumina.maturity.runners.awakening")


def run_awakening(workspace_root: Path | str) -> dict[str, Any]:
    root = Path(workspace_root)
    mark_phase_running(root, "awakening", learned={"status": "evaluating"})
    write_phase_progress(root, "awakening", progress_pct=5.0, message="Syncing birth → maturity")
    try:
        from lumina_core.maturity.maturation_progress import sync_maturation_from_birth_state

        sync_maturation_from_birth_state(root)

        evo_ok = False
        evo_meta: dict[str, Any] = {}
        write_phase_progress(root, "awakening", progress_pct=30.0, message="Checking evolution proof vs birth fitness vector")
        try:
            from lumina_core.maturity.post_birth_skill_gates import (
                awakening_evolution_proof_from_fitness,
            )
            from lumina_core.birth.evolution_proof_gate import load_evolution_proof_record

            rec = load_evolution_proof_record(root) or {}
            ep = awakening_evolution_proof_from_fitness(
                root,
                polish_oos_winrate=(
                    float(rec["oos_winrate"]) if rec.get("oos_winrate") is not None else None
                ),
                holdout_trades=int(rec.get("holdout_trades") or 0),
            )
            evo_ok = bool(ep.passed)
            evo_meta = dict(ep.detail)
            if evo_ok:
                record_maturation_milestone(root, "evolution_proof_passed", metadata=evo_meta)
                try:
                    from lumina_core.maturity.milestone_hooks import hook_evolution_proof_passed

                    hook_evolution_proof_passed(
                        root,
                        oos_winrate=float(evo_meta.get("probe_oos_wr") or 0.0),
                        lift=None,
                    )
                except Exception:
                    pass
        except Exception as exc:
            logger.debug("awakening.evolution_proof_fail_closed: %s", exc)
            evo_ok = False
            evo_meta = {"error": str(exc)}

        write_phase_progress(root, "awakening", progress_pct=60.0, message="Probing twin observability")
        twin_samples = _twin_sample_count(root)
        min_samples = cfg().awakening_min_twin_samples
        twin_ok = twin_samples >= min_samples

        write_phase_progress(
            root,
            "awakening",
            progress_pct=90.0,
            message="Evaluating exit proofs",
            learned={
                "evolution_proof_ok": evo_ok,
                "twin_samples": twin_samples,
                "twin_min_required": min_samples,
                "twin_ok": twin_ok,
                "note": "Awakening: prefer better policies (strict exit)",
                **{k: v for k, v in evo_meta.items() if v is not None},
            },
        )

        result = finish_from_exit_eval(
            root,
            "awakening",
            default_proofs=["evolution_proof_passed", "twin_observability"],
        )
        if result.get("ok"):
            write_phase_progress(root, "awakening", progress_pct=100.0, message="Awakening complete")
        return result
    except Exception as exc:
        logger.exception("awakening.failed")
        mark_phase_failed(root, "awakening", error=str(exc))
        return {"ok": False, "error": str(exc)}


def _twin_sample_count(workspace_root: Path) -> int:
    summary = workspace_root / "state" / "twin_mode_metrics_summary.json"
    if not summary.is_file():
        return 0
    try:
        import json

        raw = json.loads(summary.read_text(encoding="utf-8"))
        return int(raw.get("samples", 0) or 0)
    except Exception:
        return 0

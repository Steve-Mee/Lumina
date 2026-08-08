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
        write_phase_progress(root, "awakening", progress_pct=30.0, message="Checking evolution proof")
        try:
            from lumina_core.birth.evolution_proof_gate import (
                evolution_proof_passed,
                load_evolution_proof_record,
            )

            evo_ok = bool(evolution_proof_passed(root))
            if evo_ok:
                rec = load_evolution_proof_record(root) or {}
                evo_meta = {"oos_winrate": rec.get("oos_winrate"), "lift": rec.get("lift")}
                record_maturation_milestone(root, "evolution_proof_passed", metadata=evo_meta)
                try:
                    from lumina_core.maturity.milestone_hooks import hook_evolution_proof_passed

                    hook_evolution_proof_passed(
                        root,
                        oos_winrate=float(rec.get("oos_winrate") or 0.0),
                        lift=rec.get("lift"),
                    )
                except Exception:
                    pass
        except Exception as exc:
            logger.debug("awakening.evolution_proof_skip: %s", exc)

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

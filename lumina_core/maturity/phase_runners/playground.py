"""Playground runner — deck unlock, envelope seal, first SIM order evidence."""
from __future__ import annotations

from pathlib import Path
from typing import Any

from lumina_core.logging_utils import get_logger
from lumina_core.maturity.continuum import mark_phase_failed, mark_phase_running
from lumina_core.maturity.maturation_progress import record_maturation_milestone
from lumina_core.maturity.phase_runners.common import finish_from_exit_eval, write_phase_progress
from lumina_core.maturity.phase_specs import _sim_envelope_sealed

logger = get_logger("lumina.maturity.runners.playground")


def run_playground(workspace_root: Path | str) -> dict[str, Any]:
    root = Path(workspace_root)
    mark_phase_running(root, "playground", learned={"status": "unlocking_deck"})
    write_phase_progress(root, "playground", progress_pct=10.0, message="Unlocking Command Deck")
    try:
        record_maturation_milestone(root, "deck_unlocked", metadata={"source": "playground_runner"})
        try:
            from lumina_core.maturity.maturation_progress import sync_maturation_from_birth_state

            sync_maturation_from_birth_state(root)
        except Exception:
            pass

        write_phase_progress(root, "playground", progress_pct=40.0, message="Checking SIM envelope seal")
        sealed = _sim_envelope_sealed(root)

        economic_detail: dict[str, Any] = {}
        try:
            from lumina_core.birth.fitness_vector import load_fitness_vector
            from lumina_core.maturity.post_birth_skill_gates import economic_viability

            vec = load_fitness_vector(root)
            econ = economic_viability(
                mean_r=None if vec is None else vec.mean_r,
                skill_wr=None if vec is None else vec.oos_wr,
                breakeven_wr=None,
            )
            # Birth fitness is the baseline, not Playground pass. Record home of the gate.
            economic_detail = {
                "gate_home": "playground",
                "relocated_from": "birth_runway_stage5_profit_val",
                "birth_baseline_mean_r": None if vec is None else vec.mean_r,
                "birth_baseline_oos_wr": None if vec is None else vec.oos_wr,
                "note": "Economic viability (mean R≥0 and WR≥BE) is graded on Playground SIM tape, not Birth.",
                "baseline_not_sufficient": (not econ.passed),
            }
        except Exception as exc:
            economic_detail = {"error": str(exc)}

        write_phase_progress(root, "playground", progress_pct=70.0, message="Probing first SIM order path")
        probe = _first_sim_order_probe(root)
        if probe.get("ok"):
            record_maturation_milestone(
                root,
                "first_sim_order_placed",
                metadata={"source": "playground_probe", **{k: v for k, v in probe.items() if k != "ok"}},
            )
            write_phase_progress(
                root,
                "playground",
                extra={"probe": probe},
                learned={"first_sim_order_probe": probe},
            )
        else:
            write_phase_progress(
                root,
                "playground",
                extra={"probe": probe},
                learned={
                    "first_sim_order_probe": probe,
                    "next_step": probe.get("next_step")
                    or "Place a SIM order from Command Deck or seal envelope",
                },
            )

        write_phase_progress(
            root,
            "playground",
            progress_pct=90.0,
            message="Evaluating exit proofs",
            learned={
                "deck_unlocked": True,
                "sim_envelope_sealed": sealed,
                "economic_viability_gate": economic_detail,
                "note": "Playground: crawl safely in SIM; economic skill (WR≥BE) lives here, not Birth.",
            },
        )

        result = finish_from_exit_eval(
            root,
            "playground",
            default_proofs=["deck_unlocked", "sim_envelope_sealed", "first_sim_order_placed"],
        )
        if result.get("ok"):
            write_phase_progress(root, "playground", progress_pct=100.0, message="Playground complete")
        elif not sealed:
            result["next_step"] = "Seal the SIM risk envelope (PlaygroundEnvelopeSeal UI)"
        return result
    except Exception as exc:
        logger.exception("playground.failed")
        mark_phase_failed(root, "playground", error=str(exc))
        return {"ok": False, "error": str(exc)}


def _first_sim_order_probe(workspace_root: Path) -> dict[str, Any]:
    """Evidence of a real SIM order — health flags are not an order."""
    try:
        from lumina_core.maturity.maturation_progress import load_maturation_progress

        if "first_sim_order_placed" in load_maturation_progress(workspace_root).milestones_reached:
            return {"ok": True, "source": "milestone_existing"}
    except Exception:
        pass

    p = workspace_root / "state" / "first_sim_order.json"
    if p.is_file():
        try:
            import json

            raw = json.loads(p.read_text(encoding="utf-8"))
            if isinstance(raw, dict) and (
                raw.get("order_id") or raw.get("placed") is True or raw.get("ok") is True
            ):
                return {
                    "ok": True,
                    "source": "state/first_sim_order.json",
                    "order_id": raw.get("order_id"),
                }
        except Exception:
            pass

    return {
        "ok": False,
        "reason": "no_first_order_evidence",
        "next_step": "Open Command Deck and place first SIM order, or write state/first_sim_order.json with order_id",
    }

"""Proving Ground runner — shadow / promotion evidence (fail-closed)."""
from __future__ import annotations

from pathlib import Path
from typing import Any

from lumina_core.logging_utils import get_logger
from lumina_core.maturity.continuum import mark_phase_failed, mark_phase_running
from lumina_core.maturity.phase_runners.common import finish_from_exit_eval, write_phase_progress
from lumina_core.maturity.shadow_helpers import (
    record_insufficient_shadow_evidence,
    run_shadow_promotion_gate,
    shadow_gate_passed_from_audit,
)

logger = get_logger("lumina.maturity.runners.proving")


def run_proving_ground(workspace_root: Path | str) -> dict[str, Any]:
    root = Path(workspace_root)
    mark_phase_running(root, "proving_ground", learned={"status": "shadow_promotion"})
    write_phase_progress(root, "proving_ground", progress_pct=10.0, message="Scanning promotion audit")
    try:
        passed, meta = shadow_gate_passed_from_audit(root)
        write_phase_progress(
            root,
            "proving_ground",
            progress_pct=40.0,
            message="Audit pass found" if passed else "No pass in audit — evaluating",
            learned={"audit_pass": passed, "audit_meta": {k: meta.get(k) for k in ("mode", "dna_hash", "shadow_status") if k in meta}},
        )

        if passed:
            run_shadow_promotion_gate(root)
        else:
            # Attempt structured gate via autopilot-compatible path only (no fake pass)
            write_phase_progress(
                root,
                "proving_ground",
                progress_pct=70.0,
                message="Recording insufficient shadow evidence if still missing",
            )
            # Re-check after any side effects
            passed2, _ = shadow_gate_passed_from_audit(root)
            if not passed2:
                record_insufficient_shadow_evidence(
                    root,
                    reason="insufficient_shadow_evidence",
                )

        write_phase_progress(root, "proving_ground", progress_pct=90.0, message="Evaluating exit proofs + cert OOS walls")
        run_shadow_promotion_gate(root)
        cert_gate: dict[str, Any] = {}
        try:
            from lumina_core.maturity.post_birth_skill_gates import (
                certificate_oos_walls,
                load_certificate_oos_fields,
            )

            fields = load_certificate_oos_fields(root)
            cert = certificate_oos_walls(
                oos_wr=fields.get("oos_wr"),
                oos_sharpe=fields.get("oos_sharpe"),
                max_dd_pct=fields.get("max_dd_pct"),
            )
            cert_gate = cert.to_dict()
            write_phase_progress(
                root,
                "proving_ground",
                learned={"certificate_oos_walls": cert_gate},
            )
        except Exception as exc:
            cert_gate = {"error": str(exc)}

        result = finish_from_exit_eval(
            root,
            "proving_ground",
            default_proofs=["promotion_gate_passed"],
        )
        result["certificate_oos_walls"] = cert_gate
        if result.get("ok"):
            write_phase_progress(root, "proving_ground", progress_pct=100.0, message="Proving Ground complete")
        else:
            result["next_step"] = (
                "Need shadow validation or promotion gate pass in "
                "state/promotion_gate_audit.jsonl (passed/promoted=true). "
                "Run evolution shadow / promotion pipeline, then retry."
            )
            result["status"] = "incomplete"
        return result
    except Exception as exc:
        logger.exception("proving.failed")
        mark_phase_failed(root, "proving_ground", error=str(exc))
        return {"ok": False, "error": str(exc)}

"""Make-before-break cutover, flatten gate, freeze restore (K10–K12)."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from lumina_core.evolution.challenger_health import evaluate_challenger_health
from lumina_core.code_evolution.runtime_role import CHAMPION, CHALLENGER
from lumina_core.evolution.artifacts import (
    ArtifactBundle,
    bundle_complete_for_swap,
    freeze_bundle,
    load_bundle,
    read_pointer,
    write_pointer,
)


def has_open_position(positions: list[Any] | None) -> bool:
    for pos in positions or []:
        qty = 0.0
        if isinstance(pos, dict):
            qty = float(pos.get("qty") or pos.get("quantity") or 0.0)
        else:
            qty = float(getattr(pos, "qty", 0.0) or 0.0)
        if abs(qty) > 1e-12:
            return True
    return False


def freeze_champion(workspace: Path | str, bundle: ArtifactBundle) -> ArtifactBundle:
    frozen = freeze_bundle(
        workspace,
        artifact_id=f"freeze_{bundle.artifact_id}",
        role=CHAMPION,
        overlay_digest=bundle.overlay_digest,
        dna_hash=bundle.dna_hash,
        policy_zip=bundle.policy_zip,
        schema_ledger=bundle.schema_ledger,
        requires_org_cols=bundle.requires_org_cols,
    )
    write_pointer(
        workspace,
        CHAMPION,
        {"artifact_id": frozen.artifact_id, "content_digest": frozen.content_digest, "frozen": True},
    )
    return frozen


def try_swap(
    workspace: Path | str,
    *,
    challenger: ArtifactBundle,
    positions: list[Any] | None,
    challenger_health_green: bool,
    heartbeat_alive: bool | None = None,
    overlay_loaded: bool | None = None,
    schema_match: bool | None = None,
    open_crit_violations: int = 0,
    fabric_ok: bool = True,
) -> dict[str, Any]:
    """K10/K11: refuse incomplete bundle or open positions. Pointer flip last."""
    before = read_pointer(workspace, CHAMPION)
    if heartbeat_alive is not None or overlay_loaded is not None or schema_match is not None:
        health = evaluate_challenger_health(
            heartbeat_alive=bool(heartbeat_alive if heartbeat_alive is not None else challenger_health_green),
            overlay_loaded=bool(overlay_loaded if overlay_loaded is not None else challenger_health_green),
            schema_match=bool(schema_match if schema_match is not None else challenger_health_green),
            open_crit_violations=int(open_crit_violations),
            fabric_ok=bool(fabric_ok),
        )
        if not health["green"]:
            return {"swapped": False, "reason": f"challenger_health_{health['reason']}", "pointer": before}
    elif not challenger_health_green:
        return {"swapped": False, "reason": "challenger_health_not_green", "pointer": before}
    if has_open_position(positions):
        notify_flatten_or_abort(workspace)
        return {"swapped": False, "reason": "open_position", "pointer": before}
    missing = bundle_complete_for_swap(challenger)
    if missing:
        return {"swapped": False, "reason": "incomplete_bundle", "fail_reasons": missing, "pointer": before}

    write_pointer(
        workspace,
        CHAMPION,
        {
            "artifact_id": challenger.artifact_id,
            "content_digest": challenger.content_digest,
            "role": CHAMPION,
            "from_challenger": True,
        },
    )
    write_pointer(workspace, CHALLENGER, {"artifact_id": None, "cleared": True})
    return {"swapped": True, "reason": "ok", "pointer": read_pointer(workspace, CHAMPION)}


def restore_champion(workspace: Path | str, freeze_id: str) -> dict[str, Any]:
    frozen = load_bundle(workspace, freeze_id)
    if frozen is None:
        return {"restored": False, "reason": "freeze_missing"}
    write_pointer(
        workspace,
        CHAMPION,
        {"artifact_id": frozen.artifact_id, "content_digest": frozen.content_digest, "restored": True},
    )
    return {
        "restored": True,
        "reason": "ok",
        "content_digest": frozen.content_digest,
        "artifact_id": frozen.artifact_id,
    }


def chaos_drill(
    workspace: Path | str,
    *,
    champion: ArtifactBundle,
    challenger: ArtifactBundle,
) -> dict[str, Any]:
    """K12: freeze → swap → force fail → restore digest match."""
    frozen = freeze_champion(workspace, champion)
    swapped = try_swap(
        workspace,
        challenger=challenger,
        positions=[],
        challenger_health_green=True,
    )
    restored = restore_champion(workspace, frozen.artifact_id)
    match = str(restored.get("content_digest") or "") == frozen.content_digest
    return {
        "ok": bool(swapped.get("swapped") and restored.get("restored") and match),
        "frozen_digest": frozen.content_digest,
        "restored_digest": restored.get("content_digest"),
        "match": match,
    }


def flatten_timeout_message() -> str:
    return "flatten or abort — swap blocked while a position is open"


def notify_flatten_or_abort(workspace: Path | str) -> dict[str, Any]:
    from lumina_core.evolution.council import compose_dossier
    from lumina_core.evolution.council_notify import notify_council

    dossier = compose_dossier(
        question=flatten_timeout_message(),
        twin_values_ok=True,
        constitution_violations=0,
        risk_dd=0.0,
        swarm_fitness_delta=0.0,
        evolution_proof_passed=True,
    )
    return notify_council(workspace, "sim", dossier)

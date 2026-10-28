"""Phase 2 productive SIM campaign (H3) — shadow after Perfect Birth, optional SIM apply.

Persists operator/campaign activation under ``state/phase2_sim_campaign.json`` so
Phase 2 pillars run without editing config.yaml. REAL mode never receives apply
from this module.
"""
from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Literal

from lumina_core.birth.phase2_autonomy.execution_mode import (
    compute_shadow_evidence_from_rows,
    max_execution_mode,
    normalize_execution_mode,
)
from lumina_core.birth.phase2_autonomy.features import Phase2AutonomyFeatures
from lumina_core.birth.phase2_autonomy.metrics import load_phase2_recent_decisions
from lumina_core.logging_utils import get_logger

logger = get_logger("lumina.birth.phase2.sim_campaign")

CAMPAIGN_REL = Path("state") / "phase2_sim_campaign.json"
CampaignMode = Literal["shadow", "apply", "disabled"]


def campaign_path(workspace_root: Path | str) -> Path:
    return Path(workspace_root) / CAMPAIGN_REL


def _utcnow() -> str:
    return datetime.now(timezone.utc).isoformat()


def load_sim_campaign(workspace_root: Path | str) -> dict[str, Any] | None:
    path = campaign_path(workspace_root)
    if not path.is_file():
        return None
    try:
        raw = json.loads(path.read_text(encoding="utf-8"))
        return raw if isinstance(raw, dict) else None
    except Exception:
        return None


def save_sim_campaign(workspace_root: Path | str, data: dict[str, Any]) -> Path:
    path = campaign_path(workspace_root)
    path.parent.mkdir(parents=True, exist_ok=True)
    payload = dict(data)
    payload["updated_at"] = _utcnow()
    path.write_text(json.dumps(payload, ensure_ascii=True, indent=2), encoding="utf-8")
    return path


def disable_sim_campaign(workspace_root: Path | str) -> dict[str, Any]:
    root = Path(workspace_root)
    data = {
        "active": False,
        "mode": "disabled",
        "pillars": {},
        "reason": "disabled",
        "disabled_at": _utcnow(),
    }
    path = save_sim_campaign(root, data)
    return {"ok": True, "active": False, "path": str(path)}


def enable_sim_observe_campaign(
    workspace_root: Path | str,
    *,
    source: str = "operator",
) -> dict[str, Any]:
    """R3 M5: Activate Phase 2 in **observe** mode (propose+audit only).

    Does **not** require Perfect Birth — observe never mutates and never arms REAL.
    Shadow/apply still require PB unlock + evidence.
    """
    root = Path(workspace_root)
    data = {
        "active": True,
        "mode": "observe",
        "pillars": {
            "dynamic_wall": True,
            "self_adaptive_params": True,
            "instance_adapt": True,
        },
        # Observe may run pre-PB; shadow/apply re-check unlock on promote.
        "require_perfect_birth_flag": False,
        "require_perfect_birth_evidence": False,
        "allow_sim_scaffold": False,
        "require_twin_for_apply": True,
        "observe_only": True,
        "source": source,
        "unlocked_via": "observe_no_pb_required",
        "activated_at": _utcnow(),
        "sim_only": True,
        "real_apply_forbidden": True,
    }
    path = save_sim_campaign(root, data)
    logger.info("phase2.sim_campaign.observe_enabled path=%s", path)
    return {
        "ok": True,
        "active": True,
        "mode": "observe",
        "path": str(path),
        "campaign": data,
        "next_step": (
            "Run Birth/SIM; Phase 2 proposals audit only. "
            "After Perfect Birth: phase2_shadow_campaign.py --enable"
        ),
    }


def enable_sim_shadow_campaign(
    workspace_root: Path | str,
    *,
    allow_sim_scaffold: bool = False,
    source: str = "operator",
) -> dict[str, Any]:
    """Activate all pillars in shadow mode after Perfect Birth unlock (SIM product path).

    Fail-closed: requires perfect birth evidence unless allow_sim_scaffold (lab only).
    """
    root = Path(workspace_root)
    from lumina_core.birth.perfect_birth_gate import (
        DEFAULT_FLAG_REL,
        perfect_birth_unlock_valid,
    )

    flag = root / DEFAULT_FLAG_REL
    ok, detail = perfect_birth_unlock_valid(flag_path=flag, require_evidence=True)
    if not ok and not allow_sim_scaffold:
        return {
            "ok": False,
            "error": "perfect_birth_required",
            "detail": detail,
            "next_step": (
                "Declare Perfect Birth with real evidence "
                "(scripts/validation/declare_perfect_birth.py) then retry."
            ),
        }

    data = {
        "active": True,
        "mode": "shadow",
        "pillars": {
            "dynamic_wall": True,
            "self_adaptive_params": True,
            "instance_adapt": True,
        },
        "require_perfect_birth_flag": True,
        "require_perfect_birth_evidence": not allow_sim_scaffold,
        "allow_sim_scaffold": bool(allow_sim_scaffold),
        "require_twin_for_apply": True,
        "observe_only": False,
        "source": source,
        "unlocked_via": detail if ok else "sim_scaffold",
        "activated_at": _utcnow(),
        "promoted_from_observe": bool(
            (load_sim_campaign(root) or {}).get("mode") == "observe"
        ),
        "sim_only": True,
        "real_apply_forbidden": True,
    }
    path = save_sim_campaign(root, data)
    logger.info("phase2.sim_campaign.shadow_enabled path=%s scaffold=%s", path, allow_sim_scaffold)
    return {
        "ok": True,
        "active": True,
        "mode": "shadow",
        "path": str(path),
        "campaign": data,
    }


def promote_sim_apply_campaign(
    workspace_root: Path | str,
    *,
    min_shadow_samples: int = 8,
) -> dict[str, Any]:
    """Promote campaign mode shadow→apply for SIM only after shadow evidence.

    Never enables REAL capital mutation.
    """
    root = Path(workspace_root)
    camp = load_sim_campaign(root)
    if not camp or not camp.get("active"):
        return {"ok": False, "error": "no_active_campaign"}
    if str(camp.get("mode") or "") == "apply":
        return {"ok": True, "already": True, "mode": "apply", "campaign": camp}
    if str(camp.get("mode") or "") == "observe":
        return {
            "ok": False,
            "error": "observe_cannot_promote_to_apply",
            "next_step": (
                "Promote observe→shadow after Perfect Birth "
                "(python scripts/validation/phase2_shadow_campaign.py --enable), "
                "accumulate shadow evidence, then --promote-apply."
            ),
        }
    if str(camp.get("mode") or "") != "shadow":
        return {
            "ok": False,
            "error": "campaign_not_in_shadow",
            "mode": str(camp.get("mode") or ""),
            "next_step": "Enable shadow campaign first after Perfect Birth unlock.",
        }

    # Track B: promote to apply still requires Perfect Birth evidence (scaffold-only may skip).
    if not bool(camp.get("allow_sim_scaffold")):
        from lumina_core.birth.perfect_birth_gate import (
            DEFAULT_FLAG_REL,
            perfect_birth_unlock_valid,
        )

        ok, detail = perfect_birth_unlock_valid(
            flag_path=root / DEFAULT_FLAG_REL,
            require_evidence=True,
        )
        if not ok:
            return {
                "ok": False,
                "error": "perfect_birth_required",
                "detail": detail,
                "next_step": (
                    "Declare Perfect Birth with conjunction evidence before SIM apply promote."
                ),
            }

    rows = load_phase2_recent_decisions(limit=200, window_hours=72)
    evidence = compute_shadow_evidence_from_rows(rows)
    if not evidence.get("promote_to_apply"):
        return {
            "ok": False,
            "error": "shadow_evidence_insufficient",
            "evidence": evidence,
            "next_step": (
                f"Need ≥{min_shadow_samples} shadow decisions with adequate "
                "shadow_would_apply rate; keep birth/SIM running under shadow campaign."
            ),
        }

    camp["mode"] = "apply"
    camp["promoted_to_apply_at"] = _utcnow()
    camp["promotion_evidence"] = evidence
    camp["sim_only"] = True
    camp["real_apply_forbidden"] = True
    path = save_sim_campaign(root, camp)
    logger.info("phase2.sim_campaign.promoted_apply path=%s", path)
    return {"ok": True, "mode": "apply", "path": str(path), "evidence": evidence, "campaign": camp}


def resolve_features_with_campaign(
    cfg: Any | None,
    workspace_root: Path | str | None = None,
) -> Phase2AutonomyFeatures:
    """Merge curriculum Phase 2 features with active SIM campaign.

    Product rules (current Lumina SSOT):
    - Campaign **enables** Phase 2 without config.yaml edits (master + pillars).
    - Campaign may **raise** execution authority (observe→shadow→apply).
    - Campaign must **not demote** an explicit curriculum closed-loop
      (e.g. leftover observe campaign must not strip ``phase2_execution_mode=apply``).
    - REAL capital never armed here (orchestrator/gate still fail-closed).
    """
    base = Phase2AutonomyFeatures.from_curriculum_cfg(cfg)
    if workspace_root is None:
        return base
    camp = load_sim_campaign(workspace_root)
    if not camp or not camp.get("active"):
        return base

    camp_mode = normalize_execution_mode(str(camp.get("mode") or "shadow"))
    base_mode = normalize_execution_mode(base.execution_mode)
    # Monotonic merge: highest SIM productivity wins.
    # Pure campaign path (curriculum master off) → campaign mode only.
    # Curriculum intentionally on → max(campaign, curriculum).
    if base.enabled:
        mode = max_execution_mode(camp_mode, base_mode).value
    else:
        mode = camp_mode.value

    pillars = camp.get("pillars") if isinstance(camp.get("pillars"), dict) else {}
    camp_scaffold = bool(camp.get("allow_sim_scaffold", False))
    scaffold = bool(camp_scaffold or base.allow_sim_scaffold)

    # Perfect Birth: observe is always pre-PB safe. Shadow/apply need PB unless
    # curriculum lab scaffold (or campaign scaffold) already authorizes SIM mutate.
    if mode == "observe":
        require_pb_flag = False
        require_pb_evidence = False
    elif base.enabled and (base.allow_sim_scaffold or not base.require_perfect_birth_flag):
        # Explicit curriculum closed-loop / lab path keeps its PB policy.
        require_pb_flag = bool(base.require_perfect_birth_flag)
        require_pb_evidence = bool(base.require_perfect_birth_evidence)
        scaffold = bool(base.allow_sim_scaffold or camp_scaffold)
    else:
        # Campaign product path: shadow/apply after Perfect Birth (unless scaffold).
        require_pb_flag = True
        require_pb_evidence = not scaffold

    return Phase2AutonomyFeatures(
        enabled=True,
        dynamic_wall_enabled=bool(pillars.get("dynamic_wall", True))
        or bool(base.dynamic_wall_enabled),
        self_adaptive_params_enabled=bool(pillars.get("self_adaptive_params", True))
        or bool(base.self_adaptive_params_enabled),
        instance_adapt_enabled=bool(pillars.get("instance_adapt", True))
        or bool(base.instance_adapt_enabled),
        require_perfect_birth_flag=require_pb_flag,
        allow_sim_scaffold=scaffold,
        require_twin_for_apply=bool(
            camp.get("require_twin_for_apply", base.require_twin_for_apply)
        ),
        perfect_birth_flag_path=base.perfect_birth_flag_path,
        require_perfect_birth_evidence=require_pb_evidence,
        recheck_perfect_birth_kpis=base.recheck_perfect_birth_kpis,
        execution_mode=mode,
    )


def sim_campaign_status(
    workspace_root: Path | str,
    *,
    cfg: Any | None = None,
) -> dict[str, Any]:
    """Operator status: campaign + unlock + shadow promotion readiness.

    When ``cfg`` is provided, also reports **effective** Phase 2 features after
    curriculum×campaign merge (runtime SSOT used by BirthHandlerRegistry).
    """
    root = Path(workspace_root)
    camp = load_sim_campaign(root)
    from lumina_core.birth.perfect_birth_gate import DEFAULT_FLAG_REL, perfect_birth_unlock_valid

    unlock_ok, unlock_detail = perfect_birth_unlock_valid(
        flag_path=root / DEFAULT_FLAG_REL,
        require_evidence=True,
    )
    rows = load_phase2_recent_decisions(limit=200, window_hours=72)
    evidence = compute_shadow_evidence_from_rows(rows)
    active = bool(camp and camp.get("active"))
    mode = str((camp or {}).get("mode") or "disabled")
    can_enable_observe = not active
    can_enable_shadow = unlock_ok and (not active or mode == "observe")
    effective: dict[str, Any] | None = None
    if cfg is not None:
        feat = resolve_features_with_campaign(cfg, root)
        effective = {
            "enabled": bool(feat.enabled),
            "execution_mode": str(feat.execution_mode),
            "allow_sim_scaffold": bool(feat.allow_sim_scaffold),
            "require_perfect_birth_flag": bool(feat.require_perfect_birth_flag),
            "dynamic_wall_enabled": bool(feat.dynamic_wall_enabled),
            "self_adaptive_params_enabled": bool(feat.self_adaptive_params_enabled),
            "instance_adapt_enabled": bool(feat.instance_adapt_enabled),
            "merge_policy": "campaign_enable_raise_no_demote",
        }
    return {
        "campaign_active": active,
        "mode": mode if active else "disabled",
        "campaign": camp,
        "effective_features": effective,
        "perfect_birth_unlock": unlock_ok,
        "perfect_birth_detail": unlock_detail,
        "shadow_promotion": evidence,
        "can_enable_observe": can_enable_observe,
        "can_enable_shadow": can_enable_shadow,
        "can_promote_sim_apply": bool(
            active and mode == "shadow" and evidence.get("promote_to_apply") and unlock_ok
        ),
        "real_apply_forbidden": True,
        "next_step": (
            "Enable observe campaign (pre-PB audit): phase2_shadow_campaign.py --observe"
            if not active and not unlock_ok
            else (
                "Enable SIM shadow campaign after Perfect Birth unlock."
                if unlock_ok and (not active or mode == "observe")
                else (
                    "Run birth/SIM so Phase 2 shadow decisions accumulate; then promote SIM apply."
                    if active and mode == "shadow" and not evidence.get("promote_to_apply")
                    else (
                        "SIM apply campaign active — still fail-closed for REAL capital."
                        if active and mode == "apply"
                        else (
                            "Observe active — audit only; close PB gaps then --enable shadow."
                            if active and mode == "observe"
                            else "Close Perfect Birth KPI gaps and declare evidence first."
                        )
                    )
                )
            )
        ),
    }


def build_phase2_shadow_campaign_ops_report(
    workspace_root: Path | str | None = None,
) -> dict[str, Any]:
    """T8: Ops report for Phase 2 SIM shadow after Perfect Birth (never arms REAL)."""
    root = Path(workspace_root) if workspace_root else Path.cwd()
    status = sim_campaign_status(root)
    unlock = bool(status.get("perfect_birth_unlock"))
    active = bool(status.get("campaign_active"))
    mode = str(status.get("mode") or "disabled")
    can_shadow = bool(status.get("can_enable_shadow"))
    can_apply = bool(status.get("can_promote_sim_apply"))
    shadow_ev = status.get("shadow_promotion") if isinstance(status.get("shadow_promotion"), dict) else {}

    ladder = [
        {
            "id": "observe_campaign",
            "title": "Phase 2 observe campaign (pre-PB audit, no mutate)",
            "ok": active and mode in {"observe", "shadow", "apply"},
            "actual": {"active": active, "mode": mode},
            "action": "python scripts/validation/phase2_shadow_campaign.py --observe",
        },
        {
            "id": "perfect_birth_unlock",
            "title": "Perfect Birth flag+evidence unlock",
            "ok": unlock,
            "actual": status.get("perfect_birth_detail"),
            "action": "python scripts/validation/perfect_birth_campaign.py then declare_perfect_birth.py",
        },
        {
            "id": "shadow_campaign_active",
            "title": "SIM shadow campaign active",
            "ok": active and mode in {"shadow", "apply"},
            "actual": {"active": active, "mode": mode},
            "action": (
                "python scripts/validation/phase2_shadow_campaign.py --enable"
                if unlock
                else "Unlock Perfect Birth first (no --scaffold in production)"
            ),
        },
        {
            "id": "shadow_evidence",
            "title": "Shadow decision evidence for SIM apply promote",
            "ok": bool(shadow_ev.get("promote_to_apply")) or mode == "apply",
            "actual": shadow_ev,
            "action": "Run birth/SIM under shadow campaign until promote_to_apply",
        },
        {
            "id": "sim_apply_optional",
            "title": "Optional SIM apply campaign (still not REAL)",
            "ok": mode == "apply" or not can_apply,
            "actual": mode,
            "action": "python scripts/validation/phase2_shadow_campaign.py --promote-apply",
        },
        {
            "id": "real_apply_forbidden",
            "title": "REAL capital apply hard-blocked",
            "ok": True,
            "actual": True,
            "action": "Never set phase2 apply for REAL; use multi-gate + human approve-real",
        },
    ]
    open_items = [x for x in ladder if not x["ok"]]
    actions: list[str] = []
    for x in open_items:
        a = str(x.get("action") or "")
        if a and a not in actions:
            actions.append(a)

    # R3 honesty: "ok" for shadow product path still requires PB+shadow; observe alone is partial
    product_ok = unlock and active and mode in {"shadow", "apply"}
    return {
        "schema": "phase2_shadow_campaign_ops_v1",
        "ok": product_ok,
        "observe_ready": active and mode in {"observe", "shadow", "apply"},
        "perfect_birth_unlock": unlock,
        "campaign_active": active,
        "mode": mode,
        "can_enable_observe": bool(status.get("can_enable_observe")),
        "can_enable_shadow": can_shadow,
        "can_promote_sim_apply": can_apply,
        "ladder": ladder,
        "open_items": [x["id"] for x in open_items],
        "ordered_actions": actions,
        "status": status,
        "policy": {
            "observe_without_perfect_birth": True,
            "shadow_requires_perfect_birth_evidence": True,
            "scaffold_lab_only": True,
            "real_apply_forbidden": True,
            "twin_required_for_apply": True,
            "never_arms_real_capital": True,
        },
        "commands": {
            "status": "python scripts/validation/phase2_shadow_campaign.py",
            "observe": "python scripts/validation/phase2_shadow_campaign.py --observe",
            "enable": "python scripts/validation/phase2_shadow_campaign.py --enable",
            "disable": "python scripts/validation/phase2_shadow_campaign.py --disable",
            "promote_apply": "python scripts/validation/phase2_shadow_campaign.py --promote-apply",
            "pb_campaign": "python scripts/validation/perfect_birth_campaign.py",
            "r2_cadence": "python scripts/validation/birth_zero_human_cadence.py",
        },
        "next_step": status.get("next_step"),
    }


__all__ = [
    "CAMPAIGN_REL",
    "build_phase2_shadow_campaign_ops_report",
    "campaign_path",
    "disable_sim_campaign",
    "enable_sim_observe_campaign",
    "enable_sim_shadow_campaign",
    "load_sim_campaign",
    "promote_sim_apply_campaign",
    "resolve_features_with_campaign",
    "save_sim_campaign",
    "sim_campaign_status",
]

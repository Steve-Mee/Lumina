"""Birth status fields for genesis charter, meta milestones, and autonomy metrics."""

from __future__ import annotations

from pathlib import Path
from typing import Any

_AUTONOMY_PREFIXES = ("death_spiral_", "policy_swarm_", "oos_proxy_")


def _extract_autonomy_metrics(raw: dict[str, Any] | None) -> dict[str, Any]:
    if not isinstance(raw, dict):
        return {}
    out: dict[str, Any] = {}
    for key, value in raw.items():
        key_str = str(key)
        if key_str.startswith(_AUTONOMY_PREFIXES):
            out[key_str] = value
    return out


def _twin_observability_fields(workspace_root: Path) -> dict[str, Any] | None:
    """Best-effort Twin KPIs for birth status. Never raises; fail-soft → None."""
    try:
        from lumina_core.evolution.twin_metrics_store import TwinMetricsStore
        from lumina_core.evolution.twin_mode_promotion_gate import (
            authority_for_mode,
            canonicalize_twin_mode,
        )

        # Prefer mode state under workspace when present
        mode_path = workspace_root / "state" / "approval_twin_mode.json"
        metrics_path = workspace_root / "state" / "monitoring_twin_mode_metrics.jsonl"
        summary_path = workspace_root / "state" / "twin_mode_metrics_summary.json"
        audit_path = workspace_root / "state" / "twin_mode_promotion_audit.jsonl"

        mode = "shadow"
        if mode_path.is_file():
            import json

            try:
                raw = json.loads(mode_path.read_text(encoding="utf-8"))
                if isinstance(raw, dict):
                    mode = canonicalize_twin_mode(str(raw.get("mode") or "shadow"))
            except (OSError, json.JSONDecodeError, TypeError, ValueError):
                mode = "shadow"
        else:
            mode = canonicalize_twin_mode(mode)

        store = TwinMetricsStore(
            path=metrics_path,
            summary_path=summary_path,
            audit_path=audit_path,
        )
        snap = store.snapshot()
        rolling = store.rolling_agreement(limit=200)
        calib = store.calibration_report(limit=200)
        progress = store.mode_promotion_progress(current_mode=mode, snap=snap)
        prog = progress.get("progress") if isinstance(progress, dict) else {}
        assisted = prog.get("assisted") if isinstance(prog, dict) else {}
        full_auto = prog.get("full_auto") if isinstance(prog, dict) else {}

        return {
            "mode": mode,
            "authority": authority_for_mode(mode),
            "twin_steve_agreement_pct": snap.steve_label_agreement_pct
            if snap.steve_label_samples > 0
            else snap.agreement_pct,
            "twin_agreement_pct": snap.agreement_pct,
            "rolling_agreement_w20": rolling.get("w20"),
            "rolling_agreement_w50": rolling.get("w50"),
            "risk_flags_caught": snap.risk_flags_caught,
            "risk_flags_missed": snap.risk_flags_missed,
            "risk_flags_catch_rate_pct": snap.risk_flags_catch_rate_pct,
            "high_conf_agreement_pct": calib.get("high_conf_agreement_pct"),
            "mean_abs_calibration_error": calib.get("mean_abs_calibration_error"),
            "mode_samples": snap.samples,
            "mode_promotion_progress": {
                "assisted_ready": bool(assisted.get("ready")) if isinstance(assisted, dict) else False,
                "full_auto_ready": bool(full_auto.get("ready")) if isinstance(full_auto, dict) else False,
                "assisted_fail_reasons": list(assisted.get("fail_reasons") or [])
                if isinstance(assisted, dict)
                else [],
                "full_auto_fail_reasons": list(full_auto.get("fail_reasons") or [])
                if isinstance(full_auto, dict)
                else [],
                "samples": snap.samples,
            },
            "local_only": True,
        }
    except Exception:
        return None


def maturity_status_fields(workspace_root: Path | str) -> dict[str, Any]:
    """Load maturity artifacts for birth status / API enrichment."""
    root = Path(workspace_root)
    from lumina_core.birth.checkpoint import load_checkpoint_state
    from lumina_core.birth.genesis_charter import resolve_genesis_charter
    from lumina_core.evolution.meta_milestones import load_meta_milestones

    charter = resolve_genesis_charter(root)
    milestones = [item.to_dict() for item in load_meta_milestones(root)]

    ckpt = load_checkpoint_state(root)
    autonomy_sources: list[dict[str, Any]] = []
    if isinstance(ckpt, dict):
        for key in ("stage_metrics", "autonomy_metrics"):
            block = ckpt.get(key)
            if isinstance(block, dict):
                autonomy_sources.append(block)
        autonomy_sources.append(ckpt)

    autonomy_metrics: dict[str, Any] = {}
    for source in autonomy_sources:
        autonomy_metrics.update(_extract_autonomy_metrics(source))

    progress_autonomy = _extract_autonomy_metrics(
        ckpt if isinstance(ckpt, dict) else None
    )
    autonomy_metrics.update(progress_autonomy)

    twin_obs = _twin_observability_fields(root)

    return {
        "genesis_charter": charter,
        "meta_milestones": milestones,
        "autonomy_metrics": autonomy_metrics or None,
        "twin_observability": twin_obs,
    }
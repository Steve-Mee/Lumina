"""T15: Twin mode SSOT audit — config vs persisted state vs live controller.

Fail-closed findings:
- yaml ``mode: full_auto`` is never live SSOT (seed ignored → shadow until gate promote)
- config vs state drift is reported (state wins when present)
- REAL capital + full_auto is critical
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from lumina_core.evolution.twin_mode_types import (
    _DEFAULT_MODE_STATE,
    _MODE_RANK,
    authority_for_mode,
    canonicalize_twin_mode,
)

_REAL_LIKE = frozenset({"real", "live", "prod", "production", "sim_real_guard"})


def _read_json(path: Path) -> dict[str, Any] | None:
    if not path.is_file():
        return None
    try:
        raw = json.loads(path.read_text(encoding="utf-8"))
        return raw if isinstance(raw, dict) else None
    except Exception:
        return None


def _load_yaml_twin_section(workspace: Path) -> dict[str, Any]:
    """Load evolution.approval_twin from config.yaml without requiring full ConfigLoader."""
    cfg_path = workspace / "config.yaml"
    if not cfg_path.is_file():
        # Fall back to ConfigLoader (repo root / env)
        try:
            from lumina_core.config_loader import ConfigLoader

            sec = ConfigLoader.section("evolution", "approval_twin", default={}) or {}
            return dict(sec) if isinstance(sec, dict) else {}
        except Exception:
            return {}
    try:
        import yaml

        raw = yaml.safe_load(cfg_path.read_text(encoding="utf-8")) or {}
        if not isinstance(raw, dict):
            return {}
        evo = raw.get("evolution") if isinstance(raw.get("evolution"), dict) else {}
        twin = evo.get("approval_twin") if isinstance(evo.get("approval_twin"), dict) else {}
        return dict(twin)
    except Exception:
        try:
            from lumina_core.config_loader import ConfigLoader

            sec = ConfigLoader.section("evolution", "approval_twin", default={}) or {}
            return dict(sec) if isinstance(sec, dict) else {}
        except Exception:
            return {}


def build_twin_mode_ssot_audit(
    *,
    workspace: Path | str | None = None,
    live_mode: str | None = None,
    capital_mode_hint: str | None = None,
) -> dict[str, Any]:
    """Compare config mode, state file, and optional live mode; return ops report."""
    root = Path(workspace).resolve() if workspace else Path.cwd().resolve()
    twin_cfg = _load_yaml_twin_section(root)
    promo = (
        twin_cfg.get("mode_promotion")
        if isinstance(twin_cfg.get("mode_promotion"), dict)
        else {}
    )

    mode_state_rel = str(
        promo.get("mode_state_path")
        or twin_cfg.get("mode_state_path")
        or _DEFAULT_MODE_STATE
    )
    mode_state_path = (
        Path(mode_state_rel)
        if Path(mode_state_rel).is_absolute()
        else root / mode_state_rel
    )
    audit_rel = str(promo.get("audit_path") or "state/twin_mode_promotion_audit.jsonl")
    audit_path = Path(audit_rel) if Path(audit_rel).is_absolute() else root / audit_rel

    config_raw = str(twin_cfg.get("mode") or "shadow")
    config_mode = canonicalize_twin_mode(config_raw)
    config_full_auto_seed = config_raw.strip().lower() in {
        "full_auto",
        "full-auto",
        "fullauto",
        "active",
    }

    state_payload = _read_json(mode_state_path)
    state_mode: str | None = None
    state_reason = ""
    state_updated = ""
    if state_payload is not None:
        state_mode = canonicalize_twin_mode(state_payload.get("mode"))
        state_reason = str(state_payload.get("reason") or "")
        state_updated = str(state_payload.get("updated_at") or "")

    # Live SSOT: state file wins when present; else config seed (full_auto demoted to shadow)
    if state_mode is not None:
        ssot_mode = state_mode
        ssot_source = "state_file"
    elif config_full_auto_seed:
        ssot_mode = "shadow"
        ssot_source = "config_seed_full_auto_ignored"
    else:
        ssot_mode = config_mode
        ssot_source = "config_seed"

    live_canonical = canonicalize_twin_mode(live_mode) if live_mode is not None else None

    cap = str(
        capital_mode_hint
        or promo.get("capital_mode_hint")
        or twin_cfg.get("capital_mode")
        or "sim"
    ).strip().lower()
    real_like = cap in _REAL_LIKE

    auto_promote = bool(promo.get("auto_promote_when_ready", False))
    auto_promote_fa = bool(promo.get("auto_promote_full_auto_when_ready", False))
    forbid_fa_real = bool(promo.get("forbid_full_auto_in_real_capital", True))

    findings: list[dict[str, Any]] = []

    if config_full_auto_seed:
        findings.append(
            {
                "id": "yaml_full_auto_seed",
                "severity": "warn",
                "ok": False,
                "detail": (
                    "config approval_twin.mode is full_auto/active — seed ignored; "
                    "live remains shadow until TwinModePromotionGate promote"
                ),
            }
        )
    else:
        findings.append(
            {
                "id": "yaml_full_auto_seed",
                "severity": "info",
                "ok": True,
                "detail": f"config mode seed={config_mode} (not full_auto force)",
            }
        )

    if state_payload is None:
        findings.append(
            {
                "id": "state_file",
                "severity": "info",
                "ok": True,
                "detail": f"no state file yet at {mode_state_path} — SSOT from {ssot_source}",
            }
        )
    else:
        findings.append(
            {
                "id": "state_file",
                "severity": "info",
                "ok": True,
                "detail": f"state mode={state_mode} reason={state_reason!r}",
            }
        )

    if state_mode is not None and state_mode != config_mode and not config_full_auto_seed:
        # Drift is OK when state was promoted above config seed
        higher = _MODE_RANK.get(state_mode, 0) > _MODE_RANK.get(config_mode, 0)
        findings.append(
            {
                "id": "config_state_drift",
                "severity": "info" if higher else "warn",
                "ok": higher,
                "detail": (
                    f"config={config_mode} state={state_mode} "
                    f"({'promoted above seed — OK' if higher else 'state below config seed'})"
                ),
            }
        )
    else:
        findings.append(
            {
                "id": "config_state_drift",
                "severity": "info",
                "ok": True,
                "detail": "config and state aligned or full_auto seed ignored",
            }
        )

    if live_canonical is not None:
        match = live_canonical == ssot_mode
        findings.append(
            {
                "id": "live_matches_ssot",
                "severity": "critical" if not match else "info",
                "ok": match,
                "detail": f"live={live_canonical} ssot={ssot_mode} source={ssot_source}",
            }
        )

    if real_like and ssot_mode == "full_auto":
        findings.append(
            {
                "id": "full_auto_under_real",
                "severity": "critical",
                "ok": False,
                "detail": f"ssot full_auto under capital={cap} — forbidden",
            }
        )
    else:
        findings.append(
            {
                "id": "full_auto_under_real",
                "severity": "info",
                "ok": True,
                "detail": f"capital={cap} ssot={ssot_mode} forbid_fa_real={forbid_fa_real}",
            }
        )

    if auto_promote_fa:
        findings.append(
            {
                "id": "auto_promote_full_auto",
                "severity": "warn",
                "ok": False,
                "detail": "auto_promote_full_auto_when_ready=true — prefer explicit gate promote",
            }
        )
    else:
        findings.append(
            {
                "id": "auto_promote_full_auto",
                "severity": "info",
                "ok": True,
                "detail": "auto_promote_full_auto_when_ready=false (preferred)",
            }
        )

    findings.append(
        {
            "id": "auto_promote_assisted",
            "severity": "info",
            "ok": True,
            "detail": f"auto_promote_when_ready={auto_promote}",
        }
    )

    critical_fail = any(f["severity"] == "critical" and not f["ok"] for f in findings)
    warn_fail = any(f["severity"] == "warn" and not f["ok"] for f in findings)
    # Gate ok: no critical; warns (yaml full_auto seed, auto_promote_fa) do not fail CI by default
    ok = not critical_fail

    ordered_actions: list[str] = []
    if config_full_auto_seed:
        ordered_actions.append(
            "Set evolution.approval_twin.mode to shadow (or assisted seed only) in config.yaml"
        )
    if real_like and ssot_mode == "full_auto":
        ordered_actions.append(
            "Demote twin mode under REAL capital: python scripts/validation/twin_promote_ops.py"
        )
    if live_canonical is not None and live_canonical != ssot_mode:
        ordered_actions.append(
            "Restart twin service / reconcile live controller with state/approval_twin_mode.json"
        )
    if not ordered_actions:
        ordered_actions.append(
            "SSOT healthy — promote only via gate: python scripts/validation/twin_promote_ops.py"
        )

    return {
        "schema": "twin_mode_ssot_audit_v1",
        "ok": ok,
        "workspace": str(root),
        "ssot_mode": ssot_mode,
        "ssot_source": ssot_source,
        "authority": authority_for_mode(ssot_mode),
        "config": {
            "raw": config_raw,
            "canonical": config_mode,
            "full_auto_seed_ignored": config_full_auto_seed,
        },
        "state": {
            "path": str(mode_state_path),
            "exists": mode_state_path.is_file(),
            "mode": state_mode,
            "reason": state_reason,
            "updated_at": state_updated,
        },
        "live": {
            "mode": live_canonical,
            "provided": live_mode is not None,
        },
        "capital_mode": cap,
        "real_like_capital": real_like,
        "flags": {
            "auto_promote_when_ready": auto_promote,
            "auto_promote_full_auto_when_ready": auto_promote_fa,
            "forbid_full_auto_in_real_capital": forbid_fa_real,
        },
        "audit_path": str(audit_path),
        "audit_exists": audit_path.is_file(),
        "findings": findings,
        "warn_count": sum(1 for f in findings if f["severity"] == "warn" and not f["ok"]),
        "critical_count": sum(
            1 for f in findings if f["severity"] == "critical" and not f["ok"]
        ),
        "has_warnings": warn_fail,
        "ordered_actions": ordered_actions,
        "commands": {
            "audit": "python scripts/validation/twin_mode_ssot_audit.py",
            "promote_ops": "python scripts/validation/twin_promote_ops.py --isolated",
            "deep_audit": "python scripts/validation/run_deep_audit_gates.py",
        },
    }


__all__ = ["build_twin_mode_ssot_audit"]

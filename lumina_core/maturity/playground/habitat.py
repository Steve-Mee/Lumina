"""Playground habitat telemetry — SIM only, no occupancy gift, no invented BE."""
from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from lumina_core.maturity.playground.envelope import envelope_sealed_for_pass
from lumina_core.maturity.playground.fills import first_honest_fill
from lumina_core.maturity.playground.progress import load_playground_progress

OCCUPANCY_REL = Path("state") / "lumina_playground_occupancy.json"
HEALTH_REL = Path("state") / "fabric_sim_health.json"


def read_mode(workspace_root: Path | str) -> str:
    path = Path(workspace_root) / "config.yaml"
    if not path.is_file():
        return ""
    try:
        import yaml

        raw = yaml.safe_load(path.read_text(encoding="utf-8"))
    except Exception:
        return ""
    if not isinstance(raw, dict):
        return ""
    return str(raw.get("mode") or "").strip().lower()


def habitat_error(*, mode: str, nt_down: bool = False) -> bool:
    if str(mode or "").strip().lower() == "real":
        return True
    return bool(nt_down)


def nt_down(workspace_root: Path | str) -> bool:
    path = Path(workspace_root) / HEALTH_REL
    if not path.is_file():
        return False
    try:
        raw = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return True
    if not isinstance(raw, dict):
        return True
    if raw.get("ok") is False or raw.get("healthy") is False:
        return True
    return False


def live_occupancy(workspace_root: Path | str) -> float | None:
    path = Path(workspace_root) / OCCUPANCY_REL
    if path.is_file():
        try:
            raw = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, ValueError):
            raw = None
        if isinstance(raw, dict):
            occ = _f(raw.get("occupancy"))
            if occ is not None:
                return occ
    return _f(load_playground_progress(workspace_root).get("occupancy"))


def live_breakeven_wr(workspace_root: Path | str) -> float | None:
    fill = first_honest_fill(workspace_root)
    price = _f((fill or {}).get("fill_px"))
    if price is None or price <= 0.0:
        return None
    from lumina_core.birth.birth_trade_geometry import (
        BIRTH_FALLBACK_STOP_PCT,
        BIRTH_FALLBACK_TARGET_PCT,
        economics_after_cost,
    )

    _win, _loss, _rr, be_wr, _cost = economics_after_cost(
        BIRTH_FALLBACK_STOP_PCT,
        BIRTH_FALLBACK_TARGET_PCT,
        price=float(price),
    )
    return float(be_wr)


def envelope_breached(workspace_root: Path | str) -> bool:
    return bool(load_playground_progress(workspace_root).get("envelope_breached"))


def waiting_operator(workspace_root: Path | str) -> bool:
    prog = load_playground_progress(workspace_root)
    if not envelope_sealed_for_pass(workspace_root):
        return True
    if not bool(prog.get("deck_live")):
        return True
    return False


def habitat_snapshot(workspace_root: Path | str) -> dict[str, Any]:
    mode = read_mode(workspace_root)
    down = nt_down(workspace_root)
    return {
        "mode": mode,
        "nt_down": down,
        "habitat_error": habitat_error(mode=mode, nt_down=down),
        "occupancy": live_occupancy(workspace_root),
        "breakeven_wr": live_breakeven_wr(workspace_root),
        "envelope_breached": envelope_breached(workspace_root),
        "waiting_operator": waiting_operator(workspace_root),
        "envelope_sealed": envelope_sealed_for_pass(workspace_root),
    }


def _f(value: Any) -> float | None:
    if value is None or value == "":
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        return None

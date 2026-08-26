"""Auto-computed Genesis Maturity Charter — zero manual birth configuration."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any

import yaml

from lumina_core.birth.config import load_birth_v2_config, resolve_trade_budget_cap
from lumina_core.birth.foundation_history import (
    foundation_history_max_days,
    foundation_history_start_days,
)
from lumina_core.logging_utils import get_logger

logger = get_logger("lumina.birth.genesis_charter")


@dataclass(slots=True)
class GenesisCharter:
    training_trades: int
    stage1_winrate_pass_threshold: float
    max_real_days: int
    prefer_real_data_only: bool
    rationale: dict[str, str]

    def to_dict(self) -> dict[str, Any]:
        return {
            "training_trades": int(self.training_trades),
            "stage1_winrate_pass_threshold": float(self.stage1_winrate_pass_threshold),
            "max_real_days": int(self.max_real_days),
            "prefer_real_data_only": bool(self.prefer_real_data_only),
            "rationale": dict(self.rationale),
            "auto_charter": True,
        }


def _load_raw_config(workspace_root: Path) -> dict[str, Any]:
    path = workspace_root / "config.yaml"
    if not path.is_file():
        return {}
    try:
        loaded = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
        return loaded if isinstance(loaded, dict) else {}
    except Exception as exc:
        logger.warning("genesis_charter.config_load_failed: %s", exc)
        return {}


def _resolve_hardware_profile(raw: dict[str, Any]) -> str:
    profile = str(raw.get("hardware_profile", "sweet") or "sweet").strip().lower()
    if profile in {"lite", "sweet", "beast"}:
        return profile
    return "sweet"


def compute_genesis_charter(workspace_root: Path | str) -> GenesisCharter:
    """Derive birth charter from hardware profile + birth_v2 SSOT."""
    root = Path(workspace_root)
    raw = _load_raw_config(root)
    cfg = load_birth_v2_config(root)
    cur = cfg.curriculum
    cap, cap_source = resolve_trade_budget_cap(raw)
    profile = _resolve_hardware_profile(raw)

    profile_scale = {"lite": 0.65, "sweet": 1.0, "beast": 1.35}.get(profile, 1.0)
    training_trades = max(5000, min(int(cap), int(round(cap * profile_scale))))

    winrate_threshold = float(cur.stage1_winrate_recommended or cur.stage1_winrate_pass_threshold)
    if profile == "lite":
        winrate_threshold = max(float(cur.stage1_winrate_pass_floor), winrate_threshold - 0.02)
    elif profile == "beast":
        winrate_threshold = min(0.55, winrate_threshold + 0.02)

    max_real_days = foundation_history_max_days()

    rationale = {
        "training_trades": f"trade_budget_cap={cap} ({cap_source}) × profile_scale={profile_scale}",
        "stage1_winrate_pass_threshold": f"recommended={cur.stage1_winrate_recommended} profile={profile}",
        "max_real_days": (
            f"Foundation history ceiling {max_real_days}d "
            f"(start {foundation_history_start_days()}d; not sized from trades)"
        ),
        "prefer_real_data_only": "birth_v2.prefer_real_data_only",
    }
    return GenesisCharter(
        training_trades=training_trades,
        stage1_winrate_pass_threshold=round(winrate_threshold, 4),
        max_real_days=max_real_days,
        prefer_real_data_only=bool(cfg.prefer_real_data_only),
        rationale=rationale,
    )


def load_genesis_charter(workspace_root: Path | str) -> GenesisCharter | None:
    """Read persisted charter snapshot when available."""
    path = Path(workspace_root) / "state" / "lumina_genesis_charter.json"
    if not path.is_file():
        return None
    import json

    try:
        raw = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        logger.debug("genesis_charter.load_failed: %s", exc)
        return None
    if not isinstance(raw, dict):
        return None
    try:
        return GenesisCharter(
            training_trades=max(0, int(raw.get("training_trades", 0) or 0)),
            stage1_winrate_pass_threshold=float(raw.get("stage1_winrate_pass_threshold", 0.0) or 0.0),
            max_real_days=max(0, int(raw.get("max_real_days", 0) or 0)),
            prefer_real_data_only=bool(raw.get("prefer_real_data_only", False)),
            rationale=dict(raw.get("rationale") or {}) if isinstance(raw.get("rationale"), dict) else {},
        )
    except (TypeError, ValueError) as exc:
        logger.debug("genesis_charter.load_invalid: %s", exc)
        return None


def resolve_genesis_charter(workspace_root: Path | str) -> dict[str, Any]:
    """Return persisted charter or compute a live snapshot for status payloads."""
    loaded = load_genesis_charter(workspace_root)
    if loaded is not None:
        return loaded.to_dict()
    return compute_genesis_charter(workspace_root).to_dict()


def persist_genesis_charter(workspace_root: Path | str) -> GenesisCharter:
    """Write auto charter snapshot for UI/audit."""
    root = Path(workspace_root)
    charter = compute_genesis_charter(root)
    path = root / "state" / "lumina_genesis_charter.json"
    path.parent.mkdir(parents=True, exist_ok=True)
    import json

    path.write_text(json.dumps(charter.to_dict(), ensure_ascii=True, indent=2), encoding="utf-8")
    return charter
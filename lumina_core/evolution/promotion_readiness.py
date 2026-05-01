"""Promotion readiness bundle — fail-closed checks before HTTP or runtime promotion writes.

Used by ``lumina_os`` evolution endpoints and optionally by ``SelfEvolutionMetaAgent``
so protected modes (``real``, ``paper``, ``sim_real_guard``) share one gate definition.

See ADR-0004 (reality gap) and trade reconciler status for operational alignment.
"""

from __future__ import annotations

import json
import os
from dataclasses import dataclass
from pathlib import Path
from typing import Any


def _norm_mode(mode: str | None) -> str:
    m = str(mode or "sim").strip().lower()
    return m if m else "sim"


def _protected_mode(mode: str | None) -> bool:
    return _norm_mode(mode) in {"real", "paper", "sim_real_guard"}


def is_protected_promotion_mode(mode: str | None) -> bool:
    """True when promotion bundle checks apply (``real``, ``paper``, ``sim_real_guard``)."""
    return _protected_mode(mode)


@dataclass(frozen=True, slots=True)
class PromotionReadinessResult:
    ok: bool
    reasons: tuple[str, ...]

    def message(self) -> str:
        return "; ".join(self.reasons) if self.reasons else "ok"


def _reconciler_status_path() -> Path:
    raw = os.getenv("TRADE_RECONCILER_STATUS_FILE") or os.getenv("TRADER_LEAGUE_RECONCILIATION_STATUS_FILE")
    if raw:
        return Path(raw)
    return Path("state/trade_reconciler_status.json")


def _reality_gap_history_path() -> Path:
    raw = os.getenv("LUMINA_REALITY_GAP_HISTORY_PATH")
    if raw:
        return Path(raw)
    return Path("state/reality_gap_history.jsonl")


def _shadow_runs_path() -> Path:
    raw = os.getenv("EVOLUTION_SHADOW_RUNS_PATH")
    if raw:
        return Path(raw)
    return Path("state/evolution_shadow_runs.json")


def _check_reconciler(*, status_path: Path) -> tuple[bool, str | None]:
    if not status_path.exists():
        return True, None
    try:
        data = json.loads(status_path.read_text(encoding="utf-8"))
    except Exception as exc:
        return False, f"reconciler_status_unreadable:{exc}"
    if not isinstance(data, dict):
        return False, "reconciler_status_invalid_shape"
    pending = int(data.get("pending_count", 0) or 0)
    if pending > 0:
        return False, f"reconciler_pending_orders:{pending}"
    err = data.get("last_error")
    if err is not None and str(err).strip():
        return False, f"reconciler_last_error:{err}"
    return True, None


def _check_reality_gap(*, history_path: Path) -> tuple[bool, str | None]:
    if not history_path.exists():
        return True, None
    try:
        from lumina_core.engine.backtest.reality_gap import RealityGapTracker
    except Exception as exc:
        return False, f"reality_gap_import_failed:{exc}"
    tracker = RealityGapTracker(history_path=history_path)
    n = tracker.load_history(history_path)
    if n <= 0:
        return True, None
    band = str(tracker.rolling_stats().get("band_status", "GREEN"))
    if band == "RED":
        return False, "reality_gap_band_red"
    return True, None


def _check_shadow_for_dna(*, shadow_path: Path, dna_hash: str) -> tuple[bool, str | None]:
    h = str(dna_hash or "").strip()
    if not h:
        return True, None
    if not shadow_path.exists():
        return False, "shadow_state_missing_for_dna_gate"
    try:
        runs = json.loads(shadow_path.read_text(encoding="utf-8"))
    except Exception as exc:
        return False, f"shadow_state_unreadable:{exc}"
    if not isinstance(runs, dict):
        return False, "shadow_state_invalid_shape"
    rec = runs.get(h)
    if not isinstance(rec, dict):
        return False, f"shadow_record_missing:{h[:12]}"
    status = str(rec.get("status", "")).lower()
    if status not in {"passed", "promoted"}:
        return False, f"shadow_not_passed:{status or 'unknown'}"
    return True, None


def extract_dna_hash_for_gate(challenger: dict[str, Any], proposal: dict[str, Any] | None) -> str:
    """Return DNA hash if present on challenger or proposal (optional shadow linkage)."""
    for blob in (challenger, proposal or {}):
        if not isinstance(blob, dict):
            continue
        for key in ("dna_hash", "promotion_dna_hash", "winner_dna_hash"):
            raw = blob.get(key)
            if raw is not None and str(raw).strip():
                return str(raw).strip()
    gen = proposal.get("genetic_evolution") if isinstance(proposal, dict) else None
    if isinstance(gen, dict):
        ph = gen.get("promoted_hash")
        if ph is not None and str(ph).strip():
            return str(ph).strip()
    return ""


def check_promotion_readiness(
    *,
    mode: str | None,
    challenger: dict[str, Any],
    proposal: dict[str, Any] | None = None,
    reconciler_status_path: Path | None = None,
    reality_gap_history_path: Path | None = None,
    shadow_runs_path: Path | None = None,
    require_shadow_when_dna_present: bool = True,
) -> PromotionReadinessResult:
    """Return ``ok`` if promotion writes are allowed for this mode and evidence bundle."""
    if not _protected_mode(mode):
        return PromotionReadinessResult(ok=True, reasons=())

    reasons: list[str] = []
    rpath = reconciler_status_path or _reconciler_status_path()
    ok_r, msg_r = _check_reconciler(status_path=rpath)
    if not ok_r and msg_r:
        reasons.append(msg_r)

    gpath = reality_gap_history_path or _reality_gap_history_path()
    ok_g, msg_g = _check_reality_gap(history_path=gpath)
    if not ok_g and msg_g:
        reasons.append(msg_g)

    dna_h = extract_dna_hash_for_gate(challenger, proposal)
    if dna_h and require_shadow_when_dna_present:
        spath = shadow_runs_path or _shadow_runs_path()
        ok_s, msg_s = _check_shadow_for_dna(shadow_path=spath, dna_hash=dna_h)
        if not ok_s and msg_s:
            reasons.append(msg_s)

    if reasons:
        return PromotionReadinessResult(ok=False, reasons=tuple(reasons))
    return PromotionReadinessResult(ok=True, reasons=("bundle_ok",))

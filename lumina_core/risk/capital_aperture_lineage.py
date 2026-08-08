"""Single capital aperture — order lineage contract (H1).

Fail-closed in strict capital modes: every order that reaches Final Arbitration
must carry ``decision_context_id`` (+ optional ``prev_hash``) in metadata.

Soft modes (paper/sim/birth): best-effort ensure so the typed chain is never empty
on capital-adjacent paths without inventing REAL provenance.
"""
from __future__ import annotations

import logging
import uuid
from datetime import datetime, timezone
from typing import Any

from lumina_core.risk.aperture_guard import STRICT_MODES

logger = logging.getLogger("lumina.risk.capital_aperture_lineage")

# Modes where missing lineage is FATAL (no synthetic invent).
LINEAGE_STRICT_MODES = frozenset(STRICT_MODES) | frozenset({"live", "production", "prod"})

# Soft modes may receive best-effort synthetic ctx for observability (never REAL).
LINEAGE_SOFT_MODES = frozenset(
    {"paper", "sim", "birth", "practice", "shadow", "unknown", ""}
)

# Deep-research H1 goal: ≥95% reconstructable pre-trade decisions with decision_context_id.
H1_LINEAGE_COVERAGE_TARGET_PCT = 95.0
# Intermediate ops goal (Phase Hub / Guardian soft band).
PHASE2_LINEAGE_COVERAGE_TARGET_PCT = 80.0

__all__ = [
    "H1_LINEAGE_COVERAGE_TARGET_PCT",
    "LINEAGE_SOFT_MODES",
    "LINEAGE_STRICT_MODES",
    "PHASE2_LINEAGE_COVERAGE_TARGET_PCT",
    "append_lineage_audit_record",
    "aperture_lineage_integrity_snapshot",
    "capital_aperture_residual_report",
    "ensure_order_lineage",
    "evaluate_aperture_coverage_gate",
    "extract_order_lineage",
    "is_lineage_strict_mode",
    "require_order_lineage",
]


def is_lineage_strict_mode(mode: str | None) -> bool:
    return _mode(mode) in LINEAGE_STRICT_MODES


def _mode(mode: str | None) -> str:
    return str(mode or "paper").strip().lower() or "paper"


def extract_order_lineage(order: Any) -> dict[str, str | None]:
    meta = getattr(order, "metadata", None)
    if not isinstance(meta, dict):
        meta = {}
    ctx = meta.get("decision_context_id") or getattr(order, "decision_context_id", None)
    prev = meta.get("prev_hash") or getattr(order, "prev_hash", None)
    topic = meta.get("prev_event_topic")
    return {
        "decision_context_id": str(ctx).strip() if ctx else None,
        "prev_hash": str(prev).strip() if prev else None,
        "prev_event_topic": str(topic).strip() if topic else None,
    }


def require_order_lineage(order: Any, *, mode: str | None) -> tuple[bool, str]:
    """Strict check: lineage present. Soft modes always pass check (use ensure)."""
    m = _mode(mode)
    lin = extract_order_lineage(order)
    if m in LINEAGE_STRICT_MODES:
        if not lin.get("decision_context_id"):
            return False, "missing_decision_context_id_strict_aperture"
        return True, "ok"
    return True, "ok_soft"


def ensure_order_lineage(
    order: Any,
    *,
    mode: str | None,
    allow_synthetic_soft: bool = True,
) -> tuple[bool, str]:
    """Ensure order metadata carries lineage.

    - Strict modes: require existing ctx (no invent) → fail if missing.
    - Soft modes: invent best-effort ctx if missing when allow_synthetic_soft.
    Mutates order.metadata in place when soft-ensuring.
    """
    m = _mode(mode)
    lin = extract_order_lineage(order)
    meta = getattr(order, "metadata", None)
    if not isinstance(meta, dict):
        meta = {}
        try:
            order.metadata = meta
        except Exception:
            return False, "order_metadata_not_writable"

    # Strip legacy bypass remnant so it cannot confuse future readers
    if "skip_admission_chain_recheck" in meta:
        meta.pop("skip_admission_chain_recheck", None)
        meta["legacy_bypass_flag_stripped"] = True
        logger.error(
            "capital_aperture.legacy_bypass_stripped mode=%s — skip_admission_chain_recheck removed",
            m,
        )

    if lin.get("decision_context_id"):
        # Normalize onto metadata for downstream brokers
        meta["decision_context_id"] = lin["decision_context_id"]
        if lin.get("prev_hash"):
            meta.setdefault("prev_hash", lin["prev_hash"])
        meta.setdefault("lineage_checked_at", datetime.now(timezone.utc).isoformat())
        return True, "ok_present"

    if m in LINEAGE_STRICT_MODES:
        logger.error(
            "capital_aperture.lineage_missing_strict mode=%s symbol=%s",
            m,
            getattr(order, "symbol", ""),
        )
        return False, "missing_decision_context_id_strict_aperture"

    if not allow_synthetic_soft:
        return False, "missing_decision_context_id_soft"

    # Soft invent — paper/sim/birth observability only
    ctx = f"aperture-soft-{uuid.uuid4().hex[:16]}"
    meta["decision_context_id"] = ctx
    meta.setdefault("prev_hash", "GENESIS")
    meta["lineage_source"] = "capital_aperture_soft_ensure"
    meta["lineage_checked_at"] = datetime.now(timezone.utc).isoformat()
    try:
        order.metadata = meta
    except Exception:
        pass
    logger.debug("capital_aperture.soft_lineage_ensured mode=%s ctx=%s", m, ctx)
    return True, "ok_soft_ensured"


def append_lineage_audit_record(
    workspace_root: Any | None,
    record: dict[str, Any],
) -> bool:
    """Best-effort append to state/decision_log.jsonl for coverage measurement.

    Never raises; never blocks capital path. Soft observability only.
    """
    from pathlib import Path
    import json

    try:
        root = Path(workspace_root) if workspace_root else Path.cwd()
        path = root / "state" / "decision_log.jsonl"
        path.parent.mkdir(parents=True, exist_ok=True)
        payload = dict(record or {})
        payload.setdefault("schema", "capital_aperture_decision_v1")
        payload.setdefault("timestamp", datetime.now(timezone.utc).isoformat())
        with path.open("a", encoding="utf-8") as fh:
            fh.write(json.dumps(payload, ensure_ascii=True, default=str) + "\n")
        return True
    except Exception:
        logger.debug("capital_aperture.audit_append_failed", exc_info=True)
        return False


def aperture_lineage_integrity_snapshot(
    workspace_root: Any | None = None,
    *,
    audit_limit: int = 100,
) -> dict[str, Any]:
    """Best-effort integrity snapshot for ops / Phase Hub / Guardian.

    Counts recent audit decision rows with/without decision_context_id.
    """
    from pathlib import Path

    root = Path(workspace_root) if workspace_root else Path.cwd()
    state = root / "state"
    # Prefer dedicated decision_log (H1 appends here) then broader audit trails.
    candidates = [
        state / "decision_log.jsonl",
        state / "audit_log.jsonl",
        state / "monitoring_decision_log.jsonl",
    ]
    rows: list[dict[str, Any]] = []
    source = None
    for path in candidates:
        if not path.is_file():
            continue
        source = str(path)
        try:
            lines = path.read_text(encoding="utf-8").strip().splitlines()
            for raw in lines[-max(1, audit_limit) :]:
                raw = raw.strip()
                if not raw:
                    continue
                try:
                    import json

                    obj = json.loads(raw)
                except Exception:
                    continue
                if isinstance(obj, dict):
                    rows.append(obj)
        except Exception:
            continue
        if rows:
            break

    with_ctx = 0
    without_ctx = 0
    for r in rows:
        ctx = r.get("decision_context_id") or (r.get("metadata") or {}).get(
            "decision_context_id"
        )
        if isinstance(r.get("metadata"), dict) and not ctx:
            ctx = r["metadata"].get("decision_context_id")
        if ctx:
            with_ctx += 1
        else:
            without_ctx += 1
    total = with_ctx + without_ctx
    pct = round((with_ctx / total) * 100.0, 2) if total else None

    return {
        "schema": "capital_aperture_lineage_v1",
        "strict_modes": sorted(LINEAGE_STRICT_MODES),
        "audit_source": source,
        "sample_size": total,
        "with_decision_context_id": with_ctx,
        "without_decision_context_id": without_ctx,
        "lineage_coverage_pct": pct,
        "target_coverage_pct": H1_LINEAGE_COVERAGE_TARGET_PCT,
        "phase2_target_coverage_pct": PHASE2_LINEAGE_COVERAGE_TARGET_PCT,
        "coverage_meets_phase2_goal": bool(
            pct is not None and pct >= PHASE2_LINEAGE_COVERAGE_TARGET_PCT
        ),
        "coverage_meets_h1_goal": bool(
            pct is not None and pct >= H1_LINEAGE_COVERAGE_TARGET_PCT
        ),
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "note": (
            "Strict modes reject missing lineage at admission; "
            "soft modes soft-ensure synthetic ctx for observability only. "
            f"H1 coverage goal ≥{H1_LINEAGE_COVERAGE_TARGET_PCT}%."
        ),
        "residual": capital_aperture_residual_report(),
    }


def evaluate_aperture_coverage_gate(
    snapshot: dict[str, Any] | None = None,
    *,
    workspace_root: Any | None = None,
    audit_limit: int = 200,
    min_coverage_pct: float | None = None,
    min_sample_size: int = 10,
    phase2_band: bool = False,
) -> dict[str, Any]:
    """H1/T2: pass/fail gate for lineage coverage on durable decision logs.

    - sample_size == 0 → soft_pass (no production samples yet; not a failure)
    - sample_size < min_sample_size → soft_pass (thin sample; do not claim H1 green)
    - sample_size >= min_sample_size → hard gate on coverage_pct vs target

    Never invents coverage. Never opens capital paths.
    """
    snap = snapshot or aperture_lineage_integrity_snapshot(
        workspace_root, audit_limit=audit_limit
    )
    target = float(
        min_coverage_pct
        if min_coverage_pct is not None
        else (
            PHASE2_LINEAGE_COVERAGE_TARGET_PCT
            if phase2_band
            else H1_LINEAGE_COVERAGE_TARGET_PCT
        )
    )
    sample = int(snap.get("sample_size") or 0)
    pct_raw = snap.get("lineage_coverage_pct")
    pct = float(pct_raw) if pct_raw is not None else None

    if sample <= 0:
        return {
            "schema": "aperture_coverage_gate_v1",
            "ok": True,
            "soft_pass": True,
            "hard_fail": False,
            "reason": "no_samples",
            "message": (
                "No decision_log/audit rows found — soft pass. "
                "Run SIM/REAL sessions through Final Arbitration to accumulate samples."
            ),
            "sample_size": 0,
            "lineage_coverage_pct": None,
            "target_coverage_pct": target,
            "min_sample_size": int(min_sample_size),
            "snapshot": snap,
        }

    if sample < int(min_sample_size):
        return {
            "schema": "aperture_coverage_gate_v1",
            "ok": True,
            "soft_pass": True,
            "hard_fail": False,
            "reason": "thin_sample",
            "message": (
                f"sample_size={sample} < min_sample_size={min_sample_size} — soft pass. "
                f"Coverage observed={pct}% (not H1-certified until N≥{min_sample_size})."
            ),
            "sample_size": sample,
            "lineage_coverage_pct": pct,
            "target_coverage_pct": target,
            "min_sample_size": int(min_sample_size),
            "snapshot": snap,
        }

    meets = pct is not None and pct >= target
    return {
        "schema": "aperture_coverage_gate_v1",
        "ok": bool(meets),
        "soft_pass": False,
        "hard_fail": not bool(meets),
        "reason": "coverage_ok" if meets else "coverage_below_target",
        "message": (
            f"coverage={pct}% target={target}% sample_size={sample} — "
            + ("H1 goal met." if meets else "below target; improve admission lineage emit.")
        ),
        "sample_size": sample,
        "lineage_coverage_pct": pct,
        "target_coverage_pct": target,
        "min_sample_size": int(min_sample_size),
        "coverage_meets_h1_goal": bool(snap.get("coverage_meets_h1_goal")),
        "coverage_meets_phase2_goal": bool(snap.get("coverage_meets_phase2_goal")),
        "snapshot": snap,
    }


def capital_aperture_residual_report() -> dict[str, Any]:
    """Track E residual SSOT: what is closed vs deferred for H1 capital aperture.

    Does not claim production ≥95% without samples — that is runtime-measured.
    """
    return {
        "schema": "capital_aperture_residual_v1",
        "single_non_bypassable_aperture": True,
        "authoritative_path": "broker.submit_order → run_final_arbitration → ensure_order_lineage → enforce_pre_trade_gate",
        "closed": [
            {
                "id": "strict_lineage_required",
                "status": "done",
                "note": "REAL/live/prod/sim_real_guard reject missing decision_context_id",
            },
            {
                "id": "soft_lineage_ensure",
                "status": "done",
                "note": "paper/sim/birth get synthetic ctx for observability only",
            },
            {
                "id": "legacy_skip_admission_strip",
                "status": "done",
                "note": "skip_admission_chain_recheck stripped + logged; never short-circuits",
            },
            {
                "id": "durable_decision_log",
                "status": "done",
                "note": "state/decision_log.jsonl on admit and reject",
            },
            {
                "id": "aperture_guard_tripwire",
                "status": "done",
                "note": "enforce_no_bypass_in_strict_mode fatal on reintroduced bypass",
            },
            {
                "id": "nt_paper_crosstrade_fa",
                "status": "done",
                "note": "NinjaTrader/Paper/CrossTrade brokers call run_final_arbitration before submit",
            },
        ],
        "residual": [
            {
                "id": "full_capital_path_bus_rewire",
                "status": "partial_t10",
                "note": (
                    "Core spine typed: admission.gate_entry, risk.final_arbitration.result, "
                    "risk.admission.lineage_checked. Inventory: capital_bus_lineage.py; "
                    "scripts/validation/capital_bus_lineage_gate.py. Residual rewire continuous."
                ),
            },
            {
                "id": "h1_95pct_live_production",
                "status": "runtime_measured",
                "note": (
                    f"Goal ≥{H1_LINEAGE_COVERAGE_TARGET_PCT}% via "
                    "scripts/validation/aperture_coverage_gate.py "
                    "(soft pass if sample_size=0 or thin; hard fail only when N≥min and below target)."
                ),
            },
            {
                "id": "execution_fabric_safety_plane",
                "status": "brain_failclosed_partial",
                "note": (
                    "Brain: disconnect→SAFE (places blocked); place_order_sync rejects SAFE/FULL_SAFE; "
                    "lineage required in strict mode. Host C# cancel/flatten grace still operator-validated E2E."
                ),
            },
        ],
        "policy": {
            "twin_cannot_bypass_aperture": True,
            "synthetic_lineage_never_real": True,
            "coverage_goal_pct": H1_LINEAGE_COVERAGE_TARGET_PCT,
        },
    }

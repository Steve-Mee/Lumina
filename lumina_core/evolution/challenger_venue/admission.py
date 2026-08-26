"""Sim-mode Admission Chain for challenger paper intents — no skip flags (constitution #7)."""

from __future__ import annotations

from typing import Any

from lumina_core.risk.admission_chain import (
    CANONICAL_ADMISSION_STEPS,
    AdmissionChain,
    AdmissionContext,
)

_SKIP_KEYS = frozenset(
    {
        "skip_admission_chain_recheck",
        "skip_admission",
        "bypass_admission",
        "experimental_bypass",
    }
)


def _pass(_ctx: AdmissionContext) -> tuple[bool, str]:
    return True, "ok"


def admit_challenger_intent(intent: dict[str, Any], *, engine: Any = None) -> dict[str, Any]:
    """Fail-closed paper admit. Mode is always sim; bypass is always forbidden."""
    raw = dict(intent or {})
    meta = raw.get("metadata") if isinstance(raw.get("metadata"), dict) else {}
    for key in _SKIP_KEYS:
        if bool(raw.get(key)) or bool(meta.get(key)):
            return {"admitted": False, "reason": f"skip_flag_forbidden:{key}", "bypassed": False}
    if bool(raw.get("disable_risk_controller")):
        return {"admitted": False, "reason": "disable_risk_controller_forbidden", "bypassed": False}

    side = str(raw.get("side") or "").strip().upper()
    qty = float(raw.get("qty") or raw.get("quantity") or 0.0)
    symbol = str(raw.get("symbol") or raw.get("instrument") or "").strip()
    if side not in {"BUY", "SELL", "LONG", "SHORT"} or qty <= 0.0 or not symbol:
        return {"admitted": False, "reason": "malformed_intent", "bypassed": False}

    meta_dict: dict[str, Any] = dict(meta) if isinstance(meta, dict) else {}
    handlers = {step: _pass for step in CANONICAL_ADMISSION_STEPS}
    ctx = AdmissionContext(
        engine=engine if engine is not None else object(),
        mode="sim",
        symbol=symbol,
        regime=str(raw.get("regime") or "NEUTRAL"),
        proposed_risk=float(raw.get("proposed_risk") or 0.0),
        order_side=side,
        metadata=meta_dict,
        step_handlers=handlers,
        experimental_bypass_step_ids=frozenset[str](),
        forbid_bypass=True,
    )
    ok, reason, trace = AdmissionChain(steps=CANONICAL_ADMISSION_STEPS).run(ctx)
    return {
        "admitted": bool(ok),
        "reason": str(reason),
        "bypassed": any(item.bypassed for item in trace.results),
    }

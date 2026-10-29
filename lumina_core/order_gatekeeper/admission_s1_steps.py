"""S1 admission handlers: SIM whitelist and LIVE_RELEASE (Risk Core)."""

from __future__ import annotations

from collections.abc import Callable
from typing import Any

from lumina_core.risk.admission_chain import AdmissionContext
from lumina_core.risk.live_release import (
    LIVE_ACCOUNT_PATH_CLOSED_S1,
    admit_live_orders,
    live_release_from_engine,
)
from lumina_core.risk.sim_account_guard import (
    admit_sim_account,
    connected_account_from_engine,
    modes_requiring_whitelist,
    whitelist_from_engine,
)

AdmissionHandler = Callable[[AdmissionContext], tuple[bool, str]]


def _agent_id(ctx: AdmissionContext) -> str:
    return str(ctx.metadata.get("agent_id", ""))


def make_sim_account_whitelist_step(ctx: Any) -> AdmissionHandler:
    engine = ctx.engine

    def _step(admission_ctx: AdmissionContext) -> tuple[bool, str]:
        mode = admission_ctx.normalized_mode()
        if mode == "paper":
            return True, "not_required_paper"
        if mode == "real":
            return True, "sim_whitelist_not_applicable_real"
        if mode not in modes_requiring_whitelist():
            reason = f"nt_bridge_not_allowed_in_mode:{mode}"
            admission_ctx.metadata["deny_reason_code"] = reason
            return False, reason
        account = str(admission_ctx.metadata.get("connected_account") or "") or connected_account_from_engine(
            engine
        )
        requested = admission_ctx.metadata.get("sim_account_whitelist")
        if requested is None:
            requested = whitelist_from_engine(engine)
        ok, reason = admit_sim_account(
            account,
            requested if isinstance(requested, (list, tuple, frozenset, set)) else None,
            mode=mode,
            agent_id=_agent_id(admission_ctx),
        )
        if ok is not True:
            admission_ctx.metadata["deny_reason_code"] = reason
            return False, reason
        return True, reason

    return _step


def make_live_release_step(ctx: Any) -> AdmissionHandler:
    engine = ctx.engine

    def _step(admission_ctx: AdmissionContext) -> tuple[bool, str]:
        mode = admission_ctx.normalized_mode()
        if mode != "real":
            return True, "live_release_not_required"
        record = admission_ctx.metadata.get("live_release")
        if record is None:
            record = live_release_from_engine(engine)
        ok, reason = admit_live_orders(record, agent_id=_agent_id(admission_ctx))
        if ok is True:
            reason = LIVE_ACCOUNT_PATH_CLOSED_S1
            ok = False
        admission_ctx.metadata["deny_reason_code"] = reason
        return False, reason

    return _step


def attach_s1_admission_metadata(engine: Any, metadata: dict[str, Any]) -> None:
    """Stamp account + whitelist + live_release onto the admission context."""
    metadata.setdefault("connected_account", connected_account_from_engine(engine))
    metadata.setdefault("sim_account_whitelist", whitelist_from_engine(engine))
    payload = live_release_from_engine(engine)
    if payload is not None:
        metadata.setdefault("live_release", payload)

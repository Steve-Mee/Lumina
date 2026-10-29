"""S3/S4 entry criteria 1–9. Missing evidence is ``research_sim_gated``. Yaml cannot lift D1."""

from __future__ import annotations

import hmac
import os
from collections.abc import Mapping
from contextlib import contextmanager
from contextvars import ContextVar
from dataclasses import dataclass
from typing import Iterator

from lumina_core.broker.ninjatrader.account_names import (
    account_on_sim_whitelist,
    canonicalize_account_name,
    is_paper_account_name,
)
from lumina_core.research_bridge.continuity_meter import (
    FAR_MAX,
    POWER_MIN,
    PRODUCED_BY,
    TTD_FAST_MAX_DAYS,
    TTD_SLOW_MAX_DAYS,
    ContinuityMeterReport,
)
from lumina_core.research_bridge.independence import independent_set
from lumina_core.risk.live_release import (
    PURPOSE_LIVE,
    SECRET_ENV,
    compute_live_release_mac,
)

RESEARCH_BRIDGE_SOURCE = "research_bridge"
RESEARCH_SIM_GATED = "research_sim_gated"
SIM_INSTRUMENT_NOT_YET_RELEASED = "sim_instrument_not_yet_released"
S3_INSTRUMENTS: frozenset[str] = frozenset({"MES", "MNQ"})
ADR0058_WINDOW_BARS = 20
MIN_SURVIVORS = 2
MAX_SURVIVORS = 3
SUPERVISOR_MARKERS: tuple[str, ...] = (
    "supervisor_tick_exec",
    "run_tick_exec",
    "confluence",
)

_BOUND: "SimGateContext | None" = None
_PLACE_ARMED: ContextVar[bool] = ContextVar("lumina_s3_research_place", default=False)
_NON_RESEARCH_RELEASE: "LoggedHumanRelease | None" = None


class SimGateRefused(ValueError):
    """S3 SIM entry failed closed."""


@dataclass(frozen=True, slots=True)
class SurvivorRecord:
    hypothesis_id: str
    config_id: str
    family: str
    instrument: str
    stage: str
    tape_kind: str
    passed_validation_gate: bool
    expected_horizon_bars: int
    fill_history_bars: int
    returns: tuple[float, ...]
    validation_mac: str
    report_sha256: str
    promotion_gate_promoted: bool


@dataclass(frozen=True, slots=True)
class LoggedHumanRelease:
    adr_path: str
    approved_by: str
    purpose: str


@dataclass(frozen=True, slots=True)
class SimGateContext:
    research_execution_mode_boot: str
    trade_mode: str
    sim_real_guard_env: bool
    connected_account: str
    whitelist: tuple[str, ...]
    live_release_record: Mapping[str, object] | None
    instrument: str
    survivors: tuple[SurvivorRecord, ...]
    continuity_meter: ContinuityMeterReport | None
    promotion_hmac_ok: bool
    approval_required: bool
    approval_present: bool
    market_connected: bool
    equity_snapshot_stale: bool
    reduce_only: bool = False
    yaml_mode_now: str = ""
    max_survivors: int = MAX_SURVIVORS


def bind_sim_gate(ctx: SimGateContext | None) -> SimGateContext | None:
    """Process-local evidence. Hot-reloaded yaml is not this object."""
    global _BOUND
    previous = _BOUND
    _BOUND = ctx
    return previous


def bound_context() -> SimGateContext | None:
    return _BOUND


def bind_logged_human_release(release: LoggedHumanRelease | None) -> LoggedHumanRelease | None:
    global _NON_RESEARCH_RELEASE
    previous = _NON_RESEARCH_RELEASE
    _NON_RESEARCH_RELEASE = release
    return previous


def logged_human_release() -> LoggedHumanRelease | None:
    return _NON_RESEARCH_RELEASE


def supervisor_source_blocked(source: str) -> bool:
    token = str(source or "").strip().lower()
    if not token:
        return False
    return any(marker in token for marker in SUPERVISOR_MARKERS)


def research_place_is_armed() -> bool:
    return _PLACE_ARMED.get() is True


@contextmanager
def arm_research_place(ctx: SimGateContext | None = None) -> Iterator[None]:
    ok, reason = evaluate(ctx)
    if ok is not True:
        raise SimGateRefused(reason)
    token = _PLACE_ARMED.set(True)
    try:
        yield
    finally:
        _PLACE_ARMED.reset(token)


def evaluate(ctx: SimGateContext | None = None) -> tuple[bool, str]:
    """All nine criteria. First failure wins. Missing bound context → gated."""
    evidence = ctx if ctx is not None else _BOUND
    if evidence is None:
        return False, RESEARCH_SIM_GATED
    checks = (
        _criterion_mode,
        _criterion_live_release,
        _criterion_whitelist,
        _criterion_trade_mode,
        _criterion_instrument,
        _criterion_survivors,
        _criterion_continuity,
        _criterion_promotion,
        _criterion_approval,
    )
    for check in checks:
        ok, reason = check(evidence)
        if ok is not True:
            return False, reason
    if evidence.market_connected is not True:
        return False, RESEARCH_SIM_GATED
    if evidence.equity_snapshot_stale is True and evidence.reduce_only is not True:
        return False, "equity_snapshot_stale"
    return True, "research_sim_gate_ok"


def evaluate_instrument(instrument: str, ctx: SimGateContext | None = None) -> tuple[bool, str]:
    root = str(instrument or "").strip().upper().split()[0] if str(instrument or "").strip() else ""
    if root not in S3_INSTRUMENTS:
        return False, SIM_INSTRUMENT_NOT_YET_RELEASED
    return evaluate(ctx)


def _criterion_mode(ctx: SimGateContext) -> tuple[bool, str]:
    boot = str(ctx.research_execution_mode_boot or "").strip().lower()
    if boot != "sim":
        return False, RESEARCH_SIM_GATED
    return True, "ok"


def _criterion_live_release(ctx: SimGateContext) -> tuple[bool, str]:
    if _live_release_is_real(ctx.live_release_record) is True:
        return False, RESEARCH_SIM_GATED
    return True, "ok"


def _criterion_whitelist(ctx: SimGateContext) -> tuple[bool, str]:
    account = canonicalize_account_name(ctx.connected_account)
    if not account:
        return False, "ninjatrader_account_unknown"
    if not is_paper_account_name(account):
        return False, "sim_account_not_whitelisted"
    if not account_on_sim_whitelist(account, ctx.whitelist):
        return False, "sim_account_not_whitelisted"
    return True, "ok"


def _criterion_trade_mode(ctx: SimGateContext) -> tuple[bool, str]:
    mode = str(ctx.trade_mode or "").strip().lower()
    if mode == "real":
        return False, RESEARCH_SIM_GATED
    if mode == "sim":
        return False, RESEARCH_SIM_GATED
    if mode != "sim_real_guard":
        return False, RESEARCH_SIM_GATED
    if ctx.sim_real_guard_env is not True:
        return False, "sim_real_guard_disabled"
    return True, "ok"


def _criterion_instrument(ctx: SimGateContext) -> tuple[bool, str]:
    root = str(ctx.instrument or "").strip().upper().split()[0] if str(ctx.instrument or "").strip() else ""
    if root not in S3_INSTRUMENTS:
        return False, SIM_INSTRUMENT_NOT_YET_RELEASED
    return True, "ok"


def _criterion_survivors(ctx: SimGateContext) -> tuple[bool, str]:
    eligible: list[SurvivorRecord] = []
    for row in ctx.survivors:
        ok, reason = _survivor_eligible(row)
        if ok is not True:
            continue
        eligible.append(row)
    if len(eligible) < MIN_SURVIVORS:
        return False, "survivors_insufficient"
    chosen, reason = independent_set(eligible)
    if len(chosen) < MIN_SURVIVORS:
        return False, reason if reason != "independent" else "survivors_not_independent"
    cap = int(ctx.max_survivors) if int(ctx.max_survivors) >= MIN_SURVIVORS else MAX_SURVIVORS
    if len(chosen) > cap:
        return False, "survivors_over_capacity"
    return True, "ok"


def _survivor_eligible(row: SurvivorRecord) -> tuple[bool, str]:
    if str(row.stage) not in {"active", "deweighted"}:
        return False, "survivors_stage"
    if row.passed_validation_gate is not True:
        return False, "survivors_gate_failed"
    if str(row.tape_kind) != "nt_pit":
        return False, "survivors_not_nt_pit"
    if isinstance(row.expected_horizon_bars, bool) or not isinstance(row.expected_horizon_bars, int):
        return False, "expected_horizon_missing"
    if row.expected_horizon_bars < 1:
        return False, "expected_horizon_missing"
    if isinstance(row.fill_history_bars, bool) or not isinstance(row.fill_history_bars, int):
        return False, "survivors_fill_history"
    if row.fill_history_bars < row.expected_horizon_bars:
        return False, "survivors_fill_history"
    if row.fill_history_bars < ADR0058_WINDOW_BARS:
        return False, "survivors_fill_history"
    if str(row.instrument).strip().upper() not in S3_INSTRUMENTS:
        return False, SIM_INSTRUMENT_NOT_YET_RELEASED
    if len(str(row.validation_mac)) != 64 or len(str(row.report_sha256)) != 64:
        return False, "survivors_mac_missing"
    return True, "ok"


def _criterion_continuity(ctx: SimGateContext) -> tuple[bool, str]:
    """Research team decision (relayed by Steve 2026-10-29): meter only, no caller float."""
    report = ctx.continuity_meter
    if report is None or type(report) is not ContinuityMeterReport:
        return False, "continuity_unmeasured"
    if str(report.produced_by) != PRODUCED_BY:
        return False, "continuity_unmeasured"
    if str(report.tape_kind) != "nt_pit":
        return False, "continuity_not_nt_pit"
    digest = str(report.bar_sha256)
    if len(digest) != 64:
        return False, "continuity_unbound"
    far = float(report.far)
    if far != far or far < 0.0:
        return False, "far_unmeasured"
    if far > FAR_MAX:
        return False, "far_above_floor"
    ttd_fast = float(report.ttd_fast_days)
    if ttd_fast != ttd_fast or ttd_fast <= 0.0 or ttd_fast > TTD_FAST_MAX_DAYS:
        return False, "ttd_fast_above_floor"
    ttd_slow = float(report.ttd_slow_days)
    if ttd_slow != ttd_slow or ttd_slow <= 0.0 or ttd_slow > TTD_SLOW_MAX_DAYS:
        return False, "ttd_slow_above_floor"
    power = float(report.power)
    if power != power or power < POWER_MIN:
        return False, "power_below_floor"
    if report.passed is not True or str(report.reason) != "ok":
        return False, str(report.reason or "continuity_failed")
    return True, "ok"


def _criterion_promotion(ctx: SimGateContext) -> tuple[bool, str]:
    if ctx.promotion_hmac_ok is not True:
        return False, "promotion_mac_required"
    if not ctx.survivors:
        return False, "survivors_insufficient"
    if any(item.promotion_gate_promoted is not True for item in ctx.survivors if _survivor_eligible(item)[0]):
        return False, "promotion_gate_rejected"
    return True, "ok"


def _criterion_approval(ctx: SimGateContext) -> tuple[bool, str]:
    if ctx.approval_required is not True:
        return False, RESEARCH_SIM_GATED
    if ctx.approval_present is not True:
        return False, RESEARCH_SIM_GATED
    return True, "ok"


def _live_release_is_real(record: Mapping[str, object] | None) -> bool:
    """True only when enabled HMAC would verify as a REAL release. Does not consume nonce."""
    if record is None or not isinstance(record, Mapping):
        return False
    enabled = record.get("enabled")
    if enabled is not True:
        return False
    secret_raw = os.environ.get(SECRET_ENV)
    if secret_raw is None or len(str(secret_raw).strip()) < 16:
        return False
    mac = str(record.get("mac") or "").strip().lower()
    if len(mac) != 64:
        return False
    purpose = str(record.get("purpose") or "").strip()
    if purpose != PURPOSE_LIVE:
        return False
    expected = compute_live_release_mac(record, str(secret_raw).strip().encode("utf-8"))
    return hmac.compare_digest(expected, mac)


def non_research_release_allows(source: str) -> bool:
    """ADR + human logged release. Never supervisor. Still requires AdmissionChain."""
    if supervisor_source_blocked(source):
        return False
    release = _NON_RESEARCH_RELEASE
    if release is None:
        return False
    approver = str(release.approved_by or "").strip()
    folded = approver.casefold()
    if len(approver) < 2:
        return False
    if any(marker in folded for marker in ("agent", "research", "twin", "swarm", "birth")):
        return False
    path = str(release.adr_path or "").strip()
    if not path.startswith("docs/adr/") or not path.endswith(".md"):
        return False
    if str(release.purpose or "").strip().lower() not in {"non_research_place", "manual_place"}:
        return False
    return True

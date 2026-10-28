"""Independent research Risk Core. propose_order → Approved | Rejected | Scaled.

Does not import evolution, agents, validation, or lumina_core. Config is snapshotted
into a closure so object.__setattr__ on the instance or the config object cannot
weaken limits. Kill switch is sticky. Agent id cannot buy a bypass.
"""

from __future__ import annotations

import hashlib
import hmac
import math
import os
from datetime import datetime, timezone
from typing import Callable, NamedTuple

from lumina_research.risk_core.config import RiskConfig, load_default_config
from lumina_research.risk_core.seal import install_module_seal
from lumina_research.risk_core.types import INSTRUMENT_CLUSTERS, Decision, OrderProposal, cluster_for

_SEALED = ("propose_order", "RiskCore", "load_default_config", "_DISPATCH")


class _Limits(NamedTuple):
    max_position_pct: float
    max_daily_loss_pct: float
    max_total_drawdown_pct: float
    leverage_cap: float
    correlation_cluster_limit_pct: float
    heartbeat_timeout_sec: float
    min_quantity: float


class _Book:
    __slots__ = (
        "equity",
        "peak_equity",
        "gross_notional",
        "cluster_notional",
        "daily_pnl",
        "drawdown_pct",
        "last_heartbeat",
        "kill",
        "kill_reason",
    )

    def __init__(self, equity: float) -> None:
        if not math.isfinite(equity) or equity <= 0.0:
            raise ValueError("equity must be a finite positive number")
        self.equity = float(equity)
        self.peak_equity = float(equity)
        self.gross_notional = 0.0
        self.cluster_notional: dict[str, float] = {}
        self.daily_pnl = 0.0
        self.drawdown_pct = 0.0
        self.last_heartbeat: datetime | None = None
        self.kill = False
        self.kill_reason = ""

    def __setattr__(self, name: str, value: object) -> None:
        if name == "kill" and getattr(self, "kill", False) is True and value is False:
            raise AttributeError("kill switch cannot be cleared")
        object.__setattr__(self, name, value)


class _Bound:
    __slots__ = ("propose", "heartbeat", "record_pnl", "set_exposure", "config")

    def __init__(
        self,
        *,
        propose: Callable[[OrderProposal], Decision],
        heartbeat: Callable[[datetime], None],
        record_pnl: Callable[[float], None],
        set_exposure: Callable[..., None],
        config: RiskConfig,
    ) -> None:
        self.propose = propose
        self.heartbeat = heartbeat
        self.record_pnl = record_pnl
        self.set_exposure = set_exposure
        self.config = config


_DISPATCH: dict[int, _Bound] = {}


class RiskCore:
    """Config-driven hard rules. Subclassing is forbidden. State lives in a closure."""

    __slots__ = ("__weakref__",)

    def __init_subclass__(cls) -> None:
        raise TypeError("RiskCore cannot be subclassed")

    def __init__(self, config: object, *, equity: float) -> None:
        if not isinstance(config, RiskConfig):
            raise TypeError("config must be a frozen RiskConfig")
        bound = _bind(config, equity)
        _DISPATCH[id(self)] = bound

    def __setattr__(self, name: str, value: object) -> None:
        raise AttributeError("RiskCore attributes are frozen")

    @property
    def config(self) -> RiskConfig:
        return _bound(self).config

    def heartbeat(self, at: datetime) -> None:
        _bound(self).heartbeat(at)

    def record_pnl(self, pnl: float) -> None:
        _bound(self).record_pnl(pnl)

    def set_exposure(self, *, gross_notional: float, cluster_id: str, cluster_notional: float) -> None:
        _bound(self).set_exposure(
            gross_notional=gross_notional,
            cluster_id=cluster_id,
            cluster_notional=cluster_notional,
        )

    def propose_order(self, proposal: OrderProposal) -> Decision:
        bound = _DISPATCH.get(id(self))
        if bound is None:
            return Decision.rejected(proposal, "kill_switch:tamper")
        return bound.propose(proposal)


def propose_order(proposal: OrderProposal, *, core: RiskCore | None = None) -> Decision:
    engine = core if core is not None else _default_core()
    return engine.propose_order(proposal)


def _default_core() -> RiskCore:
    return RiskCore(load_default_config(), equity=100_000.0)


def _bound(core: RiskCore) -> _Bound:
    bound = _DISPATCH.get(id(core))
    if bound is None:
        raise RuntimeError("RiskCore binding missing")
    return bound


def _bind(config: RiskConfig, equity: float) -> _Bound:
    limits = _Limits(
        max_position_pct=float(config.max_position_pct),
        max_daily_loss_pct=float(config.max_daily_loss_pct),
        max_total_drawdown_pct=float(config.max_total_drawdown_pct),
        leverage_cap=float(config.leverage_cap),
        correlation_cluster_limit_pct=float(config.correlation_cluster_limit_pct),
        heartbeat_timeout_sec=float(config.heartbeat_timeout_sec),
        min_quantity=float(config.min_quantity),
    )
    book = _Book(equity)
    key = os.urandom(32)

    def payload() -> bytes:
        heartbeat = None if book.last_heartbeat is None else book.last_heartbeat.isoformat()
        clusters = tuple(sorted((str(name), float(value)) for name, value in book.cluster_notional.items()))
        return repr(
            (
                limits,
                float(book.equity),
                float(book.peak_equity),
                float(book.gross_notional),
                clusters,
                float(book.daily_pnl),
                float(book.drawdown_pct),
                heartbeat,
                bool(book.kill),
                str(book.kill_reason),
            )
        ).encode("utf-8")

    def mac() -> bytes:
        return hmac.new(key, payload(), hashlib.sha256).digest()

    cell = [mac()]

    def verify() -> bool:
        try:
            return hmac.compare_digest(cell[0], mac())
        except Exception:
            return False

    def touch() -> None:
        cell[0] = mac()

    def heartbeat(at: datetime) -> None:
        if not verify():
            _engage(book, "tamper")
            touch()
            raise RuntimeError("RiskCore state tamper")
        if at.tzinfo is None:
            raise ValueError("heartbeat timestamp must be timezone-aware UTC")
        book.last_heartbeat = at.astimezone(timezone.utc)
        touch()

    def record_pnl(pnl: float) -> None:
        if not verify():
            _engage(book, "tamper")
            touch()
            raise RuntimeError("RiskCore state tamper")
        if not math.isfinite(pnl):
            _engage(book, "non_finite_pnl")
            touch()
            raise ValueError("pnl must be finite")
        book.daily_pnl += float(pnl)
        book.equity += float(pnl)
        if book.equity > book.peak_equity:
            book.peak_equity = book.equity
        if book.peak_equity > 0.0:
            book.drawdown_pct = max(0.0, (book.peak_equity - book.equity) / book.peak_equity)
        _trip_kill_from_state(limits, book)
        touch()

    def set_exposure(*, gross_notional: float, cluster_id: str, cluster_notional: float) -> None:
        if not verify():
            _engage(book, "tamper")
            touch()
            raise RuntimeError("RiskCore state tamper")
        if not math.isfinite(gross_notional) or not math.isfinite(cluster_notional):
            raise ValueError("notionals must be finite")
        if gross_notional < 0.0 or cluster_notional < 0.0:
            raise ValueError("notionals must be >= 0")
        if cluster_id not in set(INSTRUMENT_CLUSTERS.values()):
            raise ValueError("unknown correlation cluster")
        book.gross_notional = float(gross_notional)
        book.cluster_notional[cluster_id] = float(cluster_notional)
        touch()

    def propose(proposal: OrderProposal) -> Decision:
        if not verify():
            _engage(book, "tamper")
            touch()
            return Decision.rejected(proposal, "kill_switch:tamper")
        decision = _decide(limits, book, proposal)
        touch()
        return decision

    return _Bound(
        propose=propose,
        heartbeat=heartbeat,
        record_pnl=record_pnl,
        set_exposure=set_exposure,
        config=config,
    )


def _engage(book: _Book, reason: str) -> None:
    book.kill = True
    if not book.kill_reason:
        book.kill_reason = reason


def _trip_kill_from_state(limits: _Limits, book: _Book) -> None:
    if book.equity <= 0.0:
        _engage(book, "equity_exhausted")
    if book.drawdown_pct >= limits.max_total_drawdown_pct:
        _engage(book, "drawdown_breach")
    if book.daily_pnl <= -limits.max_daily_loss_pct * max(book.peak_equity, book.equity, 1e-12):
        _engage(book, "max_daily_loss")


def _finite_proposal(proposal: OrderProposal) -> str | None:
    if not math.isfinite(proposal.quantity) or proposal.quantity <= 0.0:
        return "invalid_quantity"
    if not math.isfinite(proposal.price) or proposal.price <= 0.0:
        return "invalid_price"
    if not math.isfinite(proposal.notional) or proposal.notional <= 0.0:
        return "invalid_notional"
    try:
        expected = cluster_for(proposal.instrument)
    except ValueError:
        return "unknown_instrument"
    if proposal.cluster_id != expected:
        return "cluster_mismatch"
    return None


def _decide(limits: _Limits, book: _Book, proposal: OrderProposal) -> Decision:
    invalid = _finite_proposal(proposal)
    if invalid is not None:
        return Decision.rejected(proposal, invalid)

    now = proposal.submitted_at_utc
    if now.tzinfo is None:
        return Decision.rejected(proposal, "timestamp_not_utc")
    now_utc = now.astimezone(timezone.utc)

    if book.last_heartbeat is None:
        _engage(book, "heartbeat_missing")
        return Decision.rejected(proposal, "kill_switch:heartbeat_missing")
    age = (now_utc - book.last_heartbeat).total_seconds()
    if age < 0.0:
        return Decision.rejected(proposal, "timestamp_before_heartbeat")
    if age > limits.heartbeat_timeout_sec:
        _engage(book, "heartbeat_loss")
        return Decision.rejected(proposal, "kill_switch:heartbeat_loss")

    if book.kill:
        return Decision.rejected(proposal, f"kill_switch:{book.kill_reason or 'engaged'}")

    if book.drawdown_pct >= limits.max_total_drawdown_pct:
        _engage(book, "drawdown_breach")
        return Decision.rejected(proposal, "kill_switch:drawdown_breach")

    daily_cap = limits.max_daily_loss_pct * max(book.peak_equity, 1e-12)
    if book.daily_pnl <= -daily_cap:
        _engage(book, "max_daily_loss")
        return Decision.rejected(proposal, "kill_switch:max_daily_loss")

    if book.equity <= 0.0:
        _engage(book, "equity_exhausted")
        return Decision.rejected(proposal, "kill_switch:equity_exhausted")

    qty = proposal.quantity
    notional = proposal.notional
    reasons: list[str] = []
    cluster_id = cluster_for(proposal.instrument)

    max_position_notional = limits.max_position_pct * book.equity
    if notional > max_position_notional:
        scale = max_position_notional / notional
        qty *= scale
        notional = max_position_notional
        reasons.append("max_position_pct")

    max_gross = limits.leverage_cap * book.equity
    projected_gross = book.gross_notional + notional
    if projected_gross > max_gross:
        allowed = max(0.0, max_gross - book.gross_notional)
        if allowed <= 0.0:
            return Decision.rejected(proposal, "leverage_cap")
        scale = allowed / notional
        qty *= scale
        notional = allowed
        reasons.append("leverage_cap")

    cluster_now = book.cluster_notional.get(cluster_id, 0.0)
    max_cluster = limits.correlation_cluster_limit_pct * book.equity
    projected_cluster = cluster_now + notional
    if projected_cluster > max_cluster:
        allowed = max(0.0, max_cluster - cluster_now)
        if allowed <= 0.0:
            return Decision.rejected(proposal, "correlation_cluster_limit")
        scale = allowed / notional
        qty *= scale
        notional = allowed
        reasons.append("correlation_cluster_limit")

    if qty + 1e-12 < limits.min_quantity or notional <= 0.0:
        reason = reasons[0] if reasons else "below_min_quantity"
        return Decision.rejected(proposal, reason)

    if reasons:
        return Decision.scaled(
            proposal,
            quantity=qty,
            notional=notional,
            reason="+".join(reasons),
        )
    return Decision.approved(proposal)


install_module_seal(__name__, _SEALED)

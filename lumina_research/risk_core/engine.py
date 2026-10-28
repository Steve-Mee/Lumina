"""Independent research Risk Core. propose_order → Approved | Rejected | Scaled.

Does not import evolution, agents, validation, or lumina_core. Config is frozen.
Kill switch is sticky. Agent id cannot buy a bypass.
"""

from __future__ import annotations

from datetime import datetime, timezone

from lumina_research.risk_core.config import RiskConfig, load_default_config
from lumina_research.risk_core.seal import install_module_seal
from lumina_research.risk_core.types import Decision, OrderProposal

_SEALED = ("propose_order", "RiskCore", "load_default_config")


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
        if equity <= 0.0:
            raise ValueError("equity must be positive")
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


class RiskCore:
    """Config-driven hard rules. Subclassing is forbidden."""

    __slots__ = ("_config", "_book")
    _config: RiskConfig
    _book: _Book

    def __init_subclass__(cls) -> None:
        raise TypeError("RiskCore cannot be subclassed")

    def __init__(self, config: object, *, equity: float) -> None:
        if not isinstance(config, RiskConfig):
            raise TypeError("config must be a frozen RiskConfig")
        object.__setattr__(self, "_config", config)
        object.__setattr__(self, "_book", _Book(equity))

    def __setattr__(self, name: str, value: object) -> None:
        if name in {"_config", "_book"} and hasattr(self, name):
            raise AttributeError("RiskCore config and book binding are immutable")
        object.__setattr__(self, name, value)

    @property
    def config(self) -> RiskConfig:
        return self._config

    def heartbeat(self, at: datetime) -> None:
        if at.tzinfo is None:
            raise ValueError("heartbeat timestamp must be timezone-aware UTC")
        self._book.last_heartbeat = at.astimezone(timezone.utc)

    def record_pnl(self, pnl: float) -> None:
        book = self._book
        book.daily_pnl += float(pnl)
        book.equity += float(pnl)
        if book.equity > book.peak_equity:
            book.peak_equity = book.equity
        if book.peak_equity > 0.0:
            book.drawdown_pct = max(0.0, (book.peak_equity - book.equity) / book.peak_equity)
        self._trip_kill_from_state()

    def set_exposure(self, *, gross_notional: float, cluster_id: str, cluster_notional: float) -> None:
        if gross_notional < 0.0 or cluster_notional < 0.0:
            raise ValueError("notionals must be >= 0")
        if not cluster_id:
            raise ValueError("cluster_id is required")
        self._book.gross_notional = float(gross_notional)
        self._book.cluster_notional[cluster_id] = float(cluster_notional)

    def propose_order(self, proposal: OrderProposal) -> Decision:
        return _decide(self._config, self._book, proposal)

    def _trip_kill_from_state(self) -> None:
        book = self._book
        cfg = self._config
        if book.equity <= 0.0:
            _engage(book, "equity_exhausted")
        if book.drawdown_pct >= cfg.max_total_drawdown_pct:
            _engage(book, "drawdown_breach")
        if book.daily_pnl <= -cfg.max_daily_loss_pct * max(book.peak_equity, book.equity, 1e-12):
            _engage(book, "max_daily_loss")


def propose_order(proposal: OrderProposal, *, core: RiskCore | None = None) -> Decision:
    engine = core if core is not None else _default_core()
    return engine.propose_order(proposal)


def _default_core() -> RiskCore:
    return RiskCore(load_default_config(), equity=100_000.0)


def _engage(book: _Book, reason: str) -> None:
    book.kill = True
    if not book.kill_reason:
        book.kill_reason = reason


def _decide(config: RiskConfig, book: _Book, proposal: OrderProposal) -> Decision:
    now = proposal.submitted_at_utc
    if now.tzinfo is None:
        return Decision.rejected(proposal, "timestamp_not_utc")
    now_utc = now.astimezone(timezone.utc)

    if book.last_heartbeat is None:
        _engage(book, "heartbeat_missing")
        return Decision.rejected(proposal, "kill_switch:heartbeat_missing")
    age = (now_utc - book.last_heartbeat).total_seconds()
    if age > config.heartbeat_timeout_sec:
        _engage(book, "heartbeat_loss")
        return Decision.rejected(proposal, "kill_switch:heartbeat_loss")

    if book.kill:
        return Decision.rejected(proposal, f"kill_switch:{book.kill_reason or 'engaged'}")

    if book.drawdown_pct >= config.max_total_drawdown_pct:
        _engage(book, "drawdown_breach")
        return Decision.rejected(proposal, "kill_switch:drawdown_breach")

    daily_cap = config.max_daily_loss_pct * max(book.peak_equity, 1e-12)
    if book.daily_pnl <= -daily_cap:
        _engage(book, "max_daily_loss")
        return Decision.rejected(proposal, "kill_switch:max_daily_loss")

    if book.equity <= 0.0:
        _engage(book, "equity_exhausted")
        return Decision.rejected(proposal, "kill_switch:equity_exhausted")

    qty = proposal.quantity
    notional = proposal.notional
    reasons: list[str] = []

    max_position_notional = config.max_position_pct * book.equity
    if notional > max_position_notional:
        scale = max_position_notional / notional
        qty *= scale
        notional = max_position_notional
        reasons.append("max_position_pct")

    max_gross = config.leverage_cap * book.equity
    projected_gross = book.gross_notional + notional
    if projected_gross > max_gross:
        allowed = max(0.0, max_gross - book.gross_notional)
        if allowed <= 0.0:
            return Decision.rejected(proposal, "leverage_cap")
        scale = allowed / notional
        qty *= scale
        notional = allowed
        reasons.append("leverage_cap")

    cluster_now = book.cluster_notional.get(proposal.cluster_id, 0.0)
    max_cluster = config.correlation_cluster_limit_pct * book.equity
    projected_cluster = cluster_now + notional
    if projected_cluster > max_cluster:
        allowed = max(0.0, max_cluster - cluster_now)
        if allowed <= 0.0:
            return Decision.rejected(proposal, "correlation_cluster_limit")
        scale = allowed / notional
        qty *= scale
        notional = allowed
        reasons.append("correlation_cluster_limit")

    if qty + 1e-12 < config.min_quantity or notional <= 0.0:
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

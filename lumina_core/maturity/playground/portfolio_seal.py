"""Playground SIM envelope from the account, not from a typed number.

The daily floor is 2% of cash (CashValue). It moves when that cash moves.
Missing cash stays unsealed. Net liquidation is not a substitute. REAL is never written.
"""
from __future__ import annotations

import os
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from lumina_core.maturity.playground.envelope import (
    envelope_sealed_for_pass,
    read_seal,
    write_operator_seal,
)

# Two percent of cash. The dollar floor changes when the account cash changes.
DAILY_LOSS_FRACTION = 0.02
_REFRESH_DRIFT = 0.05
_SIM_MODES = frozenset({"sim", "paper"})
_MEMORY_MARGIN_RATIO = 0.9
_MEMORY_MARGIN_TOLERANCE = 0.005
_FACTORY_CASH = 100_000.0


@dataclass(frozen=True)
class SimAccount:
    cash: float | None
    equity: float | None
    buying_power: float | None
    account_name: str
    gateway_kind: str


def caps_from_equity(equity: float, *, fraction: float = DAILY_LOSS_FRACTION) -> tuple[float, float]:
    """Negative daily floor and matching open-risk cap, both the same budget."""
    budget = abs(float(equity)) * float(fraction)
    if budget <= 0.0:
        raise ValueError("equity_budget_empty")
    return -budget, budget


def _finite(value: Any) -> float | None:
    if isinstance(value, bool) or value is None:
        return None
    try:
        number = float(value)
    except (TypeError, ValueError):
        return None
    if number != number or number in (float("inf"), float("-inf")):
        return None
    return number


def _positive(value: Any) -> float | None:
    number = _finite(value)
    if number is None or number <= 0.0:
        return None
    return number


def _memory_kind(equity: float | None, buying_power: float | None, explicit: str) -> str:
    if str(explicit or "").strip().lower() == "memory":
        return "memory"
    if equity is None or equity <= 0.0 or buying_power is None:
        return ""
    if abs((buying_power / equity) - _MEMORY_MARGIN_RATIO) <= _MEMORY_MARGIN_TOLERANCE:
        return "memory"
    return ""


def _account_ready(account: SimAccount | None) -> bool:
    """Cash is the seal basis. A memory-gateway reading is not NinjaTrader cash."""
    return (
        account is not None
        and account.cash is not None
        and account.gateway_kind != "memory"
    )


def _sim_from_broker(account: Any) -> SimAccount | None:
    if account is None:
        return None
    raw = getattr(account, "raw", None)
    raw = raw if isinstance(raw, dict) else {}
    equity = _positive(getattr(account, "equity", None))
    cash = _positive(getattr(account, "balance", None))
    buying_power = _finite(getattr(account, "available_margin", None))
    if cash is None and equity is None:
        return None
    name = str(raw.get("account_name") or getattr(account, "account_name", "") or "")
    kind = _memory_kind(equity, buying_power, str(raw.get("gateway_kind") or ""))
    return SimAccount(
        cash=cash,
        equity=equity,
        buying_power=buying_power,
        account_name=name,
        gateway_kind=kind,
    )


def read_sim_account() -> SimAccount | None:
    """Cash, net liquidation, and buying power. None when the account was not read.

    Uses the live Brain session when one is already up. Otherwise a unary
    account read. Never opens a TradingStream.
    """
    session: SimAccount | None = None
    try:
        from lumina_core.broker.ninjatrader.fabric_link_supervisor import (
            get_fabric_link_supervisor,
        )

        client = get_fabric_link_supervisor().get_client()
    except Exception:
        client = None
    if client is not None:
        try:
            account, _positions, code = client.get_account_state()
            if code == "ok":
                session = _sim_from_broker(account)
                if _account_ready(session):
                    return session
        except Exception:
            session = None
    unary: SimAccount | None = None
    try:
        from lumina_core.broker.ninjatrader.fabric_client import read_account_snapshot_unary

        unary = _sim_from_broker(read_account_snapshot_unary())
    except Exception:
        unary = None
    if _account_ready(unary):
        return unary
    # Keep a real equity reading when cash was not on that channel.
    for candidate in (unary, session):
        if candidate is not None and candidate.gateway_kind != "memory":
            return candidate
    return None


def read_sim_equity() -> float | None:
    """Net liquidation. None when that number has not been read."""
    account = read_sim_account()
    if account is None or account.equity is None:
        return None
    return float(account.equity)


_ACCOUNT_CACHE: tuple[float, SimAccount | None] = (0.0, None)
_ACCOUNT_CACHE_SEC = 5.0


def cached_sim_account() -> SimAccount | None:
    """Last live account read. A miss stays cached so the deck does not hammer NT."""
    global _ACCOUNT_CACHE
    now = time.monotonic()
    stamp, cached = _ACCOUNT_CACHE
    if stamp > 0.0 and now - stamp < _ACCOUNT_CACHE_SEC:
        return cached
    cached = read_sim_account()
    _ACCOUNT_CACHE = (now, cached)
    return cached


def floor_sentence(
    *,
    cap: float,
    cash: float,
    equity: float | None,
    buying_power: float | None,
    account_name: str,
) -> str:
    """The screen line. The cap is the sealed number. Cash, net, and buying power are the reading."""
    if abs(abs(float(cap)) - abs(float(cash)) * DAILY_LOSS_FRACTION) < 1.0:
        head = f"Dagvloer {cap:.0f} = -2% van cash {cash:.0f}."
    else:
        head = f"Dagvloer {cap:.0f}. Cash {cash:.0f}."
    if equity is not None and equity > 0.0:
        net = f"Netto {equity:.0f}."
    else:
        net = "Netto niet gelezen."
    if buying_power is not None and buying_power > 0.0:
        power = f"Koopkracht {buying_power:.0f}."
    else:
        power = "Koopkracht niet gelezen."
    label = str(account_name or "").strip() or "Sim"
    text = f"{head} {net} {power} Rekening {label}."
    if abs(float(cash) - _FACTORY_CASH) < 1.0:
        text += (
            f" {label} cash is {cash:.0f}. "
            "Reset Initial cash in NinjaTrader als het budget anders moet. "
            "De vloer volgt die cash."
        )
    return text


def configured_account_name(workspace_root: Path | str) -> str:
    """Operator account from config.yaml. Empty when the file names none."""
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
    broker = raw.get("broker")
    if not isinstance(broker, dict):
        return ""
    nt = broker.get("ninjatrader")
    if not isinstance(nt, dict):
        return ""
    return str(nt.get("account_name") or "").strip()


def account_wait_sentence(bound: str, wanted: str) -> str:
    """The addon is still on another account. Do not seal that cash as the requested floor."""
    seen = str(bound or "").strip() or "geen rekeningnaam"
    asked = str(wanted or "").strip()
    return (
        f"Addon leest {seen}. Gevraagde rekening is {asked}. "
        f"De dagvloer blijft de verzegeling van {seen} tot de addon {asked} leest."
    )


def workspace_mode(workspace_root: Path | str) -> str:
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


def floor_mode(engine: Any, workspace_root: Path | str) -> str:
    """SIM only when neither the process nor the config says REAL."""
    env = str(os.getenv("LUMINA_MODE") or os.getenv("TRADE_MODE") or "").strip().lower()
    cfg = workspace_mode(workspace_root)
    if env in {"real", "live"} or cfg in {"real", "live"}:
        return "real"
    if cfg in _SIM_MODES:
        return cfg
    if env in _SIM_MODES:
        return env
    return ""


def apply_sim_portfolio_caps(
    controller: Any,
    *,
    mode: str,
    cap: float,
    open_risk: float,
) -> bool:
    """Point the SIM hard floor at the portfolio budget. Never raises open risk. Never touches REAL."""
    if str(mode or "").strip().lower() not in _SIM_MODES:
        return False
    if float(cap) >= 0.0 or float(open_risk) <= 0.0 or controller is None:
        return False
    seen: set[int] = set()
    touched = False
    for limits in (
        getattr(controller, "limits", None),
        getattr(controller, "_base_limits", None),
        getattr(controller, "_active_limits", None),
    ):
        if limits is None or id(limits) in seen:
            continue
        seen.add(id(limits))
        limits.daily_loss_cap = float(cap)
        if float(getattr(limits, "max_total_open_risk", 0.0) or 0.0) > float(open_risk):
            limits.max_total_open_risk = float(open_risk)
        per = float(getattr(limits, "max_open_risk_per_instrument", 0.0) or 0.0)
        if per > float(open_risk):
            limits.max_open_risk_per_instrument = float(open_risk)
        touched = True
    return touched


def maintain_sim_floor(engine: Any, workspace_root: Path | str) -> str:
    """Refresh the SIM seal and the in-memory hard floor. REAL is a no-op."""
    mode = floor_mode(engine, workspace_root)
    if mode not in _SIM_MODES:
        return ""
    sentence = ensure_portfolio_seal(workspace_root)
    raw = read_seal(workspace_root)
    if not isinstance(raw, dict) or raw.get("source") != "portfolio_fraction":
        return sentence
    if not envelope_sealed_for_pass(workspace_root):
        return sentence
    apply_sim_portfolio_caps(
        getattr(engine, "risk_controller", None),
        mode=mode,
        cap=float(raw["daily_loss_cap"]),
        open_risk=float(raw["max_total_open_risk"]),
    )
    return sentence


def ensure_portfolio_seal(workspace_root: Path | str) -> str:
    """Write or refresh the SIM seal from cash. Returns the sentence the screen shows."""
    if workspace_mode(workspace_root) not in _SIM_MODES:
        return "Dagvloer blijft dicht buiten SIM."
    account = read_sim_account()
    if account is None or account.cash is None:
        return "Sim-cash nog niet gelezen. Dagvloer opent bij een gelezen cash-saldo."
    if _memory_kind(account.equity, account.buying_power, account.gateway_kind) == "memory":
        return (
            "Gelezen rekening komt uit de memory-gateway. "
            "Dagvloer blijft open tot NinjaTrader Sim de cash schrijft."
        )
    wanted = configured_account_name(workspace_root)
    bound = str(account.account_name or "").strip()
    if wanted and wanted.casefold() != bound.casefold():
        return account_wait_sentence(bound, wanted)
    try:
        cap, risk = caps_from_equity(account.cash)
    except ValueError:
        return "Sim-cash is 0. Dagvloer opent zodra de cash boven 0 staat."
    current = read_seal(workspace_root)
    sealed_cap = cap
    if isinstance(current, dict) and envelope_sealed_for_pass(workspace_root):
        same_basis = str(current.get("floor_basis") or "") == "cash"
        old_cash = _positive(current.get("cash"))
        if (
            same_basis
            and old_cash is not None
            and abs(account.cash - old_cash) / old_cash < _REFRESH_DRIFT
        ):
            sealed_cap = float(current["daily_loss_cap"])
            return floor_sentence(
                cap=sealed_cap,
                cash=account.cash,
                equity=account.equity,
                buying_power=account.buying_power,
                account_name=account.account_name,
            )
    write_operator_seal(
        workspace_root,
        daily_loss_cap=cap,
        max_total_open_risk=risk,
        source="portfolio_fraction",
        equity=account.equity if account.equity is not None else account.cash,
        daily_loss_fraction=DAILY_LOSS_FRACTION,
        cash=account.cash,
        net_liquidation=account.equity,
        buying_power=_positive(account.buying_power),
        account_name=account.account_name,
        floor_basis="cash",
    )
    return floor_sentence(
        cap=cap,
        cash=account.cash,
        equity=account.equity,
        buying_power=account.buying_power,
        account_name=account.account_name,
    )

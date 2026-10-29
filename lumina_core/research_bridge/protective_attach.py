"""ATM template (A) default, companion STOP (C) fallback. Not B or D.

Research team decision (relayed by Steve 2026-10-29): server-side NT ATM
template is primary. Companion STOP is fallback when ATM is missing or
unreliable for that broker/connection. Fail-closed: no entry if neither ATM
nor a confirmed C-stop. Residual C risk: MARKET can fill before STOP is
working; hard timeout then Risk Core flatten.

Follow-up (research team 2026-10-29 22:08, sha 991138fd, not Steve): one
generic ATR ATM template for ES/NQ/MES/MNQ; ATM confirm uses the same short
window; fill-before-ATM flattens if ATM is not confirmed.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta
from typing import Any, Mapping

from lumina_core.broker.broker_bridge.schemas import Order, OrderResult

SOURCE_LABEL = "research team decision (relayed by Steve 2026-10-29)"
FOLLOWUP_SOURCE = "research team 2026-10-29 22:08 sha991138fd (not Steve)"
PATH_ATM = "atm"
PATH_COMPANION = "companion"
PATH_REFUSED = "refused"
ATTACH_ATM = "atm"
ATTACH_COMPANION = "companion"
ATM_UNAVAILABLE = "atm_unavailable"
ATM_UNCONFIRMED = "atm_unconfirmed"
FILL_BEFORE_ATM = "atm_unconfirmed_after_fill"
COMPANION_UNCONFIRMED = "companion_stop_unconfirmed"
PROTECTIVE_REFUSED = "protective_attach_refused"
DEFAULT_CONFIRM_TIMEOUT_MS = 5000
DEFAULT_COMPANION_CONFIRM_TIMEOUT_MS = DEFAULT_CONFIRM_TIMEOUT_MS
DEFAULT_ATM_CONFIRM_TIMEOUT_MS = DEFAULT_CONFIRM_TIMEOUT_MS
GENERIC_ATM_TEMPLATE_NAME = "LuminaProtective"
GENERIC_ATM_INSTRUMENTS = ("ES", "NQ", "MES", "MNQ")
ATM_STOP_ATR_PERIOD = 14
ATM_STOP_ATR_MULTIPLE = 1.5
ATM_TARGET_ATR_MULTIPLE = 2.0
RESIDUAL_C_RISK = (
    "Companion STOP is a second order. MARKET may fill before the STOP is "
    "working. Window is companion_confirm_timeout_ms; on miss, Risk Core "
    "flattens. ATM (option A) has none of that second-order race when NT "
    "attaches stop+target+OCO on the server at entry."
)
RESIDUAL_A_RACE = (
    "NT Submit then StartAtmStrategy: MARKET may fill before ATM children are "
    "working. Window is atm_confirm_timeout_ms; on miss, companion fallback if "
    "enabled, else Risk Core flatten. ATM reject after no fill does not retry MARKET."
)


@dataclass(frozen=True, slots=True)
class ProtectiveAttachConfig:
    templates_by_account: tuple[tuple[str, str], ...] = ()
    templates_by_connection: tuple[tuple[str, str], ...] = ()
    default_template: str = ""
    fallback_companion: bool = True
    companion_confirm_timeout_ms: int = DEFAULT_COMPANION_CONFIRM_TIMEOUT_MS
    atm_confirm_timeout_ms: int = DEFAULT_ATM_CONFIRM_TIMEOUT_MS
    account: str = "Sim101"
    connection: str = ""


@dataclass(frozen=True, slots=True)
class ProtectiveAttachPlan:
    path: str
    atm_template: str
    reason: str
    companion_confirm_timeout_ms: int
    residual_risk: str
    atm_confirm_timeout_ms: int = DEFAULT_ATM_CONFIRM_TIMEOUT_MS


def _pairs(raw: object) -> tuple[tuple[str, str], ...]:
    if not isinstance(raw, Mapping):
        return ()
    out: list[tuple[str, str]] = []
    for key, value in raw.items():
        name = str(key or "").strip()
        if not name:
            continue
        out.append((name, str(value or "").strip()))
    return tuple(out)


def _lookup(pairs: tuple[tuple[str, str], ...], name: str) -> str | None:
    wanted = str(name or "").strip().lower()
    if not wanted:
        return None
    for key, value in pairs:
        if str(key).strip().lower() == wanted:
            return str(value)
    return None


def _timeout_ms(raw: object, default: int) -> int:
    try:
        timeout = int(raw)
    except (TypeError, ValueError):
        return int(default)
    if timeout < 1:
        return int(default)
    return timeout


def from_mapping(
    raw: Mapping[str, Any] | None,
    *,
    account: str = "Sim101",
    connection: str = "",
) -> ProtectiveAttachConfig:
    blob: Mapping[str, Any] = raw if isinstance(raw, Mapping) else {}
    atm = blob.get("atm") if isinstance(blob.get("atm"), Mapping) else blob
    if not isinstance(atm, Mapping):
        atm = {}
    timeout = _timeout_ms(
        atm.get("companion_confirm_timeout_ms", DEFAULT_COMPANION_CONFIRM_TIMEOUT_MS),
        DEFAULT_COMPANION_CONFIRM_TIMEOUT_MS,
    )
    atm_timeout = _timeout_ms(atm.get("atm_confirm_timeout_ms", timeout), timeout)
    fallback = atm.get("fallback_companion", True)
    return ProtectiveAttachConfig(
        templates_by_account=_pairs(atm.get("templates_by_account")),
        templates_by_connection=_pairs(atm.get("templates_by_connection")),
        default_template=str(atm.get("default_template") or atm.get("atm_strategy_template") or "").strip(),
        fallback_companion=fallback is not False,
        companion_confirm_timeout_ms=timeout,
        atm_confirm_timeout_ms=atm_timeout,
        account=str(account or "Sim101").strip() or "Sim101",
        connection=str(connection or "").strip(),
    )


def from_engine(engine: object | None) -> ProtectiveAttachConfig:
    if engine is None:
        return from_mapping(None)
    config = getattr(engine, "config", None)
    account = str(
        getattr(engine, "nt_connected_account", None)
        or getattr(config, "account_name", None)
        or getattr(config, "ninjatrader_account_name", None)
        or "Sim101"
    ).strip() or "Sim101"
    connection = str(
        getattr(config, "ninjatrader_connection", None) or getattr(engine, "nt_connection", None) or ""
    ).strip()
    nt_cfg = getattr(config, "ninjatrader", None) if config is not None else None
    if isinstance(nt_cfg, Mapping):
        return from_mapping(nt_cfg, account=account, connection=connection)
    if nt_cfg is not None:
        raw = {
            "atm": {
                "templates_by_account": getattr(nt_cfg, "templates_by_account", None)
                or getattr(nt_cfg, "atm_strategy_templates", None)
                or {},
                "templates_by_connection": getattr(nt_cfg, "templates_by_connection", None) or {},
                "default_template": getattr(nt_cfg, "atm_strategy_template", None) or "",
                "fallback_companion": getattr(nt_cfg, "atm_fallback_companion", True),
                "companion_confirm_timeout_ms": getattr(
                    nt_cfg, "companion_confirm_timeout_ms", DEFAULT_COMPANION_CONFIRM_TIMEOUT_MS
                ),
                "atm_confirm_timeout_ms": getattr(
                    nt_cfg, "atm_confirm_timeout_ms", DEFAULT_ATM_CONFIRM_TIMEOUT_MS
                ),
            }
        }
        nested = getattr(nt_cfg, "atm", None)
        if nested is not None:
            raw = {"atm": nested if isinstance(nested, Mapping) else vars(nested)}
        return from_mapping(raw, account=account, connection=connection)
    return from_mapping(None, account=account, connection=connection)


def resolve_atm_template(cfg: ProtectiveAttachConfig) -> str:
    conn = _lookup(cfg.templates_by_connection, cfg.connection)
    if conn is not None:
        return str(conn).strip()
    acct = _lookup(cfg.templates_by_account, cfg.account)
    if acct is not None:
        return str(acct).strip()
    return str(cfg.default_template or "").strip()


def plan_protective_attach(cfg: ProtectiveAttachConfig, *, reduce_only: bool = False) -> ProtectiveAttachPlan:
    timeout = int(cfg.companion_confirm_timeout_ms)
    atm_timeout = int(cfg.atm_confirm_timeout_ms)
    if reduce_only is True:
        return ProtectiveAttachPlan(PATH_REFUSED, "", "reduce_only", timeout, "", atm_timeout)
    template = resolve_atm_template(cfg)
    if template:
        return ProtectiveAttachPlan(PATH_ATM, template, "atm_default", timeout, RESIDUAL_A_RACE, atm_timeout)
    if cfg.fallback_companion is True:
        return ProtectiveAttachPlan(
            PATH_COMPANION,
            "",
            "atm_missing_companion_fallback",
            timeout,
            RESIDUAL_C_RISK,
            atm_timeout,
        )
    return ProtectiveAttachPlan(PATH_REFUSED, "", PROTECTIVE_REFUSED, timeout, "", atm_timeout)


def within_confirm_timeout(*, started: datetime, now: datetime, timeout_ms: int) -> bool:
    elapsed_ms = (now - started) / timedelta(milliseconds=1)
    return elapsed_ms <= float(max(1, int(timeout_ms)))


def atm_confirmed(result: OrderResult | None) -> bool:
    if result is None or result.accepted is not True:
        return False
    raw = result.raw if isinstance(result.raw, dict) else {}
    kind = str(raw.get("protective_attach") or "").strip().lower()
    return kind == ATTACH_ATM


def atm_confirmed_on_time(
    result: OrderResult | None,
    *,
    started: datetime,
    now: datetime,
    timeout_ms: int,
) -> bool:
    if within_confirm_timeout(started=started, now=now, timeout_ms=timeout_ms) is not True:
        return False
    return atm_confirmed(result)


def live_fill_without_confirmed_atm(result: OrderResult | None) -> bool:
    """Venue may have a fill even when ATM children are missing or the attach was rejected."""
    if result is None:
        return False
    if atm_confirmed(result) is True:
        return False
    if result.accepted is True:
        return True
    if int(result.filled_qty or 0) > 0:
        return True
    raw = result.raw if isinstance(result.raw, dict) else {}
    blob = " ".join(
        (
            str(result.message or ""),
            str(result.status or ""),
            str(raw.get("rejection_reason") or ""),
            str(raw.get("reason") or ""),
        )
    ).lower()
    return FILL_BEFORE_ATM in blob or "fill_before_atm" in blob


def companion_confirmed(result: OrderResult | None, *, started: datetime, now: datetime, timeout_ms: int) -> bool:
    if within_confirm_timeout(started=started, now=now, timeout_ms=timeout_ms) is not True:
        return False
    if result is None or result.accepted is not True:
        return False
    status = str(result.status or "").strip().lower()
    if status in {"rejected", "error", "cancelled"}:
        return False
    return True


def emergency_flatten_order(*, instrument: str, entry_side: str, quantity: int, strategy_id: str) -> Order:
    side = "SELL" if str(entry_side or "").strip().upper() == "BUY" else "BUY"
    return Order(
        symbol=str(instrument),
        side=side,
        quantity=max(1, int(quantity)),
        order_type="MARKET",
        metadata={
            "reduce_only": True,
            "emergency": True,
            "reason": "unconfirmed_protective_stop",
            "strategy_id": str(strategy_id),
            "mode_context": "sim_real_guard",
            "protected": False,
        },
    )

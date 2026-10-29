"""SIM account whitelist for the live Risk Core (ADR-0061 / S1).

Prefix helpers (`Sim*`, `DEMO*`) are diagnostics only and never allow.
An empty or omitted list denies every account. The process-frozen list cannot
widen at runtime except through an HMAC-signed operator release.
"""

from __future__ import annotations

import hmac
import logging
import os
import threading
from collections.abc import Iterable, Mapping, Sequence
from datetime import datetime, timezone
from typing import Final

from lumina_core.broker.ninjatrader.account_names import (
    account_on_sim_whitelist,
    canonicalize_account_name,
    is_paper_account_name,
)

logger = logging.getLogger("lumina.risk.sim_account_guard")

SIM_WHITELIST_EMPTY: Final[str] = "sim_whitelist_empty"
SIM_ACCOUNT_NOT_WHITELISTED: Final[str] = "sim_account_not_whitelisted"
SIM_WHITELIST_TAMPERED: Final[str] = "sim_whitelist_tampered"
SIM_WHITELIST_WIDEN_REFUSED: Final[str] = "sim_whitelist_widen_refused"
SIM_WHITELIST_LIVE_NAME_FORBIDDEN: Final[str] = "sim_whitelist_live_name_forbidden"
SIM_WHITELIST_WIDENED: Final[str] = "sim_whitelist_widened"
ACCOUNT_UNKNOWN: Final[str] = "ninjatrader_account_unknown"

_MODES_REQUIRING_WHITELIST: Final[frozenset[str]] = frozenset({"sim", "sim_real_guard"})
_SEAL_KEY: Final[bytes] = os.urandom(32)


def canonicalize_whitelist(names: Iterable[object] | None) -> tuple[str, ...]:
    """Stable unique names. Empty input becomes an empty tuple (deny-all)."""
    if names is None:
        return ()
    if isinstance(names, (str, bytes)):
        return ()
    seen: dict[str, str] = {}
    for raw in names:
        label = canonicalize_account_name(str(raw) if raw is not None else "")
        if not label:
            continue
        key = label.casefold()
        if key not in seen:
            seen[key] = label
    return tuple(seen.values())


def _seal_for(names: frozenset[str]) -> bytes:
    body = "|".join(sorted(item.casefold() for item in names)).encode("utf-8")
    return hmac.new(_SEAL_KEY, body, "sha256").digest()


def log_sim_reject(*, reason: str, account: str, mode: str, agent_id: str = "") -> None:
    logger.error(
        "s1.sim_whitelist.reject",
        extra={
            "event_data": {
                "event": "s1.sim_whitelist.reject",
                "reason": str(reason),
                "account": str(account),
                "mode": str(mode),
                "agent_id": str(agent_id or ""),
                "timestamp": datetime.now(timezone.utc).isoformat(),
            }
        },
    )


class SimWhitelistLock:
    """Process-frozen SIM whitelist. Runtime yaml/env cannot add names."""

    def __init__(self) -> None:
        self._mutex = threading.Lock()
        self._frozen: frozenset[str] | None = None
        self._seal: bytes = b""

    def is_frozen(self) -> bool:
        with self._mutex:
            return self._frozen is not None

    def is_tampered(self) -> bool:
        with self._mutex:
            if self._frozen is None:
                return False
            return not hmac.compare_digest(self._seal, _seal_for(self._frozen))

    def freeze(self, names: Iterable[object] | None) -> frozenset[str]:
        """First call wins. Later calls ignore extra names."""
        with self._mutex:
            if self._frozen is None:
                frozen = frozenset(canonicalize_whitelist(names))
                self._frozen = frozen
                self._seal = _seal_for(frozen)
            return self._snapshot_locked()

    def current(self) -> frozenset[str]:
        with self._mutex:
            return self._snapshot_locked()

    def _snapshot_locked(self) -> frozenset[str]:
        frozen = self._frozen
        if frozen is None:
            return frozenset()
        if not hmac.compare_digest(self._seal, _seal_for(frozen)):
            return frozenset()
        return frozenset(frozen)

    def effective(self, requested: Iterable[object] | None) -> tuple[frozenset[str], str]:
        """Return (frozen names, status). Requested extras cannot widen the set."""
        with self._mutex:
            if self._frozen is None:
                frozen = frozenset(canonicalize_whitelist(requested))
                self._frozen = frozen
                self._seal = _seal_for(frozen)
                return frozenset(frozen), "ok"
            if not hmac.compare_digest(self._seal, _seal_for(self._frozen)):
                return frozenset(), SIM_WHITELIST_TAMPERED
            current = frozenset(self._frozen)
            frozen_fold = {item.casefold() for item in current}
            extra_labels = tuple(
                item for item in canonicalize_whitelist(requested) if item.casefold() not in frozen_fold
            )
            if extra_labels:
                logger.error(
                    "s1.sim_whitelist.widen_refused",
                    extra={
                        "event_data": {
                            "event": "s1.sim_whitelist.widen_refused",
                            "reason": SIM_WHITELIST_WIDEN_REFUSED,
                            "extra": list(extra_labels),
                            "timestamp": datetime.now(timezone.utc).isoformat(),
                        }
                    },
                )
            return current, "ok"

    def widen(self, names: Iterable[object]) -> tuple[bool, str]:
        """Add paper names. Caller must have already verified a signed release."""
        extra = canonicalize_whitelist(names)
        if not extra:
            return False, SIM_WHITELIST_WIDEN_REFUSED
        for name in extra:
            if not is_paper_account_name(name):
                return False, SIM_WHITELIST_LIVE_NAME_FORBIDDEN
        with self._mutex:
            if self._frozen is not None and not hmac.compare_digest(self._seal, _seal_for(self._frozen)):
                return False, SIM_WHITELIST_TAMPERED
            current = self._frozen if self._frozen is not None else frozenset()
            merged = frozenset(current | set(extra))
            self._frozen = merged
            self._seal = _seal_for(merged)
        return True, SIM_WHITELIST_WIDENED


LOCK = SimWhitelistLock()


def connected_account_from_engine(engine: object | None) -> str:
    """Fail-closed resolver. Empty string means the account is unknown."""
    if engine is None:
        return ""
    for attr in ("nt_connected_account", "connected_account"):
        label = canonicalize_account_name(str(getattr(engine, attr, "") or ""))
        if label:
            return label
    connection = getattr(engine, "nt_connection", None) or getattr(engine, "connection", None)
    if connection is not None:
        label = canonicalize_account_name(str(getattr(connection, "account_name", "") or ""))
        if label:
            return label
    config = getattr(engine, "config", None)
    if config is not None:
        label = canonicalize_account_name(str(getattr(config, "ninjatrader_account_name", "") or ""))
        if label:
            return label
        broker = getattr(config, "broker", None)
        if isinstance(broker, Mapping):
            nt = broker.get("ninjatrader")
            if isinstance(nt, Mapping):
                label = canonicalize_account_name(str(nt.get("account_name") or ""))
                if label:
                    return label
    return ""


def whitelist_from_engine(engine: object | None) -> tuple[str, ...]:
    """Operator list from the engine snapshot. Env is never consulted."""
    if engine is None:
        return ()
    config = getattr(engine, "config", None)
    if config is None:
        return ()
    raw = getattr(config, "ninjatrader_sim_account_whitelist", None)
    if raw is None:
        broker = getattr(config, "broker", None)
        if isinstance(broker, Mapping):
            nt = broker.get("ninjatrader")
            if isinstance(nt, Mapping):
                raw = nt.get("sim_account_whitelist")
    if raw is None:
        return ()
    if isinstance(raw, (str, bytes)):
        return ()
    if isinstance(raw, Sequence):
        return canonicalize_whitelist(raw)
    return ()


def admit_sim_account(
    account: str,
    whitelist: Sequence[str] | None = None,
    *,
    mode: str = "sim",
    agent_id: str = "",
) -> tuple[bool, str]:
    """Risk Core SIM admit. Empty list denies. Prefix match never allows."""
    label = canonicalize_account_name(account)
    if not label:
        log_sim_reject(reason=ACCOUNT_UNKNOWN, account=account, mode=mode, agent_id=agent_id)
        return False, ACCOUNT_UNKNOWN
    effective, status = LOCK.effective(whitelist)
    if status == SIM_WHITELIST_TAMPERED:
        log_sim_reject(reason=SIM_WHITELIST_TAMPERED, account=label, mode=mode, agent_id=agent_id)
        return False, SIM_WHITELIST_TAMPERED
    if not effective:
        log_sim_reject(reason=SIM_WHITELIST_EMPTY, account=label, mode=mode, agent_id=agent_id)
        return False, SIM_WHITELIST_EMPTY
    if not is_paper_account_name(label):
        log_sim_reject(reason=SIM_ACCOUNT_NOT_WHITELISTED, account=label, mode=mode, agent_id=agent_id)
        return False, SIM_ACCOUNT_NOT_WHITELISTED
    if not account_on_sim_whitelist(label, tuple(effective)):
        log_sim_reject(reason=SIM_ACCOUNT_NOT_WHITELISTED, account=label, mode=mode, agent_id=agent_id)
        return False, SIM_ACCOUNT_NOT_WHITELISTED
    return True, "ok"


def modes_requiring_whitelist() -> frozenset[str]:
    return _MODES_REQUIRING_WHITELIST


def apply_signed_whitelist_widen(
    extra_names: Sequence[str],
    *,
    verified: bool,
    verify_reason: str,
) -> tuple[bool, str]:
    """Widen only after a successful HMAC verify of purpose sim_whitelist_widen."""
    if verified is not True:
        return False, str(verify_reason or SIM_WHITELIST_WIDEN_REFUSED)
    return LOCK.widen(extra_names)


__all__ = [
    "ACCOUNT_UNKNOWN",
    "LOCK",
    "SIM_ACCOUNT_NOT_WHITELISTED",
    "SIM_WHITELIST_EMPTY",
    "SIM_WHITELIST_LIVE_NAME_FORBIDDEN",
    "SIM_WHITELIST_TAMPERED",
    "SIM_WHITELIST_WIDEN_REFUSED",
    "SIM_WHITELIST_WIDENED",
    "SimWhitelistLock",
    "admit_sim_account",
    "apply_signed_whitelist_widen",
    "canonicalize_whitelist",
    "connected_account_from_engine",
    "log_sim_reject",
    "modes_requiring_whitelist",
    "whitelist_from_engine",
]

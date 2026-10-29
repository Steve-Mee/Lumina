"""SIM whitelist and LIVE_RELEASE. Research agents cannot mutate this config."""

from __future__ import annotations

from collections.abc import Iterable
from dataclasses import dataclass
from typing import Mapping, cast

from lumina_core.agent_orchestration.schemas_research import ExecutionMode, SignalIntent
from lumina_research.agents.frozen import Frozen

PHASE5_ALLOWED_MODES: frozenset[str] = frozenset({"shadow"})
_PACKAGED_LIVE_RELEASE = False
_PACKAGED_WHITELIST: frozenset[str] = frozenset()


class SimSafetyRefused(ValueError):
    """Account, mode, or LIVE_RELEASE attempt was refused fail-closed."""


@dataclass(frozen=True, slots=True)
class SimSafetyConfig:
    """Frozen SIM/LIVE safety snapshot. Weaker than packaged defaults is refused."""

    sim_whitelist: frozenset[str] = _PACKAGED_WHITELIST
    live_release: bool = _PACKAGED_LIVE_RELEASE
    live_adr_path: str = ""
    allowed_modes: frozenset[str] = PHASE5_ALLOWED_MODES

    def __post_init__(self) -> None:
        if self.live_release is True:
            raise SimSafetyRefused("LIVE_RELEASE cannot be enabled in Phase 5")
        if self.live_adr_path.strip():
            raise SimSafetyRefused("LIVE_RELEASE ADR cannot be attached in Phase 5")
        if frozenset(self.allowed_modes) != PHASE5_ALLOWED_MODES:
            raise SimSafetyRefused("Phase 5 allows shadow mode only")
        extra = frozenset(self.sim_whitelist) - _PACKAGED_WHITELIST
        if extra:
            raise SimSafetyRefused("SIM whitelist cannot be expanded in Phase 5")

    def __init_subclass__(cls) -> None:
        raise TypeError("SimSafetyConfig cannot be subclassed")

    @staticmethod
    def from_mapping(raw: Mapping[str, object]) -> SimSafetyConfig:
        allowed = {"sim_whitelist", "live_release", "live_adr_path", "allowed_modes"}
        extra = set(raw) - allowed
        if extra:
            raise SimSafetyRefused(f"unknown sim-safety keys {sorted(extra)}")
        whitelist_raw = raw.get("sim_whitelist", ())
        if isinstance(whitelist_raw, (str, bytes)):
            raise SimSafetyRefused("sim_whitelist must be a sequence of account ids")
        if not isinstance(whitelist_raw, (list, tuple, frozenset, set)):
            raise SimSafetyRefused("sim_whitelist must be a sequence of account ids")
        modes_raw = raw.get("allowed_modes", ("shadow",))
        if isinstance(modes_raw, (str, bytes)) or not isinstance(modes_raw, (list, tuple, frozenset, set)):
            raise SimSafetyRefused("allowed_modes must be a sequence")
        live_raw = raw.get("live_release", False)
        if live_raw not in {True, False}:
            raise SimSafetyRefused("live_release must be a bool")
        accounts = tuple(cast(Iterable[object], whitelist_raw))
        modes = tuple(cast(Iterable[object], modes_raw))
        return SimSafetyConfig(
            sim_whitelist=frozenset(str(item) for item in accounts),
            live_release=bool(live_raw),
            live_adr_path=str(raw.get("live_adr_path", "")),
            allowed_modes=frozenset(str(item) for item in modes),
        )


class SimSafetyGate(Frozen):
    """Rejects SIM accounts off the whitelist and any live path without LIVE_RELEASE."""

    _config: SimSafetyConfig

    def __init_subclass__(cls) -> None:
        raise TypeError("SimSafetyGate cannot be subclassed")

    def __init__(self, config: SimSafetyConfig | None = None) -> None:
        self._config = config if config is not None else SimSafetyConfig()
        self._freeze()

    @property
    def config(self) -> SimSafetyConfig:
        return self._config

    def set_whitelist(self, accounts: object) -> None:
        del accounts
        raise SimSafetyRefused("research agents cannot mutate the SIM whitelist")

    def add_account(self, account_id: str) -> None:
        del account_id
        raise SimSafetyRefused("research agents cannot mutate the SIM whitelist")

    def set_live_release(self, enabled: bool, *, adr_path: str = "") -> None:
        del enabled, adr_path
        raise SimSafetyRefused("research agents cannot mutate LIVE_RELEASE")

    def apply_live_release(self, *, review: object, adr_path: str) -> None:
        del review, adr_path
        raise SimSafetyRefused("LIVE_RELEASE requires a dedicated ADR and is not enabled in Phase 5")

    def admit(
        self,
        *,
        mode: ExecutionMode,
        account_id: str,
        stale_data: bool = False,
        lost_connection: bool = False,
    ) -> None:
        if stale_data:
            raise SimSafetyRefused("stale data: no new orders")
        if lost_connection:
            raise SimSafetyRefused("lost connection: no new orders")
        if mode == "live":
            raise SimSafetyRefused("live needs a logged LIVE_RELEASE plus an ADR; Phase 5 forbids it")
        if mode == "sim":
            if account_id not in self._config.sim_whitelist:
                raise SimSafetyRefused(f"account {account_id!r} is not on the SIM whitelist")
            if "sim" not in self._config.allowed_modes:
                raise SimSafetyRefused("real SIM orders need 2-3 survivors; Phase 5 is shadow only")
            return
        if mode not in self._config.allowed_modes:
            raise SimSafetyRefused(f"mode {mode!r} is not allowed")

    def admit_intent(self, intent: SignalIntent, *, stale_data: bool = False, lost_connection: bool = False) -> None:
        self.admit(
            mode=intent.mode,
            account_id=intent.account_id,
            stale_data=stale_data,
            lost_connection=lost_connection,
        )

"""Emergency CrossTrade opt-in control plane — single SSOT (ADR-0040).

CrossTrade is an optional prosthesis, never the default skeleton.
Activation is only possible via Operator Vault / explicit audited API.

Machine truth keys (config.yaml broker section):
- ``fallback_on_fabric_failure`` — market-data emergency hop under ninjatrader
- ``live_provider: crosstrade`` — deliberate full order-path opt-in (still not default)

Plugin module load is allowed only when either path is intentionally enabled.
Silent Fabric→CrossTrade hops are forbidden.
"""

from __future__ import annotations

import logging
import os
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Literal

logger = logging.getLogger(__name__)

Source = Literal["vault", "api", "yaml", "env", "unknown"]

_AUDIT_REL = Path("logs") / "emergency_opt_in_audit.jsonl"


@dataclass(frozen=True)
class EmergencyOptInState:
    """Immutable snapshot of emergency CrossTrade control-plane state."""

    market_data_fallback: bool
    order_provider_crosstrade: bool
    live_provider: str
    source: str = "unknown"

    @property
    def plugin_loadable(self) -> bool:
        """True only when CrossTrade code may be imported/used."""
        return bool(self.market_data_fallback or self.order_provider_crosstrade)

    @property
    def enabled(self) -> bool:
        return self.plugin_loadable


def _truthy(value: Any) -> bool:
    if isinstance(value, bool):
        return value
    return str(value or "").strip().lower() in {"1", "true", "yes", "on"}


def _read_yaml_broker(config_path: Path | None = None) -> dict[str, Any]:
    path = config_path
    if path is None:
        raw = str(os.getenv("LUMINA_CONFIG") or "config.yaml").strip()
        path = Path(raw)
    if not path.is_file():
        return {}
    try:
        import yaml

        data = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
        if not isinstance(data, dict):
            return {}
        broker = data.get("broker")
        return broker if isinstance(broker, dict) else {}
    except Exception:
        return {}


def read_emergency_opt_in(
    *,
    config_path: Path | None = None,
    engine_config: Any | None = None,
) -> EmergencyOptInState:
    """Resolve SSOT emergency state from env + yaml + optional EngineConfig."""
    env_fallback = str(os.getenv("BROKER_FALLBACK_ON_FABRIC_FAILURE", "")).strip().lower()
    env_lp = str(os.getenv("BROKER_LIVE_PROVIDER", "")).strip().lower()

    broker = _read_yaml_broker(config_path)
    yaml_fallback = _truthy(broker.get("fallback_on_fabric_failure"))
    yaml_lp = str(broker.get("live_provider") or "").strip().lower()

    eng_fallback = False
    eng_lp = ""
    if engine_config is not None:
        eng_fallback = bool(getattr(engine_config, "fallback_on_fabric_failure", False))
        eng_lp = str(getattr(engine_config, "broker_live_provider", "") or "").strip().lower()

    # Precedence: explicit env → engine → yaml → safe defaults (ninjatrader, no fallback).
    # EngineConfig wins over workspace yaml when both present so factory tests /
    # process-local config objects are authoritative.
    if env_fallback in {"1", "true", "yes", "on"}:
        market_data_fallback = True
        source: str = "env"
    elif env_fallback in {"0", "false", "no", "off"}:
        market_data_fallback = False
        source = "env"
    elif engine_config is not None and hasattr(engine_config, "fallback_on_fabric_failure"):
        market_data_fallback = eng_fallback
        source = "engine"
    else:
        market_data_fallback = yaml_fallback
        source = "yaml" if broker else "unknown"

    if env_lp in {"crosstrade", "ninjatrader"}:
        live_provider = env_lp
    elif eng_lp in {"crosstrade", "ninjatrader"}:
        live_provider = eng_lp
    elif yaml_lp in {"crosstrade", "ninjatrader"}:
        live_provider = yaml_lp
    else:
        live_provider = "ninjatrader"

    return EmergencyOptInState(
        market_data_fallback=market_data_fallback,
        order_provider_crosstrade=(live_provider == "crosstrade"),
        live_provider=live_provider,
        source=source,
    )


def assert_crosstrade_plugin_allowed(
    *,
    config_path: Path | None = None,
    engine_config: Any | None = None,
    purpose: str = "use",
) -> EmergencyOptInState:
    """Fail closed if CrossTrade would be used without deliberate opt-in."""
    state = read_emergency_opt_in(config_path=config_path, engine_config=engine_config)
    if not state.plugin_loadable:
        raise RuntimeError(
            "CrossTrade plugin blocked: emergency opt-in is OFF. "
            f"Enable via Operator Vault (market-data fallback) or explicit "
            f"broker.live_provider=crosstrade (purpose={purpose!r})."
        )
    return state


def set_market_data_fallback(
    enabled: bool,
    *,
    config_manager: Any,
    source: Source = "vault",
    workspace_root: Path | None = None,
) -> EmergencyOptInState:
    """Atomically set ``broker.fallback_on_fabric_failure`` and audit the change.

    Does **not** change ``live_provider`` (orders stay exclusive Fabric unless
    operator explicitly sets live_provider=crosstrade in config).
    """
    data = config_manager.load_yaml_config()
    if not isinstance(data, dict):
        data = {}
    broker = data.get("broker")
    if not isinstance(broker, dict):
        broker = {}
        data["broker"] = broker

    prev = _truthy(broker.get("fallback_on_fabric_failure"))
    broker["fallback_on_fabric_failure"] = bool(enabled)
    # Keep live_provider fabric-first unless already intentionally crosstrade.
    lp = str(broker.get("live_provider") or "ninjatrader").strip().lower()
    if lp not in {"crosstrade", "ninjatrader"}:
        broker["live_provider"] = "ninjatrader"
    config_manager.save_yaml_config(data)

    # Process env so runtime sees change without restart where EngineConfig re-reads.
    os.environ["BROKER_FALLBACK_ON_FABRIC_FAILURE"] = "true" if enabled else "false"

    _append_audit(
        workspace_root=workspace_root,
        event="set_market_data_fallback",
        source=source,
        previous=prev,
        enabled=bool(enabled),
    )
    logger.warning(
        "emergency_opt_in.market_data_fallback source=%s previous=%s enabled=%s",
        source,
        prev,
        enabled,
    )
    return read_emergency_opt_in(config_path=Path(config_manager.config_path))


def _append_audit(
    *,
    workspace_root: Path | None,
    event: str,
    source: str,
    previous: bool,
    enabled: bool,
) -> None:
    root = workspace_root or Path(os.getenv("LUMINA_WORKSPACE") or ".").resolve()
    path = root / _AUDIT_REL
    try:
        path.parent.mkdir(parents=True, exist_ok=True)
        line = (
            f'{{"ts":"{datetime.now(timezone.utc).isoformat()}","event":"{event}",'
            f'"source":"{source}","previous":{str(previous).lower()},'
            f'"enabled":{str(enabled).lower()}}}\n'
        )
        with path.open("a", encoding="utf-8") as fh:
            fh.write(line)
    except OSError:
        logger.warning("emergency_opt_in audit write failed", exc_info=True)

"""Always-on Fabric link supervisor — keep Brain session + heartbeats alive.

Process-level singleton: while Lumina backend lives, maintain an authenticated
TradingStream to NT Execution Fabric so SAFE_MODE clears and history/orders
share a live channel. Fail-closed capital path unchanged (no order bypass).
"""

from __future__ import annotations

import threading
import time
from dataclasses import dataclass
from typing import Any

from lumina_core.logging_utils import get_logger

logger = get_logger("lumina.fabric.link_supervisor")

_LOCK = threading.RLock()
_INSTANCE: "FabricLinkSupervisor | None" = None


@dataclass
class FabricLinkStatus:
    connected: bool = False
    target: str = ""
    session_id: str = ""
    account_name: str = ""
    last_error: str = ""
    last_error_code: str = ""
    reconnects: int = 0
    last_connect_ok_at: float = 0.0
    running: bool = False
    safe_mode: int = 0

    def to_dict(self) -> dict[str, Any]:
        return {
            "connected": self.connected,
            "target": self.target,
            "session_id": self.session_id,
            "account_name": self.account_name,
            "last_error": self.last_error,
            "last_error_code": self.last_error_code,
            "reconnects": self.reconnects,
            "last_connect_ok_at": self.last_connect_ok_at,
            "running": self.running,
            "safe_mode": self.safe_mode,
            "auth_ok": self.connected and bool(self.session_id),
        }


class FabricLinkSupervisor:
    """Background reconnect loop + shared FabricGrpcClient."""

    def __init__(self) -> None:
        self._client: Any | None = None
        self._config: Any | None = None
        self._stop = threading.Event()
        self._thread: threading.Thread | None = None
        self._status = FabricLinkStatus()
        self._gate = threading.RLock()
        self._enabled = False

    def configure_from_engine_config(self, engine_config: Any, *, mode_context: str = "sim") -> None:
        from lumina_core.broker.ninjatrader.fabric_client import FabricConfig

        self._config = FabricConfig.from_engine_config(engine_config, mode_context=mode_context)
        # Always-on heartbeats (never 0).
        if int(self._config.heartbeat_interval_ms or 0) <= 0:
            self._config.heartbeat_interval_ms = 1000
        with self._gate:
            self._status.target = self._config.target

    def start(self, *, engine_config: Any | None = None, mode_context: str = "sim") -> None:
        """Start supervisor loop if not already running (ninjatrader provider only)."""
        if engine_config is not None:
            provider = str(
                getattr(engine_config, "broker_live_provider", "") or ""
            ).strip().lower()
            # Yaml SSOT can correct poisoned EngineConfig (cwd/lru cache → crosstrade).
            if provider not in {"ninjatrader", "nt", "fabric"}:
                try:
                    from lumina_core.engine.engine_config_helpers import (
                        _config_yaml_nested,
                        clear_yaml_config_cache,
                    )

                    clear_yaml_config_cache()
                    yaml_lp = str(
                        _config_yaml_nested("", "broker", "live_provider") or ""
                    ).strip().lower()
                    if yaml_lp in {"ninjatrader", "nt", "fabric"}:
                        provider = yaml_lp
                        logger.warning(
                            "fabric.supervisor.provider_corrected_from_yaml engine=%s yaml=%s",
                            getattr(engine_config, "broker_live_provider", None),
                            yaml_lp,
                        )
                        try:
                            object.__setattr__(engine_config, "broker_live_provider", yaml_lp)
                        except Exception:
                            try:
                                engine_config.broker_live_provider = yaml_lp  # type: ignore[attr-defined]
                            except Exception:
                                pass
                except Exception:
                    pass
            if provider not in {"ninjatrader", "nt", "fabric"}:
                logger.info("fabric.supervisor.skip provider=%s", provider or "unset")
                return
            self.configure_from_engine_config(engine_config, mode_context=mode_context)

        with self._gate:
            if self._thread and self._thread.is_alive():
                self._enabled = True
                return
            self._enabled = True
            self._stop.clear()
            self._thread = threading.Thread(
                target=self._run_loop,
                name="fabric-link-supervisor",
                daemon=True,
            )
            self._thread.start()
            self._status.running = True
        logger.info("fabric.supervisor.started target=%s", getattr(self._config, "target", ""))

    def stop(self) -> None:
        self._enabled = False
        self._stop.set()
        with self._gate:
            client = self._client
            self._client = None
            self._status.connected = False
            self._status.running = False
        if client is not None:
            try:
                client.disconnect()
            except Exception:
                logger.debug("fabric.supervisor.disconnect_failed", exc_info=True)
        thr = self._thread
        if thr and thr.is_alive() and threading.current_thread() is not thr:
            thr.join(timeout=3.0)
        self._thread = None
        logger.info("fabric.supervisor.stopped")

    def status(self) -> FabricLinkStatus:
        with self._gate:
            st = FabricLinkStatus(
                connected=self._status.connected,
                target=self._status.target,
                session_id=self._status.session_id,
                account_name=self._status.account_name,
                last_error=self._status.last_error,
                last_error_code=self._status.last_error_code,
                reconnects=self._status.reconnects,
                last_connect_ok_at=self._status.last_connect_ok_at,
                running=self._status.running,
                safe_mode=self._status.safe_mode,
            )
            client = self._client
        if client is not None and getattr(client, "is_connected", False):
            st.connected = True
            st.session_id = str(getattr(client, "session_id", "") or st.session_id)
            st.account_name = str(getattr(client, "account_name", "") or st.account_name)
            try:
                st.safe_mode = int(getattr(client, "safe_mode", 0) or 0)
            except Exception:
                pass
        return st

    def get_client(self) -> Any | None:
        """Return live client only when authenticated."""
        with self._gate:
            client = self._client
        if client is not None and getattr(client, "is_connected", False):
            return client
        return None

    def ensure_connected(self, *, timeout_seconds: float = 15.0) -> bool:
        """Block until connected or timeout (also kicks the loop)."""
        if self.get_client() is not None:
            return True
        if not self._enabled or not (self._thread and self._thread.is_alive()):
            # One-shot connect without full loop if config present
            return self._try_connect_once()
        deadline = time.time() + max(1.0, float(timeout_seconds))
        while time.time() < deadline:
            if self.get_client() is not None:
                return True
            time.sleep(0.25)
        return self.get_client() is not None

    def _run_loop(self) -> None:
        backoff = 1.0
        nt_was_alive = False
        while not self._stop.is_set() and self._enabled:
            if self.get_client() is not None:
                backoff = 1.0
                nt_was_alive = True
                # Health poll — also detect half-open stream (is_connected false).
                with self._gate:
                    client = self._client
                if client is not None and not getattr(client, "is_connected", False):
                    self._mark_down("DISCONNECTED", "Fabric session dropped")
                elif not self._tcp_target_open():
                    # Host stop hung / port closed while Brain still holds a zombie session.
                    self._mark_down(
                        "CONNECTION_REFUSED",
                        "Fabric port closed — host not listening (reopen New → LUMINA)",
                    )
                else:
                    # Soft liveness: process gone while we still think connected.
                    if not self._nt_process_alive():
                        logger.error(
                            "CODE_RED fabric.supervisor.nt_died_while_session_open — "
                            "clearing client (not a Lumina taskkill)"
                        )
                        self._mark_down(
                            "NT_PROCESS_GONE",
                            "NinjaTrader.exe exited while Fabric session was open",
                        )
                        nt_was_alive = False
                self._stop.wait(2.0)
                continue

            if self._try_connect_once():
                backoff = 1.0
                nt_was_alive = True
                continue

            # Backoff reconnect — calm if NT process is gone (never taskkill; just wait).
            with self._gate:
                self._status.reconnects += 1
            nt_alive = self._nt_process_alive()
            # NT just came back after being down → reconnect immediately (avoid 30s lag + SAFE_MODE).
            if nt_alive and not nt_was_alive:
                backoff = 1.0
                logger.info(
                    "fabric.supervisor.nt_process_back — reset backoff, reconnect ASAP"
                )
            nt_was_alive = nt_alive

            if not nt_alive:
                wait = max(45.0, min(120.0, backoff * 2.0))
                logger.error(
                    "CODE_RED fabric.supervisor.nt_process_gone reconnects=%s code=%s — "
                    "NinjaTrader.exe not running (no Lumina taskkill). Waiting %.0fs before retry. "
                    "Operator: relaunch NT + New → LUMINA.",
                    self._status.reconnects,
                    self._status.last_error_code,
                    wait,
                )
                with self._gate:
                    self._status.last_error_code = "NT_PROCESS_GONE"
                    self._status.last_error = (
                        "NinjaTrader.exe is not running. Relaunch NT, open New → LUMINA. "
                        "Lumina does not auto-kill NT outside explicit Repair."
                    )
            else:
                # Host process up but gRPC not ready yet — short backoff, not 30s spam.
                wait = min(8.0, max(1.0, backoff))
                logger.warning(
                    "fabric.supervisor.reconnect_wait sec=%.1f code=%s err=%s nt_alive=%s",
                    wait,
                    self._status.last_error_code,
                    (self._status.last_error or "")[:120],
                    nt_alive,
                )
            self._stop.wait(wait)
            backoff = min(30.0, backoff * 2.0)

    @staticmethod
    def _nt_process_alive() -> bool:
        """Lightweight process probe (avoid importing lumina_launcher from core)."""
        import subprocess
        import sys

        if sys.platform != "win32":
            return True
        try:
            r = subprocess.run(
                ["tasklist", "/FI", "IMAGENAME eq NinjaTrader.exe", "/NH"],
                capture_output=True,
                text=True,
                timeout=5,
                check=False,
            )
            return "ninjatrader.exe" in (r.stdout or "").lower()
        except (OSError, subprocess.TimeoutExpired):
            return True  # fail-open: keep trying connect

    def _tcp_target_open(self) -> bool:
        """True when host:port from config accepts a TCP connect (fast fail for dead host)."""
        import socket

        cfg = self._config
        if cfg is None:
            return False
        host = str(getattr(cfg, "host", None) or "127.0.0.1")
        try:
            port = int(getattr(cfg, "port", None) or 50051)
        except (TypeError, ValueError):
            port = 50051
        try:
            with socket.create_connection((host, port), timeout=0.75):
                return True
        except OSError:
            return False

    def _refresh_token_from_ssot(self) -> None:
        """Reload token via Fabric Secret Bus before each connect attempt."""
        if self._config is None:
            return
        try:
            from lumina_core.broker.ninjatrader.fabric_secret import read as fabric_secret_read

            token = str(fabric_secret_read(heal=True).token or "").strip()
        except Exception:
            token = ""
        if token:
            try:
                object.__setattr__(self._config, "auth_token", token)
            except Exception:
                try:
                    self._config.auth_token = token  # type: ignore[attr-defined]
                except Exception:
                    pass

    def _try_connect_once(self) -> bool:
        if self._config is None:
            return False
        self._refresh_token_from_ssot()
        from lumina_core.broker.ninjatrader.fabric_client import FabricGrpcClient

        client = FabricGrpcClient(self._config)
        try:
            ok = client.connect()
        except Exception as exc:
            self._mark_down("ERROR", str(exc))
            try:
                client.disconnect()
            except Exception:
                pass
            return False

        if not ok:
            code = str(getattr(client, "last_connect_code", "") or "ERROR")
            err = str(getattr(client, "last_connect_error", "") or "connect failed")
            self._mark_down(code, err)
            try:
                client.disconnect()
            except Exception:
                pass
            # Invalidate paper GREEN on auth failure
            if code in {"AUTH_FAILED", "AUTH_TIMEOUT", "TOKEN_EMPTY"}:
                try:
                    from lumina_launcher.services.fabric_link_certificate import (
                        invalidate_certificate,
                    )

                    invalidate_certificate(reason=f"supervisor_{code.lower()}")
                except Exception:
                    pass
            return False

        with self._gate:
            old = self._client
            self._client = client
            self._status.connected = True
            self._status.session_id = str(getattr(client, "session_id", None) or "")
            self._status.account_name = str(getattr(client, "account_name", None) or "")
            self._status.last_error = ""
            self._status.last_error_code = "OK"
            self._status.last_connect_ok_at = time.time()
            self._status.target = self._config.target
        if old is not None and old is not client:
            try:
                old.disconnect()
            except Exception:
                pass
        logger.info(
            "fabric.supervisor.connected session=%s account=%s target=%s",
            self._status.session_id,
            self._status.account_name,
            self._status.target,
        )
        return True

    def _mark_down(self, code: str, message: str) -> None:
        with self._gate:
            self._status.connected = False
            self._status.last_error_code = code
            self._status.last_error = message
            client = self._client
            self._client = None
        if client is not None:
            try:
                client.disconnect()
            except Exception:
                pass


def get_fabric_link_supervisor() -> FabricLinkSupervisor:
    global _INSTANCE
    with _LOCK:
        if _INSTANCE is None:
            _INSTANCE = FabricLinkSupervisor()
        return _INSTANCE


def ensure_fabric_link_supervisor(engine_config: Any, *, mode_context: str = "sim") -> FabricLinkSupervisor:
    """Start process-level supervisor when live_provider=ninjatrader.

    Set ``LUMINA_FABRIC_SUPERVISOR=0`` for headless cache-reuse Birth (no NT host).
    Default remains always-on keep-alive. This does not arm REAL orders.
    """
    import os

    flag = str(os.getenv("LUMINA_FABRIC_SUPERVISOR", "1") or "1").strip().lower()
    if flag in {"0", "false", "off", "no"}:
        logger.info("fabric.supervisor.disabled_by_env")
        return get_fabric_link_supervisor()
    sup = get_fabric_link_supervisor()
    sup.start(engine_config=engine_config, mode_context=mode_context)
    return sup

"""Centralized runtime config hot-reload (config.yaml + birth_v2)."""

from __future__ import annotations

import atexit
import logging
import os
import threading
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, TYPE_CHECKING

from lumina_core.agent_orchestration.schemas import (
    RuntimeConfigReloadFailed,
    RuntimeConfigReloaded,
    RuntimeConfigReloadRequested,
)
from lumina_core.config.atomic_yaml import resolve_config_path
from lumina_core.config_loader import ConfigLoader

if TYPE_CHECKING:
    from lumina_core.container import ApplicationContainer

logger = logging.getLogger("lumina.runtime_config_reloader")

_VALID_MODES = frozenset({"paper", "sim", "sim_real_guard", "real"})
_VALID_BROKERS = frozenset({"paper", "live"})


@dataclass(slots=True)
class RuntimeConfigReloadResult:
    applied: bool
    rejected_reason: str | None = None
    changed_sections: list[str] = field(default_factory=list)
    validation_errors: list[str] = field(default_factory=list)
    immutable_fields: list[str] = field(default_factory=list)


def _normalize_mode(value: Any) -> str:
    text = str(value or "").strip().lower()
    aliases = {
        "paper": "paper",
        "sim": "sim",
        "simulation": "sim",
        "sim_real_guard": "sim_real_guard",
        "real": "real",
        "live": "real",
    }
    return aliases.get(text, text)


def _normalize_broker(value: Any) -> str:
    text = str(value or "").strip().lower()
    return text if text in _VALID_BROKERS else ""


def _normalize_symbols(values: Any) -> list[str]:
    if not isinstance(values, list):
        return []
    return sorted(str(item).strip().upper() for item in values if str(item).strip())


def _immutable_field_changes(cfg: dict[str, Any], live: Any) -> list[str]:
    """Return immutable fields that differ between incoming YAML and live runtime."""
    changed: list[str] = []
    broker_section = cfg.get("broker") if isinstance(cfg.get("broker"), dict) else {}

    if "mode" in cfg or "trade_mode" in cfg:
        incoming_mode = _normalize_mode(cfg.get("trade_mode") or cfg.get("mode"))
        live_mode = _normalize_mode(getattr(live, "trade_mode", ""))
        if incoming_mode and incoming_mode in _VALID_MODES and incoming_mode != live_mode:
            changed.append("trade_mode")

    if "broker_backend" in cfg or (isinstance(broker_section, dict) and "backend" in broker_section):
        incoming_broker = _normalize_broker(cfg.get("broker_backend") or broker_section.get("backend"))
        live_broker = _normalize_broker(getattr(live, "broker_backend", ""))
        if incoming_broker and incoming_broker != live_broker:
            changed.append("broker_backend")

    if "instrument" in cfg:
        incoming_inst = str(cfg.get("instrument") or "").strip().upper()
        live_inst = str(getattr(live, "instrument", "") or "").strip().upper()
        if incoming_inst and incoming_inst != live_inst:
            changed.append("instrument")

    if "swarm_symbols" in cfg:
        incoming_swarm = _normalize_symbols(cfg.get("swarm_symbols"))
        live_swarm = _normalize_symbols(getattr(live, "swarm_symbols", []))
        if incoming_swarm and incoming_swarm != live_swarm:
            changed.append("swarm_symbols")

    return changed


def _changed_top_level_sections(old_cfg: dict[str, Any], new_cfg: dict[str, Any]) -> list[str]:
    keys = set(old_cfg) | set(new_cfg)
    return sorted(key for key in keys if old_cfg.get(key) != new_cfg.get(key))


def _hot_reload_enabled(cfg: dict[str, Any]) -> bool:
    env_raw = os.getenv("LUMINA_CONFIG_HOT_RELOAD", "").strip().lower()
    if env_raw in {"0", "false", "no", "off"}:
        return False
    if env_raw in {"1", "true", "yes", "on"}:
        return True
    section = cfg.get("runtime_config")
    if isinstance(section, dict):
        hot = section.get("hot_reload")
        if isinstance(hot, dict) and "enabled" in hot:
            return bool(hot.get("enabled"))
    return True


def _debounce_ms(cfg: dict[str, Any]) -> int:
    env_raw = os.getenv("LUMINA_CONFIG_RELOAD_DEBOUNCE_MS", "").strip()
    if env_raw.isdigit():
        return max(50, int(env_raw))
    section = cfg.get("runtime_config")
    if isinstance(section, dict):
        hot = section.get("hot_reload")
        if isinstance(hot, dict):
            try:
                return max(50, int(hot.get("debounce_ms", 500)))
            except (TypeError, ValueError):
                pass
    return 500


class RuntimeConfigReloader:
    """Watch config.yaml and apply validated hot-reloads fail-closed."""

    def __init__(self, container: ApplicationContainer) -> None:
        self._container = container
        self._config_path = resolve_config_path().resolve()
        self._lock = threading.RLock()
        self._debounce_timer: threading.Timer | None = None
        self._observer: Any | None = None
        self._poll_thread: threading.Thread | None = None
        self._stop_event = threading.Event()
        self._bus_token: str | None = None
        self._last_mtime: float = 0.0
        self._started = False

    @property
    def config_path(self) -> Path:
        return self._config_path

    def start(self) -> None:
        with self._lock:
            if self._started:
                return
            cfg = ConfigLoader.get()
            if not _hot_reload_enabled(cfg):
                logger.info("runtime_config.hot_reload disabled path=%s", self._config_path)
                return

            self._last_mtime = self._config_path.stat().st_mtime if self._config_path.is_file() else 0.0
            self._subscribe_bus()
            if self._start_watchdog():
                logger.info("runtime_config.hot_reload watchdog active path=%s", self._config_path)
            else:
                self._start_poll_fallback()
                logger.info("runtime_config.hot_reload poll fallback active path=%s", self._config_path)
            atexit.register(self.stop)
            self._started = True

    def stop(self) -> None:
        with self._lock:
            if not self._started:
                return
            self._stop_event.set()
            if self._debounce_timer is not None:
                self._debounce_timer.cancel()
                self._debounce_timer = None
            if self._observer is not None:
                try:
                    self._observer.stop()
                    self._observer.join(timeout=2.0)
                except Exception:
                    logger.exception("runtime_config.watchdog_stop_failed")
                self._observer = None
            if self._bus_token is not None:
                try:
                    self._container.event_bus.unsubscribe(self._bus_token)
                except Exception:
                    logger.exception("runtime_config.bus_unsubscribe_failed")
                self._bus_token = None
            self._started = False

    def schedule_reload(self, *, source: str = "watcher") -> None:
        with self._lock:
            if self._debounce_timer is not None:
                self._debounce_timer.cancel()
            debounce_ms = _debounce_ms(ConfigLoader.get())
            self._debounce_timer = threading.Timer(
                debounce_ms / 1000.0,
                lambda: self._run_reload(source=source),
            )
            self._debounce_timer.daemon = True
            self._debounce_timer.start()

    def reload_now(self, *, source: str = "manual") -> RuntimeConfigReloadResult:
        return self._run_reload(source=source)

    def _subscribe_bus(self) -> None:
        def _on_requested(event: Any) -> None:
            _ = event
            self.schedule_reload(source="event_bus")

        self._bus_token = self._container.event_bus.subscribe(
            "runtime.config.reload_requested",
            _on_requested,
        )

    def _start_watchdog(self) -> bool:
        try:
            from lumina_core.io.watchdog_import import load_watchdog_modules

            handler_cls, observer_cls = load_watchdog_modules()
        except Exception as exc:
            logger.warning("runtime_config.watchdog_unavailable detail=%s", exc)
            return False

        reloader = self

        class _Handler(handler_cls):
            def on_modified(self, event: Any) -> None:
                if getattr(event, "is_directory", False):
                    return
                try:
                    changed = Path(str(getattr(event, "src_path", ""))).resolve()
                except Exception:
                    return
                if changed != reloader._config_path:
                    return
                reloader.schedule_reload(source="watchdog")

            def on_created(self, event: Any) -> None:
                self.on_modified(event)

        try:
            observer = observer_cls()
            observer.schedule(_Handler(), str(self._config_path.parent), recursive=False)
            observer.daemon = True
            observer.start()
            self._observer = observer
            return True
        except Exception:
            logger.exception("runtime_config.watchdog_start_failed")
            return False

    def _start_poll_fallback(self) -> None:
        if self._poll_thread is not None and self._poll_thread.is_alive():
            return

        def _poll_loop() -> None:
            while not self._stop_event.wait(30.0):
                try:
                    if not self._config_path.is_file():
                        continue
                    mtime = self._config_path.stat().st_mtime
                    if mtime > self._last_mtime:
                        self.schedule_reload(source="poll")
                except Exception:
                    logger.exception("runtime_config.poll_failed")

        self._poll_thread = threading.Thread(target=_poll_loop, name="config-reload-poll", daemon=True)
        self._poll_thread.start()

    def _run_reload(self, *, source: str) -> RuntimeConfigReloadResult:
        with self._lock:
            result = self._container.apply_config_reload(config_path=self._config_path, source=source)
            if self._config_path.is_file():
                self._last_mtime = self._config_path.stat().st_mtime
            self._publish_result(result)
            return result

    def _publish_result(self, result: RuntimeConfigReloadResult) -> None:
        ts = datetime.now(timezone.utc).isoformat()
        bus = self._container.event_bus
        path_str = str(self._config_path)
        if result.applied:
            bus.publish(
                topic="runtime.config.reloaded",
                producer="runtime_config_reloader",
                payload={
                    "config_path": path_str,
                    "changed_sections": list(result.changed_sections),
                    "timestamp": ts,
                },
                payload_model=RuntimeConfigReloaded,
            )
            return
        bus.publish(
            topic="runtime.config.reload_failed",
            producer="runtime_config_reloader",
            payload={
                "config_path": path_str,
                "reason": str(result.rejected_reason or "unknown"),
                "validation_errors": list(result.validation_errors),
                "immutable_fields": list(result.immutable_fields),
                "timestamp": ts,
            },
            payload_model=RuntimeConfigReloadFailed,
        )


def request_config_reload(container: ApplicationContainer, *, source: str = "manual") -> None:
    """Publish an in-process reload request on the central EventBus."""
    container.event_bus.publish(
        topic="runtime.config.reload_requested",
        producer=source,
        payload={"source": source, "timestamp": datetime.now(timezone.utc).isoformat()},
        payload_model=RuntimeConfigReloadRequested,
    )


def reload_config_from_disk(
    container: ApplicationContainer,
    *,
    config_path: Path | None = None,
    source: str = "manual",
) -> RuntimeConfigReloadResult:
    """Validate and apply config from disk (no watcher required)."""
    path = (config_path or resolve_config_path()).resolve()
    return container.apply_config_reload(config_path=path, source=source)


__all__ = [
    "RuntimeConfigReloadResult",
    "RuntimeConfigReloader",
    "reload_config_from_disk",
    "request_config_reload",
]

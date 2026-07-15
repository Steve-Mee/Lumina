"""Config hot-reload and birth-engine sync helpers for ApplicationContainer."""

from __future__ import annotations

import logging
import os
from pathlib import Path
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from lumina_core.container import ApplicationContainer


class ConfigHotReloadSupport:
    """Mixin: config.yaml hot-reload and birth_v2 host registration."""

    _config_reloader: Any
    _birth_reload_host: Any
    config: Any
    config_service: Any
    engine: Any
    logger: logging.Logger

    def register_birth_reload_host(self, host: Any) -> None:
        """Register active LuminaBirthEngine for birth_v2 hot-reload sync."""
        self._birth_reload_host = host

    def clear_birth_reload_host(self, host: Any | None = None) -> None:
        if host is None or self._birth_reload_host is host:
            self._birth_reload_host = None

    def apply_config_reload(
        self,
        *,
        config_path: Path | None = None,
        source: str = "manual",
    ) -> Any:
        """Validate and apply config.yaml hot-reload (fail-closed on immutable fields)."""
        from lumina_core.config.atomic_yaml import read_yaml_stable, resolve_config_path
        from lumina_core.config_loader import ConfigLoader
        from lumina_core.runtime_config_reloader import (
            RuntimeConfigReloadResult,
            _changed_top_level_sections,
            _immutable_field_changes,
        )

        path = (config_path or resolve_config_path()).resolve()
        prior_cfg = ConfigLoader.get()
        parsed = read_yaml_stable(path)
        if not parsed:
            reason = "config_empty_or_unreadable"
            self.logger.warning("CONFIG_RELOAD_FAILED,source=%s,reason=%s,path=%s", source, reason, path)
            return RuntimeConfigReloadResult(applied=False, rejected_reason=reason)

        try:
            ConfigLoader.validate_dict(parsed, raise_on_error=True)
        except RuntimeError as exc:
            errors = [str(exc)]
            self.logger.warning(
                "CONFIG_RELOAD_FAILED,source=%s,reason=validation,path=%s,detail=%s",
                source,
                path,
                exc,
            )
            return RuntimeConfigReloadResult(
                applied=False,
                rejected_reason="validation_failed",
                validation_errors=errors,
            )

        immutable = _immutable_field_changes(parsed, self.config)
        if immutable:
            self.logger.warning(
                "CONFIG_RELOAD_IMMUTABLE_REJECTED,source=%s,fields=%s,path=%s",
                source,
                ",".join(immutable),
                path,
            )
            return RuntimeConfigReloadResult(
                applied=False,
                rejected_reason="immutable_fields_changed",
                immutable_fields=immutable,
            )

        changed_sections = _changed_top_level_sections(prior_cfg, parsed)

        # Fail-closed twin oversight: block auto_approve_real and unsafe twin threshold decreases.
        try:
            from lumina_core.runtime.runtime_twin_oversight import RuntimeTwinOversight

            live_mode = str(getattr(self.config, "trade_mode", "") or "sim")
            verdict = RuntimeTwinOversight.get().audit_config_reload(
                changed_sections,
                parsed,
                mode=live_mode,
            )
            if not verdict.allowed:
                blocked = list(verdict.blocked_fields or [])
                self.logger.warning(
                    "CONFIG_RELOAD_TWIN_REJECTED,source=%s,reason=%s,fields=%s,path=%s",
                    source,
                    verdict.reason,
                    ",".join(blocked),
                    path,
                )
                try:
                    RuntimeTwinOversight.get().record_runtime_event(
                        "config_reload_blocked",
                        {"reason": verdict.reason, "blocked_fields": blocked, "source": source},
                    )
                except Exception:
                    pass
                return RuntimeConfigReloadResult(
                    applied=False,
                    rejected_reason=str(verdict.reason or "twin_oversight_blocked"),
                    immutable_fields=blocked,
                )
        except Exception as exc:
            # Fail-closed on audit infrastructure errors for real-ish modes only.
            live_mode = str(getattr(self.config, "trade_mode", "") or "sim").strip().lower()
            if live_mode in {"real", "live", "sim_real_guard"}:
                self.logger.warning(
                    "CONFIG_RELOAD_TWIN_AUDIT_FAILED,source=%s,detail=%s,path=%s",
                    source,
                    exc,
                    path,
                )
                return RuntimeConfigReloadResult(
                    applied=False,
                    rejected_reason=f"twin_audit_error:{type(exc).__name__}",
                )
            self.logger.debug("CONFIG_RELOAD_TWIN_AUDIT_SKIPPED detail=%s", exc, exc_info=True)

        ConfigLoader.invalidate()
        new_config = self.config_service.load()
        self.config = new_config
        self.engine.config = new_config

        log_level = str(
            ConfigLoader.section("logging", "level", default=os.getenv("LUMINA_LOG_LEVEL", "INFO"))
        ).upper()
        self.logger.setLevel(getattr(logging, log_level, logging.INFO))

        birth_host = self._birth_reload_host
        if birth_host is not None and hasattr(birth_host, "reload_birth_config"):
            try:
                birth_host.reload_birth_config()
                if "birth_v2" not in changed_sections:
                    changed_sections.append("birth_v2")
            except Exception as exc:
                self.logger.warning("CONFIG_RELOAD_BIRTH_SYNC_FAILED detail=%s", exc)

        self.logger.info(
            "CONFIG_RELOAD_OK,source=%s,path=%s,sections=%s",
            source,
            path,
            ",".join(changed_sections) or "none",
        )
        return RuntimeConfigReloadResult(applied=True, changed_sections=changed_sections)

    def start_config_hot_reload(self) -> None:
        """Start file watcher / poll loop for config.yaml hot-reload."""
        if self._config_reloader is not None:
            return
        from lumina_core.runtime_config_reloader import RuntimeConfigReloader

        self._config_reloader = RuntimeConfigReloader(self)
        self._config_reloader.start()

    def stop_config_hot_reload(self) -> None:
        if self._config_reloader is None:
            return
        self._config_reloader.stop()
        self._config_reloader = None


def wire_config_hot_reload(container: ApplicationContainer) -> None:
    """No-op placeholder for bounded-module symmetry (logic lives on mixin)."""
    _ = container

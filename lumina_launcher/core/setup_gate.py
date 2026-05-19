"""SSOT for launcher setup phase detection (Smart Setup + Guided Setup)."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import TYPE_CHECKING, Any

from lumina_core.engine.setup_service import SetupService
from lumina_launcher.core.setup_config import SetupConfig
from lumina_launcher.core.workspace_root import resolve_birth_workspace_root

if TYPE_CHECKING:
    from lumina_launcher.services.smart_setup_service import SmartSetupService


def _smart_setup_service_cls():
    from lumina_launcher.services.smart_setup_service import SmartSetupService

    return SmartSetupService


@dataclass(frozen=True, slots=True)
class LauncherSetupState:
    setup_complete: bool
    intelligence_stack_ready: bool
    needs_smart_setup: bool
    needs_guided_setup: bool
    launcher_ready: bool

    def to_dict(self) -> dict[str, bool]:
        return {
            "setup_complete": self.setup_complete,
            "intelligence_stack_ready": self.intelligence_stack_ready,
            "needs_smart_setup": self.needs_smart_setup,
            "needs_guided_setup": self.needs_guided_setup,
            "launcher_ready": self.launcher_ready,
        }


def resolve_launcher_setup_state(
    workspace_root: Path | str | None = None,
    *,
    setup_service: SetupService | None = None,
    smart_setup_service: SmartSetupService | None = None,
) -> LauncherSetupState:
    root = resolve_birth_workspace_root(workspace_root)
    setup = setup_service or SetupService(
        workspace_root=root,
        config_path=root / "config.yaml",
        env_path=root / ".env",
    )
    smart = smart_setup_service or _smart_setup_service_cls()(root, setup_service=setup)
    setup_cfg = SetupConfig.from_workspace(root)
    setup_complete = setup.is_setup_complete()
    intelligence_stack_ready = smart.is_intelligence_stack_ready()
    if setup_cfg.skips_smart_setup_wizard():
        needs_smart_setup = False
        needs_guided_setup = not setup_complete
    else:
        needs_smart_setup = not setup_complete and not intelligence_stack_ready
        needs_guided_setup = not setup_complete and intelligence_stack_ready
    return LauncherSetupState(
        setup_complete=setup_complete,
        intelligence_stack_ready=intelligence_stack_ready,
        needs_smart_setup=needs_smart_setup,
        needs_guided_setup=needs_guided_setup,
        launcher_ready=setup_complete,
    )


def launcher_setup_status_payload(
    workspace_root: Path | str | None = None,
    *,
    setup_service: SetupService | None = None,
    smart_setup_service: SmartSetupService | None = None,
) -> dict[str, Any]:
    """Gate flags plus compact model/provider fields for status APIs."""
    root = resolve_birth_workspace_root(workspace_root)
    setup = setup_service or SetupService(
        workspace_root=root,
        config_path=root / "config.yaml",
        env_path=root / ".env",
    )
    smart = smart_setup_service or _smart_setup_service_cls()(root, setup_service=setup)
    setup_cfg = SetupConfig.from_workspace(root)
    gate = resolve_launcher_setup_state(root, setup_service=setup, smart_setup_service=smart)
    detail = smart.get_setup_status()
    return {
        **gate.to_dict(),
        **setup_cfg.to_dict(),
        "setup_mode": setup_cfg.mode,
        "recommended_model": str(detail.get("recommended_model_key", "")),
        "recommended_provider": str(detail.get("recommended_provider", "")),
        "recommended_ollama_tag": str(detail.get("recommended_ollama_tag", "")),
        "missing": list(detail.get("missing", [])),
    }

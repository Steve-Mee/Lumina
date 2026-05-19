"""
Smart setup orchestration for the Lumina launcher.

Delegates pip/config work to lumina_core.engine.setup_service.SetupService.
Ollama install/pull uses local subprocess helpers with progress and graceful degradation.
"""

from __future__ import annotations

import platform
import shutil
import subprocess
import sys
from collections.abc import Callable
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Literal

import yaml

from lumina_core.adaptive_intelligence import AdaptiveIntelligenceManager, AdaptiveIntelligenceStatus
from lumina_core.config_loader import ConfigLoader
from lumina_core.engine.hardware_inspector import HardwareInspector, HardwareSnapshot
from lumina_core.engine.model_catalog import ModelCatalog, ModelDescriptor
from lumina_core.engine.ollama_model_resolve import resolve_ollama_model_tag
from lumina_core.engine.setup_service import SetupService
from lumina_core.logging_utils import get_logger
from lumina_launcher.services.workspace_root import resolve_birth_workspace_root

logger = get_logger(__name__)

SetupProgressCallback = Callable[["SetupProgressEvent"], None]
ProgressLevel = Literal["info", "warning", "error"]

_OLLAMA_INSTALL_TIMEOUT_SEC = 1800
_OLLAMA_PULL_TIMEOUT_SEC = 7200
_OUTPUT_TAIL_CHARS = 1200

_PROGRESS_PERCENT: dict[str, int] = {
    "detect": 5,
    "launcher_deps": 20,
    "runtime_deps": 40,
    "ollama": 55,
    "ollama_verify": 58,
    "model_pull": 70,
    "model_pull_progress": 70,
    "extra_models": 75,
    "skipped_vllm_provider": 70,
    "config": 85,
    "complete": 100,
    "failed": 100,
}


@dataclass(slots=True)
class SetupProgressEvent:
    phase: str
    message: str
    percent: int | None = None
    level: ProgressLevel = "info"
    detail: dict[str, Any] = field(default_factory=dict)


@dataclass(slots=True)
class SmartSetupOptions:
    install_ollama: bool = True
    download_recommended_model: bool = True
    force_high_tier: bool = False
    pull_extra_models: bool = False
    graceful_degrade: bool = True


@dataclass(slots=True)
class SubprocessStepResult:
    name: str
    success: bool
    message: str
    command: str = ""

    def to_dict(self) -> dict[str, Any]:
        return {
            "name": self.name,
            "success": self.success,
            "message": self.message,
            "command": self.command,
        }


@dataclass(slots=True)
class SmartSetupResult:
    success: bool
    steps: list[dict[str, Any]]
    status: dict[str, Any]
    degraded: bool = False
    warnings: list[str] = field(default_factory=list)
    manual_steps: list[dict[str, Any]] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return {
            "success": self.success,
            "steps": self.steps,
            "status": self.status,
            "degraded": self.degraded,
            "warnings": list(self.warnings),
            "manual_steps": list(self.manual_steps),
        }


class SmartSetupService:
    """Orchestrates first-run detection, intelligence-aware setup, and guided install."""

    def __init__(
        self,
        workspace_root: Path | str | None = None,
        *,
        setup_service: SetupService | None = None,
        intelligence_manager: AdaptiveIntelligenceManager | None = None,
    ) -> None:
        self.workspace_root = resolve_birth_workspace_root(workspace_root)
        self._setup_service = setup_service or SetupService(
            workspace_root=self.workspace_root,
            config_path=self.workspace_root / "config.yaml",
            env_path=self.workspace_root / ".env",
        )
        self._intelligence_manager = intelligence_manager or AdaptiveIntelligenceManager(
            self.workspace_root
        )
        self._setup_config = None

    @property
    def setup_config(self):
        if self._setup_config is None:
            from lumina_launcher.core.setup_config import SetupConfig

            self._setup_config = SetupConfig.from_workspace(self.workspace_root)
        return self._setup_config

    def default_options(self) -> SmartSetupOptions:
        return self.setup_config.to_smart_setup_options()

    def is_first_time(self) -> bool:
        first_time = not self._setup_service.is_setup_complete()
        logger.debug("smart_setup.first_time complete=%s", not first_time)
        return first_time

    def is_intelligence_stack_ready(self) -> bool:
        status = self.get_setup_status()
        stack_missing = [item for item in status.get("missing", []) if item != "setup_complete"]
        if not stack_missing:
            return True
        loaded = self._setup_service.load_status()
        return bool(loaded.get("smart_setup")) and not stack_missing

    def get_setup_status(self) -> dict[str, Any]:
        intelligence_status = self._intelligence_manager.refresh(refresh_hardware=False)
        intelligence = intelligence_status.to_dict()
        hardware = self._intelligence_manager.hardware_manager.latest().to_dict()
        descriptor = self._resolve_descriptor(intelligence_status, hardware)
        provider = str(intelligence.get("recommended_provider", "ollama") or "ollama")
        ollama_required = provider == "ollama"
        ollama_installed = self._ollama_on_path()
        model_present = self._ollama_model_installed(descriptor.ollama_tag) if ollama_required else True
        setup_complete = self._setup_service.is_setup_complete()
        missing = self._collect_missing(
            setup_complete=setup_complete,
            ollama_required=ollama_required,
            ollama_installed=ollama_installed,
            model_present=model_present,
            ollama_tag=descriptor.ollama_tag,
        )
        stack_missing = [item for item in missing if item != "setup_complete"]
        intelligence_stack_ready = not stack_missing
        ready = setup_complete and intelligence_stack_ready
        return {
            "first_time": not setup_complete,
            "setup_complete": setup_complete,
            "intelligence_stack_ready": intelligence_stack_ready,
            "ready": ready,
            "ollama_installed": ollama_installed,
            "ollama_required": ollama_required,
            "recommended_model_key": descriptor.key,
            "recommended_ollama_tag": descriptor.ollama_tag,
            "recommended_model_present": model_present,
            "recommended_provider": provider,
            "adaptive_intelligence": intelligence,
            "hardware": hardware,
            "missing": missing,
        }

    def get_install_instructions(self) -> dict[str, Any]:
        status = self.get_setup_status()
        intelligence = status.get("adaptive_intelligence", {})
        tier = str(intelligence.get("tier", "light"))
        model_key = str(status.get("recommended_model_key", ""))
        ollama_tag = str(status.get("recommended_ollama_tag", ""))
        provider = str(status.get("recommended_provider", "ollama"))
        missing = list(status.get("missing", []))
        steps: list[dict[str, Any]] = []

        if not status.get("setup_complete"):
            steps.append(
                {
                    "id": "guided_setup",
                    "title": "Voer Smart Setup uit in de launcher",
                    "command": "",
                    "manual": "Gebruik run_smart_setup() of de setup-wizard om alle stappen automatisch uit te voeren.",
                    "required": True,
                }
            )

        steps.append(
            {
                "id": "launcher_deps",
                "title": "Launcher dependencies (Streamlit, requests, ollama package)",
                "command": f"{sys.executable} -m pip install streamlit pandas requests pyyaml psutil ollama",
                "manual": "Alleen nodig als automatische installatie faalt.",
                "required": False,
            }
        )
        steps.append(
            {
                "id": "runtime_deps",
                "title": "Runtime dependencies",
                "command": f"{sys.executable} -m pip install -r requirements.txt",
                "manual": f"Voer uit vanuit: {self.workspace_root}",
                "required": False,
            }
        )

        if provider == "ollama":
            if "ollama" in missing or not status.get("ollama_installed"):
                steps.extend(self._ollama_install_instruction_steps())
            if ollama_tag and (f"model:{ollama_tag}" in missing or not status.get("recommended_model_present")):
                steps.append(
                    {
                        "id": "model_pull",
                        "title": f"Download aanbevolen model ({ollama_tag})",
                        "command": f"ollama pull {ollama_tag}",
                        "manual": f"Start Ollama en pull het model voor tier {tier}: {model_key}.",
                        "required": True,
                    }
                )
        else:
            steps.append(
                {
                    "id": "vllm_requirements",
                    "title": "vLLM high-tier setup (geen Ollama-pull)",
                    "command": "",
                    "manual": (
                        f"Tier {tier} gebruikt provider vllm. Zorg voor Linux/WSL2, NVIDIA GPU met voldoende VRAM, "
                        "en configureer vLLM volgens docs/launcher-setup-and-model-management.md."
                    ),
                    "required": True,
                }
            )

        if missing:
            summary = (
                f"LUMINA tier {tier}: model {model_key} ({provider}). "
                f"Ontbreekt nog: {', '.join(missing)}."
            )
        else:
            summary = f"LUMINA tier {tier}: setup gereed voor {model_key} via {provider}."

        return {
            "summary": summary,
            "steps": steps,
            "status": status,
        }

    def run_smart_setup(
        self,
        *,
        on_progress: SetupProgressCallback | None = None,
        options: SmartSetupOptions | None = None,
        mark_complete: bool = False,
    ) -> SmartSetupResult:
        steps: list[dict[str, Any]] = []
        warnings: list[str] = []
        manual_steps: list[dict[str, Any]] = []
        degraded = False
        opts = options if options is not None else self.default_options()
        self._apply_intelligence_mode(opts.force_high_tier)

        intelligence_status = self._intelligence_manager.refresh(refresh_hardware=True)
        intelligence = intelligence_status.to_dict()
        hardware_intel = self._intelligence_manager.hardware_manager.latest()
        descriptor = self._resolve_descriptor(intelligence_status, hardware_intel.to_dict())
        provider = str(intelligence.get("recommended_provider", "ollama") or "ollama")
        ollama_required = provider == "ollama"

        self._emit_progress(
            on_progress,
            phase="detect",
            message=(
                f"Hardware gedetecteerd: tier {intelligence.get('tier')} — "
                f"aanbevolen model {descriptor.display_name} ({provider})"
            ),
            detail={"adaptive_intelligence": intelligence, "hardware": hardware_intel.to_dict()},
        )

        for phase, runner in (
            ("launcher_deps", self._setup_service.install_launcher_dependencies),
            ("runtime_deps", self._setup_service.install_runtime_dependencies),
        ):
            result = runner()
            steps.append(result.to_dict())
            self._emit_progress(
                on_progress,
                phase=phase,
                message=result.message,
                level="error" if not result.success else "info",
                detail={"success": result.success, "command": result.command},
            )
            logger.info("smart_setup.step name=%s success=%s", result.name, result.success)
            if not result.success:
                return self._finalize_run(
                    success=False,
                    steps=steps,
                    intelligence=intelligence,
                    on_progress=on_progress,
                    failure_message=result.message,
                    warnings=warnings,
                    manual_steps=manual_steps,
                    degraded=degraded,
                )

        if ollama_required:
            if opts.install_ollama:
                ollama_result, ollama_manual = self._install_ollama_subprocess()
                steps.append(ollama_result.to_dict())
                manual_steps.extend(ollama_manual)
                self._emit_progress(
                    on_progress,
                    phase="ollama",
                    message=ollama_result.message,
                    level="error" if not ollama_result.success else "info",
                    detail={"success": ollama_result.success, "command": ollama_result.command},
                )
                logger.info("smart_setup.step name=%s success=%s", ollama_result.name, ollama_result.success)
                if not ollama_result.success:
                    warning = ollama_result.message
                    warnings.append(warning)
                    degraded = True
                    if not opts.graceful_degrade:
                        return self._finalize_run(
                            success=False,
                            steps=steps,
                            intelligence=intelligence,
                            on_progress=on_progress,
                            failure_message=warning,
                            warnings=warnings,
                            manual_steps=manual_steps,
                            degraded=degraded,
                        )
            else:
                skip_ollama = "Ollama-installatie overgeslagen (optie uitgeschakeld)."
                steps.append(
                    {"name": "ollama_skipped", "success": True, "message": skip_ollama, "command": ""}
                )
                self._emit_progress(on_progress, phase="ollama", message=skip_ollama, detail={})

            verify_result = self._verify_ollama_runtime()
            steps.append(verify_result.to_dict())
            self._emit_progress(
                on_progress,
                phase="ollama_verify",
                message=verify_result.message,
                level="warning" if not verify_result.success else "info",
                detail={"success": verify_result.success},
            )
            if not verify_result.success:
                warnings.append(verify_result.message)
                degraded = True
                if not opts.graceful_degrade:
                    return self._finalize_run(
                        success=False,
                        steps=steps,
                        intelligence=intelligence,
                        on_progress=on_progress,
                        failure_message=verify_result.message,
                        warnings=warnings,
                        manual_steps=manual_steps,
                        degraded=degraded,
                    )

            if opts.download_recommended_model:
                pull_result = self._pull_model_subprocess(descriptor, on_progress=on_progress)
                steps.append(pull_result.to_dict())
                self._emit_progress(
                    on_progress,
                    phase="model_pull",
                    message=pull_result.message,
                    level="error" if not pull_result.success else "info",
                    detail={"success": pull_result.success, "command": pull_result.command},
                )
                logger.info("smart_setup.step name=%s success=%s", pull_result.name, pull_result.success)
                if not pull_result.success:
                    warnings.append(pull_result.message)
                    degraded = True
                    manual_steps.extend(self._manual_steps_for_model(descriptor.ollama_tag))
                    if not opts.graceful_degrade:
                        return self._finalize_run(
                            success=False,
                            steps=steps,
                            intelligence=intelligence,
                            on_progress=on_progress,
                            failure_message=pull_result.message,
                            warnings=warnings,
                            manual_steps=manual_steps,
                            degraded=degraded,
                        )
            else:
                skip_model = "Model-download overgeslagen (optie uitgeschakeld)."
                steps.append(
                    {"name": "model_pull_skipped", "success": True, "message": skip_model, "command": ""}
                )
                self._emit_progress(on_progress, phase="model_pull", message=skip_model, detail={})

            if opts.pull_extra_models:
                catalog = self._intelligence_manager.hardware_manager.catalog
                for extra in catalog.upgrade_targets(descriptor.key):
                    if extra.recommended_provider != "ollama":
                        continue
                    extra_result = self._pull_model_subprocess(extra, on_progress=on_progress)
                    steps.append(extra_result.to_dict())
                    self._emit_progress(
                        on_progress,
                        phase="extra_models",
                        message=extra_result.message,
                        level="warning" if not extra_result.success else "info",
                        detail={"model": extra.key, "success": extra_result.success},
                    )
                    logger.info(
                        "smart_setup.step name=extra_model model=%s success=%s",
                        extra.key,
                        extra_result.success,
                    )
                    if not extra_result.success:
                        warnings.append(f"Extra model {extra.key}: {extra_result.message}")
                        degraded = True
                        if not opts.graceful_degrade:
                            return self._finalize_run(
                                success=False,
                                steps=steps,
                                intelligence=intelligence,
                                on_progress=on_progress,
                                failure_message=extra_result.message,
                                warnings=warnings,
                                manual_steps=manual_steps,
                                degraded=degraded,
                            )
        else:
            skip_message = (
                f"Ollama-stappen overgeslagen: provider {provider} (tier {intelligence.get('tier')})."
            )
            steps.append(
                {
                    "name": "skipped_vllm_provider",
                    "success": True,
                    "message": skip_message,
                    "command": "",
                }
            )
            self._emit_progress(
                on_progress,
                phase="skipped_vllm_provider",
                message=skip_message,
                detail={"provider": provider},
            )
            logger.info("smart_setup.step name=skipped_vllm_provider success=True")

        hardware_snapshot = HardwareInspector.capture()
        config_result = self._setup_service.apply_recommended_config(
            hardware=hardware_snapshot,
            model=descriptor,
        )
        steps.append(config_result.to_dict())
        self._emit_progress(
            on_progress,
            phase="config",
            message=config_result.message,
            level="error" if not config_result.success else "info",
            detail={"success": config_result.success, "command": config_result.command},
        )
        logger.info("smart_setup.step name=%s success=%s", config_result.name, config_result.success)
        if not config_result.success:
            return self._finalize_run(
                success=False,
                steps=steps,
                intelligence=intelligence,
                on_progress=on_progress,
                failure_message=config_result.message,
                warnings=warnings,
                manual_steps=manual_steps,
                degraded=degraded,
            )

        return self._complete_run(
            steps=steps,
            intelligence=intelligence,
            descriptor=descriptor,
            on_progress=on_progress,
            mark_complete=mark_complete,
            degraded=degraded,
            warnings=warnings,
            manual_steps=manual_steps,
        )

    def mark_setup_complete(self) -> None:
        intelligence_status = self._intelligence_manager.get_status()
        hardware_intel = self._intelligence_manager.hardware_manager.latest()
        descriptor = self._resolve_descriptor(intelligence_status, hardware_intel.to_dict())
        hardware_snapshot = HardwareInspector.capture()
        self._setup_service.mark_complete(hardware=hardware_snapshot, model=descriptor)
        existing = self._setup_service.load_status()
        merged = {
            **existing,
            "smart_setup": True,
            "adaptive_intelligence": intelligence_status.to_dict(),
            "hardware_tier": hardware_intel.intelligence_tier,
            "recommended_model": descriptor.key,
        }
        self._setup_service.save_status(merged)
        logger.info(
            "smart_setup.mark_complete tier=%s model=%s",
            intelligence_status.tier,
            descriptor.key,
        )

    def _install_ollama_subprocess(self) -> tuple[SubprocessStepResult, list[dict[str, Any]]]:
        manual_steps = self._ollama_install_instruction_steps()
        if self._ollama_on_path():
            return (
                SubprocessStepResult("ollama", True, "Ollama is al geïnstalleerd.", ""),
                [],
            )

        system = platform.system()
        if system == "Windows" and shutil.which("winget") is not None:
            command = ["winget", "install", "-e", "--id", "Ollama.Ollama"]
            result = self._run_subprocess_step(
                "ollama",
                command,
                timeout_sec=_OLLAMA_INSTALL_TIMEOUT_SEC,
                success_message="Ollama geïnstalleerd via winget. Start de Ollama-app indien nodig.",
            )
        elif system == "Darwin" and shutil.which("brew") is not None:
            command = ["brew", "install", "ollama"]
            result = self._run_subprocess_step(
                "ollama",
                command,
                timeout_sec=_OLLAMA_INSTALL_TIMEOUT_SEC,
                success_message="Ollama geïnstalleerd via Homebrew.",
            )
        elif system == "Linux":
            command = ["sh", "-c", "curl -fsSL https://ollama.com/install.sh | sh"]
            result = self._run_subprocess_step(
                "ollama",
                command,
                timeout_sec=_OLLAMA_INSTALL_TIMEOUT_SEC,
                success_message="Ollama geïnstalleerd via het officiële script.",
            )
        else:
            result = SubprocessStepResult(
                "ollama",
                False,
                (
                    "Ollama kon niet automatisch worden geïnstalleerd op dit platform. "
                    "Gebruik de handmatige stappen hieronder of download van https://ollama.com/download."
                ),
                "",
            )

        if result.success and not self._ollama_on_path():
            result = SubprocessStepResult(
                "ollama",
                False,
                (
                    "Ollama-installatie voltooid maar het commando staat nog niet op PATH. "
                    "Herstart de terminal of installeer handmatig, start daarna de Ollama-app."
                ),
                result.command,
            )
        if not result.success:
            result = SubprocessStepResult(
                "ollama",
                False,
                self._humanize_failure("ollama", result.message, "", result.command),
                result.command,
            )
        return result, manual_steps

    def _verify_ollama_runtime(self) -> SubprocessStepResult:
        if not self._ollama_on_path():
            return SubprocessStepResult(
                "ollama_verify",
                False,
                "Ollama CLI niet gevonden op PATH. Volg de handmatige installatiestappen.",
                "",
            )
        installed = ModelCatalog.installed_ollama_models()
        if installed:
            return SubprocessStepResult(
                "ollama_verify",
                True,
                f"Ollama daemon bereikbaar ({len(installed)} model(s) zichtbaar).",
                "ollama list",
            )
        list_result = self._run_subprocess_step(
            "ollama_verify",
            ["ollama", "list"],
            timeout_sec=30,
            success_message="Ollama daemon bereikbaar.",
        )
        if list_result.success:
            return list_result
        return SubprocessStepResult(
            "ollama_verify",
            False,
            (
                "Ollama is geïnstalleerd maar de daemon lijkt niet te draaien. "
                "Start de Ollama-app (Windows/macOS) of voer `ollama serve` uit en probeer opnieuw."
            ),
            "ollama list",
        )

    def _pull_model_subprocess(
        self,
        descriptor: ModelDescriptor,
        *,
        on_progress: SetupProgressCallback | None = None,
    ) -> SubprocessStepResult:
        tag = str(descriptor.ollama_tag or "").strip()
        if not tag:
            return SubprocessStepResult("model_pull", False, "Geen Ollama model-tag geconfigureerd.", "")
        if not self._ollama_on_path():
            return SubprocessStepResult(
                "model_pull",
                False,
                "Ollama CLI ontbreekt; installeer Ollama voordat je een model downloadt.",
                "",
            )
        if self._ollama_model_installed(tag):
            return SubprocessStepResult(
                "model_pull",
                True,
                f"Model {tag} is al aanwezig.",
                f"ollama pull {tag}",
            )

        command = ["ollama", "pull", tag]
        try:
            completed = subprocess.run(
                command,
                capture_output=True,
                text=True,
                timeout=_OLLAMA_PULL_TIMEOUT_SEC,
                check=False,
                cwd=str(self.workspace_root),
            )
        except subprocess.TimeoutExpired:
            return SubprocessStepResult(
                "model_pull",
                False,
                f"Time-out bij download van {tag}. Controleer netwerk en schijfruimte.",
                " ".join(command),
            )
        except Exception as exc:
            logger.exception("smart_setup.model_pull_failed tag=%s", tag)
            return SubprocessStepResult("model_pull", False, str(exc), " ".join(command))

        combined = "\n".join(
            line for line in (completed.stdout or "").splitlines() + (completed.stderr or "").splitlines() if line.strip()
        )
        for line in combined.splitlines():
            stripped = line.strip()
            if stripped:
                self._emit_progress(
                    on_progress,
                    phase="model_pull_progress",
                    message=stripped,
                    detail={"model": tag},
                )

        if completed.returncode == 0:
            message = f"Model {tag} gedownload."
            if combined.strip():
                message = f"{message}\n{combined.strip()[-_OUTPUT_TAIL_CHARS:]}"
            return SubprocessStepResult("model_pull", True, message, " ".join(command))

        detail = (completed.stderr or completed.stdout or f"Exit code {completed.returncode}").strip()
        return SubprocessStepResult(
            "model_pull",
            False,
            self._humanize_failure("model_pull", detail, combined, " ".join(command)),
            " ".join(command),
        )

    def _run_subprocess_step(
        self,
        name: str,
        command: list[str],
        *,
        timeout_sec: int,
        success_message: str,
    ) -> SubprocessStepResult:
        command_str = " ".join(command)
        try:
            completed = subprocess.run(
                command,
                capture_output=True,
                text=True,
                timeout=timeout_sec,
                check=False,
                cwd=str(self.workspace_root),
            )
        except subprocess.TimeoutExpired:
            return SubprocessStepResult(
                name,
                False,
                f"Time-out na {timeout_sec}s: {command_str}",
                command_str,
            )
        except Exception as exc:
            logger.exception("smart_setup.subprocess_failed name=%s", name)
            return SubprocessStepResult(name, False, str(exc), command_str)

        stdout = (completed.stdout or "").strip()
        stderr = (completed.stderr or "").strip()
        if completed.returncode == 0:
            message = success_message
            if stdout:
                message = f"{message}\n{stdout[-_OUTPUT_TAIL_CHARS:]}"
            return SubprocessStepResult(name, True, message, command_str)

        detail = stderr or stdout or f"Exit code {completed.returncode}"
        return SubprocessStepResult(
            name,
            False,
            self._humanize_failure(name, detail, stdout, command_str),
            command_str,
        )

    @staticmethod
    def _ollama_on_path() -> bool:
        return shutil.which("ollama") is not None

    def _manual_steps_for_model(self, ollama_tag: str) -> list[dict[str, Any]]:
        return [
            {
                "id": "model_pull_manual",
                "title": f"Download model handmatig ({ollama_tag})",
                "command": f"ollama pull {ollama_tag}",
                "manual": "Start Ollama en voer het pull-commando uit in een terminal.",
                "required": True,
            }
        ]

    @staticmethod
    def _humanize_failure(
        phase: str,
        detail: str,
        stdout: str,
        command: str,
    ) -> str:
        text = f"{detail}\n{stdout}".lower()
        if phase in {"ollama", "ollama_verify"}:
            if "winget" in command or "not found" in text:
                return (
                    "Automatische Ollama-installatie mislukt. "
                    "Installeer handmatig via winget, brew of https://ollama.com/download en start de app."
                )
            return (
                "Ollama-installatie mislukt. "
                "Installeer handmatig en start de Ollama-app voordat je doorgaat."
            )
        if phase == "model_pull":
            if "connection refused" in text or "connect" in text and "refused" in text:
                return "Kan geen verbinding maken met Ollama. Start de Ollama-app en probeer opnieuw."
            if "not found" in text or "404" in text:
                return f"Model niet gevonden bij Ollama. Controleer de tag in het catalogusbestand. Details: {detail[:400]}"
            return f"Model download mislukt: {detail[:500]}"
        return detail[:500] if detail else "Onbekende fout tijdens setup."

    def _complete_run(
        self,
        *,
        steps: list[dict[str, Any]],
        intelligence: dict[str, Any],
        descriptor: ModelDescriptor,
        on_progress: SetupProgressCallback | None,
        mark_complete: bool,
        degraded: bool,
        warnings: list[str],
        manual_steps: list[dict[str, Any]],
    ) -> SmartSetupResult:
        if mark_complete:
            self.mark_setup_complete()
        else:
            existing = self._setup_service.load_status()
            self._setup_service.save_status(
                {
                    **existing,
                    "steps": steps,
                    "adaptive_intelligence": intelligence,
                    "smart_setup": True,
                    "degraded": degraded,
                    "warnings": warnings,
                    "recommended_model": descriptor.key,
                }
            )
        complete_message = (
            "Smart setup voltooid met waarschuwingen. Controleer de inference-stappen."
            if degraded
            else "Smart setup voltooid."
        )
        self._emit_progress(
            on_progress,
            phase="complete",
            message=complete_message,
            level="warning" if degraded else "info",
            detail={"recommended_model": descriptor.key, "degraded": degraded},
        )
        status = self.get_setup_status()
        logger.info(
            "smart_setup.complete success=True degraded=%s model=%s warnings=%s",
            degraded,
            descriptor.key,
            len(warnings),
        )
        return SmartSetupResult(
            success=True,
            steps=steps,
            status=status,
            degraded=degraded,
            warnings=warnings,
            manual_steps=manual_steps,
        )

    def _apply_intelligence_mode(self, force_high: bool) -> None:
        config_path = self.workspace_root / "config.yaml"
        if not config_path.exists():
            logger.warning("smart_setup.config_missing path=%s", config_path)
            return
        try:
            payload = yaml.safe_load(config_path.read_text(encoding="utf-8")) or {}
        except Exception as exc:
            logger.warning("smart_setup.config_read_failed detail=%s", exc)
            return
        intelligence = payload.get("intelligence")
        if not isinstance(intelligence, dict):
            intelligence = {}
            payload["intelligence"] = intelligence
        intelligence["mode"] = "force_high" if force_high else "auto"
        config_path.write_text(
            yaml.safe_dump(payload, sort_keys=False, allow_unicode=False),
            encoding="utf-8",
        )
        ConfigLoader.invalidate()
        logger.info("smart_setup.intelligence_mode mode=%s", intelligence["mode"])

    def _resolve_descriptor(
        self,
        intelligence_status: AdaptiveIntelligenceStatus,
        hardware: dict[str, Any],
    ) -> ModelDescriptor:
        catalog = self._intelligence_manager.hardware_manager.catalog
        model_key = str(intelligence_status.recommended_model or "").strip()
        descriptor = catalog.get(model_key) if model_key else None
        if descriptor is not None:
            return descriptor
        return catalog.recommended_for(
            ram_gb=float(hardware.get("ram_gb", 0.0) or 0.0),
            gpu_vram_gb=float(hardware.get("gpu_vram_gb", 0.0) or 0.0),
            vllm_supported=bool(hardware.get("vllm_supported", False)),
        )

    @staticmethod
    def _ollama_model_installed(ollama_tag: str) -> bool:
        if not ollama_tag.strip():
            return False
        installed = ModelCatalog.installed_ollama_models()
        if not installed:
            return False
        resolved = resolve_ollama_model_tag(ollama_tag, installed)
        return resolved == ollama_tag

    @staticmethod
    def _collect_missing(
        *,
        setup_complete: bool,
        ollama_required: bool,
        ollama_installed: bool,
        model_present: bool,
        ollama_tag: str,
    ) -> list[str]:
        missing: list[str] = []
        if not setup_complete:
            missing.append("setup_complete")
        if ollama_required and not ollama_installed:
            missing.append("ollama")
        if ollama_required and not model_present and ollama_tag:
            missing.append(f"model:{ollama_tag}")
        return missing

    def _ollama_install_instruction_steps(self) -> list[dict[str, Any]]:
        system = platform.system()
        if system == "Windows" and shutil.which("winget") is not None:
            command = "winget install -e --id Ollama.Ollama"
            manual = "Installeer Ollama via winget en start de Ollama-app."
        elif system == "Darwin" and shutil.which("brew") is not None:
            command = "brew install ollama"
            manual = "Installeer Ollama via Homebrew en start de daemon."
        elif system == "Linux":
            command = "curl -fsSL https://ollama.com/install.sh | sh"
            manual = "Installeer Ollama via het officiële installatiescript."
        else:
            command = ""
            manual = (
                "Ollama kon niet automatisch worden geïnstalleerd op dit platform. "
                "Download Ollama van https://ollama.com/download."
            )
        return [
            {
                "id": "ollama_install",
                "title": "Installeer Ollama",
                "command": command,
                "manual": manual,
                "required": True,
            }
        ]

    def _finalize_run(
        self,
        *,
        success: bool,
        steps: list[dict[str, Any]],
        intelligence: dict[str, Any],
        on_progress: SetupProgressCallback | None,
        failure_message: str,
        warnings: list[str],
        manual_steps: list[dict[str, Any]],
        degraded: bool,
    ) -> SmartSetupResult:
        self._emit_progress(
            on_progress,
            phase="failed",
            message=failure_message,
            level="error",
            detail={"success": False},
        )
        self._setup_service.save_status(
            {
                "steps": steps,
                "adaptive_intelligence": intelligence,
                "smart_setup": False,
                "degraded": degraded,
                "warnings": warnings,
            }
        )
        status = self.get_setup_status()
        logger.warning("smart_setup.complete success=False detail=%s", failure_message)
        return SmartSetupResult(
            success=success,
            steps=steps,
            status=status,
            degraded=degraded,
            warnings=warnings,
            manual_steps=manual_steps,
        )

    @staticmethod
    def _emit_progress(
        callback: SetupProgressCallback | None,
        *,
        phase: str,
        message: str,
        level: ProgressLevel = "info",
        detail: dict[str, Any] | None = None,
    ) -> None:
        if callback is None:
            return
        event = SetupProgressEvent(
            phase=phase,
            message=message,
            percent=_PROGRESS_PERCENT.get(phase),
            level=level,
            detail=detail or {},
        )
        callback(event)

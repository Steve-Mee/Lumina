"""Ollama install, verify, and model pull subprocess helpers."""

from __future__ import annotations

import platform
from typing import TYPE_CHECKING, Any

from lumina_core.engine.model_catalog import ModelCatalog, ModelDescriptor
from lumina_core.logging_utils import get_logger
from lumina_launcher.services.setup_compat import shutil, subprocess
from lumina_launcher.services.setup_schemas import (
    OLLAMA_INSTALL_TIMEOUT_SEC,
    OLLAMA_PULL_TIMEOUT_SEC,
    OUTPUT_TAIL_CHARS,
    SetupProgressCallback,
    SubprocessStepResult,
)

if TYPE_CHECKING:
    from lumina_launcher.services.smart_setup_service import SmartSetupService

logger = get_logger(__name__)


def install_ollama_subprocess(service: SmartSetupService) -> tuple[SubprocessStepResult, list[dict[str, Any]]]:
    manual_steps = service._ollama_install_instruction_steps()
    if service._ollama_on_path():
            return (
                SubprocessStepResult("ollama", True, "Ollama is al geïnstalleerd.", ""),
                [],
            )

    system = platform.system()
    if system == "Windows" and shutil.which("winget") is not None:
            command = ["winget", "install", "-e", "--id", "Ollama.Ollama"]
            result = service._run_subprocess_step(service, 
                "ollama",
                command,
                timeout_sec=OLLAMA_INSTALL_TIMEOUT_SEC,
                success_message="Ollama geïnstalleerd via winget. Start de Ollama-app indien nodig.",
            )
    elif system == "Darwin" and shutil.which("brew") is not None:
            command = ["brew", "install", "ollama"]
            result = service._run_subprocess_step(service, 
                "ollama",
                command,
                timeout_sec=OLLAMA_INSTALL_TIMEOUT_SEC,
                success_message="Ollama geïnstalleerd via Homebrew.",
            )
    elif system == "Linux":
            command = ["sh", "-c", "curl -fsSL https://ollama.com/install.sh | sh"]
            result = service._run_subprocess_step(service, 
                "ollama",
                command,
                timeout_sec=OLLAMA_INSTALL_TIMEOUT_SEC,
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

    if result.success and not service._ollama_on_path():
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
                service._humanize_failure("ollama", result.message, "", result.command),
                result.command,
            )
    return result, manual_steps


def verify_ollama_runtime(service: SmartSetupService) -> SubprocessStepResult:
    if not service._ollama_on_path():
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
    list_result = service._run_subprocess_step(service, 
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


def pull_model_subprocess(
    service: SmartSetupService,
    descriptor: ModelDescriptor,
    *,
    on_progress: SetupProgressCallback | None = None,
) -> SubprocessStepResult:
    tag = str(descriptor.ollama_tag or "").strip()
    if not tag:
            return SubprocessStepResult("model_pull", False, "Geen Ollama model-tag geconfigureerd.", "")
    if not service._ollama_on_path():
            return SubprocessStepResult(
                "model_pull",
                False,
                "Ollama CLI ontbreekt; installeer Ollama voordat je een model downloadt.",
                "",
            )
    if service._ollama_model_installed(tag):
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
                timeout=OLLAMA_PULL_TIMEOUT_SEC,
                check=False,
                cwd=str(service.workspace_root),
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
                service._emit_progress(
                    on_progress,
                    phase="model_pull_progress",
                    message=stripped,
                    detail={"model": tag},
                )

    if completed.returncode == 0:
            message = f"Model {tag} gedownload."
            if combined.strip():
                message = f"{message}\n{combined.strip()[-OUTPUT_TAIL_CHARS:]}"
            return SubprocessStepResult("model_pull", True, message, " ".join(command))

    detail = (completed.stderr or completed.stdout or f"Exit code {completed.returncode}").strip()
    return SubprocessStepResult(
            "model_pull",
            False,
            service._humanize_failure("model_pull", detail, combined, " ".join(command)),
            " ".join(command),
    )


def run_subprocess_step(
    service: SmartSetupService,
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
                cwd=str(service.workspace_root),
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
                message = f"{message}\n{stdout[-OUTPUT_TAIL_CHARS:]}"
            return SubprocessStepResult(name, True, message, command_str)

    detail = stderr or stdout or f"Exit code {completed.returncode}"
    return SubprocessStepResult(
            name,
            False,
            service._humanize_failure(name, detail, stdout, command_str),
            command_str,
    )


def manual_steps_for_model(ollama_tag: str) -> list[dict[str, Any]]:
    return [
            {
                "id": "model_pull_manual",
                "title": f"Download model handmatig ({ollama_tag})",
                "command": f"ollama pull {ollama_tag}",
                "manual": "Start Ollama en voer het pull-commando uit in een terminal.",
                "required": True,
            }
    ]


def humanize_failure(
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

"""First-run detection, status probes, and install instruction builders."""

from __future__ import annotations

import platform
import sys
from typing import TYPE_CHECKING, Any

from lumina_core.adaptive_intelligence import AdaptiveIntelligenceStatus
from lumina_core.engine.model_catalog import ModelDescriptor
from lumina_core.engine.ollama_model_resolve import resolve_ollama_model_tag
from lumina_core.logging_utils import get_logger
from lumina_launcher.services.setup_compat import ModelCatalog, shutil

if TYPE_CHECKING:
    from lumina_launcher.services.smart_setup_service import SmartSetupService

logger = get_logger(__name__)


def is_first_time(service: SmartSetupService) -> bool:
    first_time = not service._setup_service.is_setup_complete()
    logger.debug("smart_setup.first_time complete=%s", not first_time)
    return first_time


def is_intelligence_stack_ready(service: SmartSetupService) -> bool:
    status = service.get_setup_status()
    stack_missing = [item for item in status.get("missing", []) if item != "setup_complete"]
    if not stack_missing:
            return True
    loaded = service._setup_service.load_status()
    return bool(loaded.get("smart_setup")) and not stack_missing


def get_setup_status(service: SmartSetupService) -> dict[str, Any]:
    intelligence_status = service._intelligence_manager.refresh(refresh_hardware=False)
    intelligence = intelligence_status.to_dict()
    hardware = service._intelligence_manager.hardware_manager.latest().to_dict()
    descriptor = service._resolve_descriptor(intelligence_status, hardware)
    provider = str(intelligence.get("recommended_provider", "ollama") or "ollama")
    ollama_required = provider == "ollama"
    ollama_installed = service._ollama_on_path()
    model_present = service._ollama_model_installed(descriptor.ollama_tag) if ollama_required else True
    setup_complete = service._setup_service.is_setup_complete()
    missing = service._collect_missing(
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


def get_install_instructions(service: SmartSetupService) -> dict[str, Any]:
    status = get_setup_status(service)
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
                "command": f"{sys.executable} -m pip install pandas requests pyyaml psutil ollama",
                "manual": "Alleen nodig als automatische installatie faalt.",
                "required": False,
            }
    )
    steps.append(
            {
                "id": "runtime_deps",
                "title": "Runtime dependencies",
                "command": f"{sys.executable} -m pip install -r requirements.txt",
                "manual": f"Voer uit vanuit: {service.workspace_root}",
                "required": False,
            }
    )

    if provider == "ollama":
            if "ollama" in missing or not status.get("ollama_installed"):
                steps.extend(service._ollama_install_instruction_steps())
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


def resolve_descriptor(
    service: SmartSetupService,
    intelligence_status: AdaptiveIntelligenceStatus,
    hardware: dict[str, Any],
) -> ModelDescriptor:
    catalog = service._intelligence_manager.hardware_manager.catalog
    model_key = str(intelligence_status.recommended_model or "").strip()
    descriptor = catalog.get(model_key) if model_key else None
    if descriptor is not None:
            return descriptor
    return catalog.recommended_for(
            ram_gb=float(hardware.get("ram_gb", 0.0) or 0.0),
            gpu_vram_gb=float(hardware.get("gpu_vram_gb", 0.0) or 0.0),
            vllm_supported=bool(hardware.get("vllm_supported", False)),
    )


def ollama_on_path() -> bool:
    return shutil.which("ollama") is not None


def ollama_model_installed(ollama_tag: str) -> bool:
    if not ollama_tag.strip():
            return False
    installed = ModelCatalog.installed_ollama_models()
    if not installed:
            return False
    resolved = resolve_ollama_model_tag(ollama_tag, installed)
    return resolved == ollama_tag


def collect_missing(
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


def ollama_install_instruction_steps() -> list[dict[str, Any]]:
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

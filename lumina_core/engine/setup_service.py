from __future__ import annotations
import logging

import json
import platform
import shutil
import subprocess
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import yaml

from .hardware_inspector import HardwareSnapshot
from .model_catalog import ModelCatalog, ModelDescriptor


@dataclass(slots=True)
class SetupStepResult:
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


class SetupService:
    STATE_FILE = Path("state/lumina_setup_complete.json")
    STATUS_FILE = Path("state/lumina_setup_status.json")

    def __init__(self, *, config_path: Path | None = None, env_path: Path | None = None):
        self.config_path = config_path or Path("config.yaml")
        self.env_path = env_path or Path(".env")

    def is_first_run(self) -> bool:
        return not self.STATE_FILE.exists()

    def load_status(self) -> dict[str, Any]:
        if not self.STATUS_FILE.exists():
            return {}
        try:
            payload = json.loads(self.STATUS_FILE.read_text(encoding="utf-8"))
            return payload if isinstance(payload, dict) else {}
        except Exception:
            logging.exception("Unhandled broad exception fallback in lumina_core/engine/setup_service.py:51")
            return {}

    def save_status(self, payload: dict[str, Any]) -> None:
        self.STATUS_FILE.parent.mkdir(parents=True, exist_ok=True)
        self.STATUS_FILE.write_text(json.dumps(payload, indent=2), encoding="utf-8")

    def mark_complete(self, *, hardware: HardwareSnapshot, model: ModelDescriptor) -> None:
        payload = {
            "completed": True,
            "python": sys.executable,
            "os": platform.system(),
            "hardware_profile": hardware.profile_tier,
            "recommended_model": model.key,
            "provider": model.recommended_provider,
        }
        self.STATE_FILE.parent.mkdir(parents=True, exist_ok=True)
        self.STATE_FILE.write_text(json.dumps(payload, indent=2), encoding="utf-8")

    def install_runtime_dependencies(self) -> SetupStepResult:
        command = [sys.executable, "-m", "pip", "install", "-r", "requirements.txt"]
        return self._run_step("runtime_dependencies", command, "Python runtime packages installed")

    def install_launcher_dependencies(self) -> SetupStepResult:
        packages = ["streamlit", "pandas", "requests", "pyyaml", "psutil", "ollama"]
        command = [sys.executable, "-m", "pip", "install", *packages]
        return self._run_step("launcher_dependencies", command, "Launcher dependencies installed")

    def install_unsloth_dependencies(self) -> SetupStepResult:
        command = [sys.executable, "-m", "pip", "install", "-r", "requirements_finetune.txt"]
        return self._run_step("unsloth_dependencies", command, "Fine-tuning dependencies installed")

    def ensure_ollama(self) -> SetupStepResult:
        if shutil.which("ollama") is not None:
            return SetupStepResult("ollama", True, "Ollama is already installed")

        system = platform.system()
        if system == "Windows" and shutil.which("winget") is not None:
            command = ["winget", "install", "-e", "--id", "Ollama.Ollama"]
            return self._run_step("ollama", command, "Ollama installed via winget")
        if system == "Darwin" and shutil.which("brew") is not None:
            command = ["brew", "install", "ollama"]
            return self._run_step("ollama", command, "Ollama installed via brew")
        if system == "Linux":
            command = ["sh", "-c", "curl -fsSL https://ollama.com/install.sh | sh"]
            return self._run_step("ollama", command, "Ollama installed via official script")
        return SetupStepResult(
            "ollama",
            False,
            "Ollama kon niet automatisch worden geinstalleerd op deze machine; gebruik een ondersteunde package manager of installeer handmatig.",
        )

    def pull_model(self, descriptor: ModelDescriptor) -> SetupStepResult:
        command = ["ollama", "pull", descriptor.ollama_tag]
        return self._run_step("model_pull", command, f"Model {descriptor.ollama_tag} downloaded")

    def apply_recommended_config(self, *, hardware: HardwareSnapshot, model: ModelDescriptor) -> SetupStepResult:
        if not self.config_path.exists():
            return SetupStepResult("config_update", False, f"Config not found: {self.config_path}")
        payload = yaml.safe_load(self.config_path.read_text(encoding="utf-8")) or {}
        payload["hardware_profile"] = hardware.profile_tier
        inference = payload.setdefault("inference", {})
        if not isinstance(inference, dict):
            inference = {}
            payload["inference"] = inference
        inference["primary_provider"] = model.recommended_provider
        inference["provider_order"] = self._build_provider_order(model.recommended_provider)
        ollama = payload.setdefault("ollama", {})
        if not isinstance(ollama, dict):
            ollama = {}
            payload["ollama"] = ollama
        ollama["num_ctx"] = model.context_length
        ollama["context_length"] = model.context_length
        models = payload.setdefault("models", {})
        if not isinstance(models, dict):
            models = {}
            payload["models"] = models
        models["reasoning"] = model.ollama_tag
        models.setdefault("vision", "qwen2.5-vl:7b")
        models.setdefault("reflector", "qwen2.5:3b")
        models.setdefault("meta", model.ollama_tag)
        payload.setdefault("vllm", {})
        if isinstance(payload["vllm"], dict):
            payload["vllm"]["model_name"] = model.key
        self.config_path.write_text(yaml.safe_dump(payload, sort_keys=False, allow_unicode=False), encoding="utf-8")
        return SetupStepResult("config_update", True, f"Config updated for {model.display_name}")

    def upgrade_model(self, descriptor: ModelDescriptor) -> list[SetupStepResult]:
        results = [self.pull_model(descriptor)]
        if results[-1].success:
            cached_hardware = (
                HardwareSnapshot(**json.loads(Path("state/hardware_snapshot.json").read_text(encoding="utf-8")))
                if Path("state/hardware_snapshot.json").exists()
                else None
            )
            if cached_hardware is not None:
                results.append(self.apply_recommended_config(hardware=cached_hardware, model=descriptor))
        return results

    @staticmethod
    def load_catalog() -> ModelCatalog:
        return ModelCatalog()

    @staticmethod
    def _build_provider_order(primary: str) -> list[str]:
        order = [primary]
        for provider in ["vllm", "ollama", "grok_remote"]:
            if provider not in order:
                order.append(provider)
        return order

    def _run_step(self, name: str, command: list[str], success_message: str) -> SetupStepResult:
        try:
            completed = subprocess.run(
                command,
                capture_output=True,
                text=True,
                timeout=1800,
                check=False,
            )
        except Exception as exc:
            logging.exception("Unhandled broad exception fallback in lumina_core/engine/setup_service.py:171")
            return SetupStepResult(name, False, str(exc), " ".join(command))

        stdout = completed.stdout.strip()
        stderr = completed.stderr.strip()
        if completed.returncode == 0:
            message = success_message
            if stdout:
                message = f"{success_message}\n{stdout[-700:]}"
            return SetupStepResult(name, True, message, " ".join(command))
        detail = stderr or stdout or f"Exit code {completed.returncode}"
        return SetupStepResult(name, False, detail[-1200:], " ".join(command))

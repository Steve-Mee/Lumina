from __future__ import annotations
import logging

import json
import platform
import shutil
import subprocess
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any


@dataclass(slots=True)
class HardwareSnapshot:
    os_name: str
    os_version: str
    cpu_name: str
    cpu_cores_physical: int
    cpu_cores_logical: int
    ram_gb: float
    gpu_name: str | None
    gpu_vram_gb: float
    compute_capability: float
    ollama_installed: bool
    ollama_running: bool
    nvidia_smi_available: bool
    vllm_supported: bool
    profile_tier: str
    recommended_model_key: str
    recommended_provider: str
    recommended_context_length: int
    notes: list[str]

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


class HardwareInspector:
    STATE_FILE = Path("state/hardware_snapshot.json")

    @classmethod
    def capture(cls) -> HardwareSnapshot:
        os_name = platform.system()
        memory = cls._read_memory_gb()
        gpu_name, gpu_vram_gb, compute_capability, nvidia_smi_available = cls._read_nvidia_gpu()
        ollama_installed = shutil.which("ollama") is not None
        ollama_running = cls._detect_ollama_running()
        vllm_supported = nvidia_smi_available and compute_capability >= 7.0 and os_name != "Windows"
        profile_tier = cls._classify_tier(memory, gpu_vram_gb, compute_capability)
        recommended_model_key, recommended_provider, recommended_context_length = cls._recommend_inference_plan(
            profile_tier=profile_tier,
            gpu_vram_gb=gpu_vram_gb,
            vllm_supported=vllm_supported,
        )
        notes = cls._build_notes(
            profile_tier=profile_tier,
            gpu_vram_gb=gpu_vram_gb,
            ram_gb=memory,
            compute_capability=compute_capability,
            os_name=os_name,
            ollama_installed=ollama_installed,
            ollama_running=ollama_running,
            vllm_supported=vllm_supported,
        )

        cpu_name = platform.processor().strip() or "Unknown CPU"
        snapshot = HardwareSnapshot(
            os_name=os_name,
            os_version=platform.version(),
            cpu_name=cpu_name,
            cpu_cores_physical=max(1, cls._cpu_count(logical=False)),
            cpu_cores_logical=max(1, cls._cpu_count(logical=True)),
            ram_gb=memory,
            gpu_name=gpu_name,
            gpu_vram_gb=gpu_vram_gb,
            compute_capability=compute_capability,
            ollama_installed=ollama_installed,
            ollama_running=ollama_running,
            nvidia_smi_available=nvidia_smi_available,
            vllm_supported=vllm_supported,
            profile_tier=profile_tier,
            recommended_model_key=recommended_model_key,
            recommended_provider=recommended_provider,
            recommended_context_length=recommended_context_length,
            notes=notes,
        )
        cls.STATE_FILE.parent.mkdir(parents=True, exist_ok=True)
        cls.STATE_FILE.write_text(json.dumps(snapshot.to_dict(), indent=2), encoding="utf-8")
        return snapshot

    @staticmethod
    def load_cached() -> HardwareSnapshot | None:
        path = HardwareInspector.STATE_FILE
        if not path.exists():
            return None
        try:
            payload = json.loads(path.read_text(encoding="utf-8"))
        except Exception:
            logging.exception("Unhandled broad exception fallback in lumina_core/engine/hardware_inspector.py:97")
            return None
        try:
            return HardwareSnapshot(**payload)
        except Exception:
            logging.exception("Unhandled broad exception fallback in lumina_core/engine/hardware_inspector.py:101")
            return None

    @staticmethod
    def tier_requirements() -> dict[str, dict[str, Any]]:
        return {
            "light": {
                "ram_gb": 16,
                "gpu_vram_gb": 0,
                "provider": "ollama",
                "best_model_key": "qwen3.5-4b",
                "summary": "Startniveau voor CPU of kleine GPU. Bedoeld voor lokale tests en lichtere redeneertaken.",
            },
            "sweet": {
                "ram_gb": 32,
                "gpu_vram_gb": 8,
                "provider": "ollama",
                "best_model_key": "qwen3.5-9b",
                "summary": "Beste balans voor lokale trading inference met GPU-versnelling en ruimere context.",
            },
            "beast": {
                "ram_gb": 64,
                "gpu_vram_gb": 20,
                "provider": "vllm",
                "best_model_key": "qwen3.5-35b",
                "summary": "Volledige high-end modus voor grote modellen, vLLM-serving en toekomstige fine-tuning.",
            },
        }

    @staticmethod
    def _cpu_count(*, logical: bool) -> int:
        try:
            import psutil  # pyright: ignore[reportMissingImports]

            count = psutil.cpu_count(logical=logical)
            return int(count or 0)
        except Exception:
            logging.exception("Unhandled broad exception fallback in lumina_core/engine/hardware_inspector.py:137")
            return 0

    @staticmethod
    def _read_memory_gb() -> float:
        try:
            import psutil  # pyright: ignore[reportMissingImports]

            return round(psutil.virtual_memory().total / (1024**3), 1)
        except Exception:
            logging.exception("Unhandled broad exception fallback in lumina_core/engine/hardware_inspector.py:146")
            return 0.0

    @staticmethod
    def _detect_ollama_running() -> bool:
        if shutil.which("ollama") is None:
            return False
        try:
            completed = subprocess.run(
                ["ollama", "list"],
                capture_output=True,
                text=True,
                timeout=5,
                check=False,
            )
            return completed.returncode == 0
        except Exception:
            logging.exception("Unhandled broad exception fallback in lumina_core/engine/hardware_inspector.py:162")
            return False

    @staticmethod
    def _read_nvidia_gpu() -> tuple[str | None, float, float, bool]:
        if shutil.which("nvidia-smi") is None:
            return None, 0.0, 0.0, False

        try:
            completed = subprocess.run(
                [
                    "nvidia-smi",
                    "--query-gpu=name,memory.total,compute_cap",
                    "--format=csv,noheader,nounits",
                ],
                capture_output=True,
                text=True,
                timeout=5,
                check=False,
            )
            if completed.returncode != 0:
                return None, 0.0, 0.0, True
            first_line = next((line.strip() for line in completed.stdout.splitlines() if line.strip()), "")
            if not first_line:
                return None, 0.0, 0.0, True
            parts = [part.strip() for part in first_line.split(",")]
            if len(parts) < 3:
                return None, 0.0, 0.0, True
            name = parts[0] or None
            memory_mib = float(parts[1]) if parts[1] else 0.0
            compute_capability = float(parts[2]) if parts[2] else 0.0
            return name, round(memory_mib / 1024.0, 1), compute_capability, True
        except Exception:
            logging.exception("Unhandled broad exception fallback in lumina_core/engine/hardware_inspector.py:194")
            return None, 0.0, 0.0, True

    @classmethod
    def _classify_tier(cls, ram_gb: float, gpu_vram_gb: float, compute_capability: float) -> str:
        if ram_gb >= 64 and gpu_vram_gb >= 20 and compute_capability >= 7.0:
            return "beast"
        if ram_gb >= 32 and gpu_vram_gb >= 8:
            return "sweet"
        return "light"

    @staticmethod
    def _recommend_inference_plan(profile_tier: str, gpu_vram_gb: float, vllm_supported: bool) -> tuple[str, str, int]:
        if profile_tier == "beast" and vllm_supported:
            return "qwen3.5-35b", "vllm", 32768
        if profile_tier in {"beast", "sweet"} and gpu_vram_gb >= 8:
            return "qwen3.5-9b", "ollama", 16384
        return "qwen3.5-4b", "ollama", 8192

    @staticmethod
    def _build_notes(
        *,
        profile_tier: str,
        gpu_vram_gb: float,
        ram_gb: float,
        compute_capability: float,
        os_name: str,
        ollama_installed: bool,
        ollama_running: bool,
        vllm_supported: bool,
    ) -> list[str]:
        notes: list[str] = []
        if not ollama_installed:
            notes.append("Ollama is nog niet geinstalleerd; de setup-wizard kan dit proberen te automatiseren.")
        elif not ollama_running:
            notes.append("Ollama is geinstalleerd maar reageert nog niet; start of installeer de service opnieuw.")
        if gpu_vram_gb <= 0:
            notes.append("Geen NVIDIA GPU gevonden; de app gebruikt CPU/Ollama fallback en vLLM blijft uitgeschakeld.")
        elif not vllm_supported:
            blockers: list[str] = []
            if os_name == "Windows":
                blockers.append("Windows-native runtime")
            if compute_capability and compute_capability < 7.0:
                blockers.append(f"compute capability {compute_capability:.1f} < sm_70")
            reason = "; ".join(blockers) if blockers else "runtime/gpu beperkingen"
            notes.append(
                "De GPU is zichtbaar maar vLLM-pad is geblokkeerd "
                f"({reason}); gebruik Linux of WSL2 met CUDA voor beast-modus."
            )
        if profile_tier == "light":
            notes.append(
                f"Huidig profiel light: minimaal 32 GB RAM en 8 GB VRAM is nodig voor sweet, 64 GB RAM en 20 GB VRAM voor beast. Huidig RAM={ram_gb:.1f} GB."
            )
        elif profile_tier == "sweet":
            notes.append(
                "Huidig profiel sweet: voor beast is 64 GB RAM, minstens 20 GB VRAM en een Linux/WSL2 CUDA runtime met sm_70+ GPU nodig."
            )
        else:
            notes.append(
                "Huidig profiel beast: hardware is klaar voor grote Qwen-modellen en optionele Unsloth QLoRA op Linux/WSL2."
            )
        return notes

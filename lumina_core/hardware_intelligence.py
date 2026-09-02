"""Hardware intelligence: model tier resolution and performance profile detection."""

from __future__ import annotations

import json
import logging
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Literal

from lumina_core.engine.hardware_inspector import HardwareInspector, HardwareSnapshot
from lumina_core.engine.model_catalog import ModelCatalog, ModelDescriptor

logger = logging.getLogger(__name__)

HardwareProfileName = Literal["cpu_efficient", "gpu_accelerated"]

_GPU_ACCELERATED_MIN_VRAM_GB = 8.0
_HARDWARE_PROFILE_STATE_REL = Path("state/hardware_profile.json")

_LEGACY_TO_CANONICAL_TIER = {
    "beast": "high",
    "sweet": "standard",
    "light": "light",
}


@dataclass(slots=True, frozen=True)
class HardwareProfileTuning:
    """Performance knobs aligned with birth/PPO curriculum defaults."""

    rollout_chunk_trades: int
    max_escalation_level: int
    exploration_chunk_size: int
    curriculum_ppo_timesteps: int
    chunk_size: int
    ppo_update_timesteps: int
    oracle_scan_stride: int
    recommended_model_tier: str

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


HARDWARE_PROFILES: dict[str, HardwareProfileTuning] = {
    "cpu_efficient": HardwareProfileTuning(
        rollout_chunk_trades=50,
        max_escalation_level=2,
        exploration_chunk_size=4,
        curriculum_ppo_timesteps=1_500,
        chunk_size=10_000,
        ppo_update_timesteps=10_000,
        oracle_scan_stride=10,
        recommended_model_tier="light",
    ),
    "gpu_accelerated": HardwareProfileTuning(
        rollout_chunk_trades=250,
        max_escalation_level=5,
        exploration_chunk_size=8,
        curriculum_ppo_timesteps=3_000,
        chunk_size=50_000,
        ppo_update_timesteps=25_000,
        oracle_scan_stride=5,
        recommended_model_tier="standard",
    ),
}


def _cuda_available() -> bool:
    try:
        import torch  # pyright: ignore[reportMissingImports]

        return bool(torch.cuda.is_available())
    except ImportError:
        return False


def _read_gpu_via_torch() -> tuple[str | None, float]:
    try:
        import torch  # pyright: ignore[reportMissingImports]

        if not torch.cuda.is_available():
            return None, 0.0
        props = torch.cuda.get_device_properties(0)
        name = str(torch.cuda.get_device_name(0) or "").strip() or None
        vram_gb = round(float(props.total_memory) / (1024**3), 1)
        return name, vram_gb
    except ImportError:
        return None, 0.0
    except Exception:
        logger.exception("Failed to read GPU properties via torch.cuda")
        return None, 0.0


def detect_hardware_profile() -> dict[str, Any]:
    """Detect CUDA, GPU, CPU, RAM and recommend a performance profile."""
    has_cuda = _cuda_available()
    gpu_name, vram_gb = _read_gpu_via_torch()
    if gpu_name is None and vram_gb <= 0.0:
        nvidia_name, nvidia_vram, _, _ = HardwareInspector._read_nvidia_gpu()
        gpu_name = nvidia_name
        vram_gb = float(nvidia_vram)

    cpu_cores = max(1, HardwareInspector._cpu_count(logical=True))
    ram_gb = float(HardwareInspector._read_memory_gb())
    recommended_profile: HardwareProfileName = (
        "gpu_accelerated"
        if has_cuda and vram_gb >= _GPU_ACCELERATED_MIN_VRAM_GB
        else "cpu_efficient"
    )

    return {
        "has_cuda": has_cuda,
        "gpu_name": gpu_name,
        "vram_gb": float(vram_gb),
        "cpu_cores": int(cpu_cores),
        "ram_gb": ram_gb,
        "recommended_profile": recommended_profile,
    }


def _resolve_workspace_root(workspace_root: Path | str | None) -> Path:
    if workspace_root is None:
        return Path.cwd().resolve()
    return Path(workspace_root).resolve()


def _hardware_profile_state_path(workspace_root: Path) -> Path:
    return workspace_root / _HARDWARE_PROFILE_STATE_REL


def _load_hardware_profile_state(path: Path) -> dict[str, Any] | None:
    if not path.exists():
        return None
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        logger.exception("Failed to load hardware profile state from %s", path)
        return None
    if not isinstance(payload, dict):
        return None
    profile_name = str(payload.get("profile", "")).strip()
    if profile_name not in HARDWARE_PROFILES:
        return None
    tuning = payload.get("tuning")
    if not isinstance(tuning, dict):
        return None
    return payload


def _save_hardware_profile_state(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2), encoding="utf-8")


def _build_hardware_profile_payload(detection: dict[str, Any], profile_name: str) -> dict[str, Any]:
    tuning = HARDWARE_PROFILES[profile_name]
    return {
        "profile": profile_name,
        "detection": detection,
        "tuning": tuning.to_dict(),
        "created_at": datetime.now(timezone.utc).isoformat(),
    }


def get_or_create_hardware_profile(workspace_root: Path | str | None = None) -> dict[str, Any]:
    """Load a persisted hardware profile or detect, persist, and return one."""
    root = _resolve_workspace_root(workspace_root)
    state_path = _hardware_profile_state_path(root)
    cached = _load_hardware_profile_state(state_path)
    if cached is not None:
        return cached

    detection = detect_hardware_profile()
    profile_name = str(detection.get("recommended_profile", "cpu_efficient"))
    if profile_name not in HARDWARE_PROFILES:
        profile_name = "cpu_efficient"
    payload = _build_hardware_profile_payload(detection, profile_name)
    _save_hardware_profile_state(state_path, payload)
    return payload


@dataclass(slots=True)
class HardwareIntelligenceSnapshot:
    profile_tier: str
    intelligence_tier: str
    recommended_model_key: str
    recommended_provider: str
    recommended_context_length: int
    ram_gb: float
    gpu_vram_gb: float
    vllm_supported: bool

    def to_dict(self) -> dict[str, Any]:
        return {
            "profile_tier": self.profile_tier,
            "intelligence_tier": self.intelligence_tier,
            "recommended_model_key": self.recommended_model_key,
            "recommended_provider": self.recommended_provider,
            "recommended_context_length": self.recommended_context_length,
            "ram_gb": float(self.ram_gb),
            "gpu_vram_gb": float(self.gpu_vram_gb),
            "vllm_supported": bool(self.vllm_supported),
        }


class HardwareIntelligenceManager:
    """Hardware/model intelligence helper used by AdaptiveIntelligenceManager."""

    def __init__(self, workspace_root: Path | str | None = None) -> None:
        self.workspace_root = Path(workspace_root).resolve() if workspace_root is not None else Path.cwd().resolve()
        catalog_path = self.workspace_root / "lumina_model_catalog.json"
        if not catalog_path.is_file():
            repo_catalog = Path(__file__).resolve().parents[1] / "lumina_model_catalog.json"
            if repo_catalog.is_file():
                catalog_path = repo_catalog
        self.catalog = ModelCatalog(catalog_path)
        self._latest_hardware_snapshot: HardwareSnapshot | None = None
        self._latest_intelligence_snapshot: HardwareIntelligenceSnapshot | None = None

    @staticmethod
    def _canonical_tier(profile_tier: str) -> str:
        normalized = str(profile_tier or "").strip().lower()
        return _LEGACY_TO_CANONICAL_TIER.get(normalized, "light")

    def resolve(self, *, refresh_hardware: bool = False) -> HardwareIntelligenceSnapshot:
        if refresh_hardware:
            hardware = HardwareInspector.capture()
        else:
            hardware = HardwareInspector.load_cached() or HardwareInspector.capture()
        self._latest_hardware_snapshot = hardware

        descriptor: ModelDescriptor = self.catalog.recommended_for(
            ram_gb=hardware.ram_gb,
            gpu_vram_gb=hardware.gpu_vram_gb,
            vllm_supported=hardware.vllm_supported,
        )
        snapshot = HardwareIntelligenceSnapshot(
            profile_tier=str(hardware.profile_tier),
            intelligence_tier=self._canonical_tier(str(hardware.profile_tier)),
            recommended_model_key=descriptor.key,
            recommended_provider=descriptor.recommended_provider,
            recommended_context_length=int(descriptor.context_length),
            ram_gb=float(hardware.ram_gb),
            gpu_vram_gb=float(hardware.gpu_vram_gb),
            vllm_supported=bool(hardware.vllm_supported),
        )
        self._latest_intelligence_snapshot = snapshot
        return snapshot

    def latest(self) -> HardwareIntelligenceSnapshot:
        if self._latest_intelligence_snapshot is None:
            return self.resolve(refresh_hardware=False)
        return self._latest_intelligence_snapshot

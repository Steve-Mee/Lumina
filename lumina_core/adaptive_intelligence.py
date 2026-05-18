from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any

from lumina_core.config_loader import ConfigLoader
from lumina_core.hardware_intelligence import HardwareIntelligenceManager, HardwareIntelligenceSnapshot

_FORCED_MODE_TO_TIER = {
    "force_high": "high",
    "force_standard": "standard",
    "force_light": "light",
}
_VALID_MODES = {"auto", "force_high", "force_standard", "force_light"}


@dataclass(slots=True)
class AdaptiveIntelligenceStatus:
    tier: str
    mode: str
    reasoning_mode: str
    degraded_state: bool
    status_reason: str
    recommended_model: str
    recommended_provider: str
    context_length: int
    last_probe_error: str | None = None

    def to_dict(self) -> dict[str, Any]:
        return {
            "tier": self.tier,
            "mode": self.mode,
            "reasoning_mode": self.reasoning_mode,
            "degraded_state": self.degraded_state,
            "status_reason": self.status_reason,
            "recommended_model": self.recommended_model,
            "recommended_provider": self.recommended_provider,
            "context_length": int(self.context_length),
            "last_probe_error": self.last_probe_error,
        }


def build_status_signature(status: dict[str, Any]) -> tuple[Any, ...]:
    """Stable signature for transition detection and deduplicated publishing."""
    return (
        str(status.get("tier", "")),
        str(status.get("mode", "")),
        str(status.get("reasoning_mode", "")),
        bool(status.get("degraded_state", False)),
        str(status.get("status_reason", "")),
        str(status.get("recommended_model", "")),
        str(status.get("recommended_provider", "")),
        int(status.get("context_length", 0) or 0),
        str(status.get("last_probe_error", "") or ""),
    )


class AdaptiveIntelligenceManager:
    """
    Central intelligence SSOT.

    Public facade for tier/model/provider decisions and degrade state.
    """

    def __init__(self, workspace_root: Path | str | None = None) -> None:
        self.workspace_root = Path(workspace_root).resolve() if workspace_root is not None else Path.cwd().resolve()
        self.hardware_manager = HardwareIntelligenceManager(self.workspace_root)
        self._status: AdaptiveIntelligenceStatus | None = None

    @staticmethod
    def _read_intelligence_mode() -> str:
        cfg = ConfigLoader.get()
        section = cfg.get("intelligence", {}) if isinstance(cfg, dict) else {}
        mode_raw = section.get("mode", "auto") if isinstance(section, dict) else "auto"
        mode = str(mode_raw or "auto").strip().lower()
        return mode if mode in _VALID_MODES else "auto"

    @staticmethod
    def _reasoning_mode_for_tier(tier: str) -> str:
        if tier == "high":
            return "hybrid_deep"
        if tier == "standard":
            return "hybrid_balanced"
        return "fast_path_only"

    def refresh(self, *, refresh_hardware: bool = False) -> AdaptiveIntelligenceStatus:
        mode = self._read_intelligence_mode()
        hardware: HardwareIntelligenceSnapshot = self.hardware_manager.resolve(refresh_hardware=refresh_hardware)
        tier = hardware.intelligence_tier
        status_reason = "auto_hardware_resolution"
        degraded_state = False

        forced_tier = _FORCED_MODE_TO_TIER.get(mode)
        if forced_tier is not None:
            if forced_tier == "high" and hardware.intelligence_tier != "high":
                # Fail-closed fallback: keep running on available tier when hardware cannot satisfy force_high.
                degraded_state = True
                status_reason = "force_high_requested_but_hardware_insufficient"
            else:
                tier = forced_tier
                status_reason = f"forced_mode:{mode}"

        self._status = AdaptiveIntelligenceStatus(
            tier=tier,
            mode=mode,
            reasoning_mode=self._reasoning_mode_for_tier(tier),
            degraded_state=degraded_state,
            status_reason=status_reason,
            recommended_model=hardware.recommended_model_key,
            recommended_provider=hardware.recommended_provider,
            context_length=int(hardware.recommended_context_length),
            last_probe_error=None,
        )
        return self._status

    def report_probe_failure(self, error: Exception | str) -> AdaptiveIntelligenceStatus:
        status = self.get_status()
        status.degraded_state = True
        status.status_reason = "probe_failure"
        status.last_probe_error = str(error)
        if status.tier == "high":
            status.tier = "standard"
            status.reasoning_mode = self._reasoning_mode_for_tier("standard")
        elif status.tier == "standard":
            status.tier = "light"
            status.reasoning_mode = self._reasoning_mode_for_tier("light")
        self._status = status
        return status

    def get_status(self) -> AdaptiveIntelligenceStatus:
        if self._status is None:
            return self.refresh(refresh_hardware=False)
        return self._status

    def to_dict(self) -> dict[str, Any]:
        return self.get_status().to_dict()

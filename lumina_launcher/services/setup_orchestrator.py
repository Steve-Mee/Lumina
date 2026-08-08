"""Smart setup run orchestration and completion persistence."""

from __future__ import annotations

from typing import TYPE_CHECKING

import yaml

from lumina_core.config_loader import ConfigLoader
from lumina_core.config.atomic_yaml import atomic_write_yaml
from lumina_core.logging_utils import get_logger
from lumina_launcher.services import setup_detector
from lumina_launcher.services.setup_compat import HardwareInspector

if TYPE_CHECKING:
    from lumina_launcher.services.smart_setup_service import SmartSetupService

logger = get_logger(__name__)


def apply_intelligence_mode(service: SmartSetupService, force_high: bool) -> None:
    config_path = service.workspace_root / "config.yaml"
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
    atomic_write_yaml(config_path, payload)
    ConfigLoader.invalidate()
    logger.info("smart_setup.intelligence_mode mode=%s", intelligence["mode"])


def mark_setup_complete(service: SmartSetupService) -> None:
    intelligence_status = service._intelligence_manager.get_status()
    hardware_intel = service._intelligence_manager.hardware_manager.latest()
    descriptor = setup_detector.resolve_descriptor(
        service, intelligence_status, hardware_intel.to_dict()
    )
    hardware_snapshot = HardwareInspector.capture()
    service._setup_service.mark_complete(hardware=hardware_snapshot, model=descriptor)
    existing = service._setup_service.load_status()
    merged = {
        **existing,
        "smart_setup": True,
        "adaptive_intelligence": intelligence_status.to_dict(),
        "hardware_tier": hardware_intel.intelligence_tier,
        "recommended_model": descriptor.key,
    }
    service._setup_service.save_status(merged)
    logger.info(
        "smart_setup.mark_complete tier=%s model=%s",
        intelligence_status.tier,
        descriptor.key,
    )

from lumina_launcher.services.setup_orchestrator_run import complete_run, finalize_run, run_smart_setup  # noqa: F401, E402

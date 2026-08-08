"""Smart setup run helpers (M5)."""
from __future__ import annotations

import logging
from typing import TYPE_CHECKING, Any

from lumina_core.engine.model_catalog import ModelDescriptor
from lumina_launcher.services import setup_detector
from lumina_launcher.services.ollama_installer import manual_steps_for_model
from lumina_launcher.services.setup_compat import HardwareInspector
from lumina_launcher.services.setup_progress import emit_progress
from lumina_launcher.services.setup_schemas import (
    SetupProgressCallback,
    SmartSetupOptions,
    SmartSetupResult,
)

if TYPE_CHECKING:
    from lumina_launcher.services.smart_setup_service import SmartSetupService

logger = logging.getLogger(__name__)


def _s():
    from lumina_launcher.services import setup_orchestrator as s

    return s

def complete_run(
    service: SmartSetupService,
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
        _s().mark_setup_complete(service)
    else:
        existing = service._setup_service.load_status()
        service._setup_service.save_status(
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
    emit_progress(
        on_progress,
        phase="complete",
        message=complete_message,
        level="warning" if degraded else "info",
        detail={"recommended_model": descriptor.key, "degraded": degraded},
    )
    status = setup_detector.get_setup_status(service)
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

def finalize_run(
    service: SmartSetupService,
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
    emit_progress(
        on_progress,
        phase="failed",
        message=failure_message,
        level="error",
        detail={"success": False},
    )
    service._setup_service.save_status(
        {
            "steps": steps,
            "adaptive_intelligence": intelligence,
            "smart_setup": False,
            "degraded": degraded,
            "warnings": warnings,
        }
    )
    status = setup_detector.get_setup_status(service)
    logger.warning("smart_setup.complete success=False detail=%s", failure_message)
    return SmartSetupResult(
        success=success,
        steps=steps,
        status=status,
        degraded=degraded,
        warnings=warnings,
        manual_steps=manual_steps,
    )

def run_smart_setup(
    service: SmartSetupService,
    *,
    on_progress: SetupProgressCallback | None = None,
    options: SmartSetupOptions | None = None,
    mark_complete: bool = False,
) -> SmartSetupResult:
    steps: list[dict[str, Any]] = []
    warnings: list[str] = []
    manual_steps: list[dict[str, Any]] = []
    degraded = False
    opts = options if options is not None else service.default_options()
    _s().apply_intelligence_mode(service, opts.force_high_tier)

    intelligence_status = service._intelligence_manager.refresh(refresh_hardware=True)
    intelligence = intelligence_status.to_dict()
    hardware_intel = service._intelligence_manager.hardware_manager.latest()
    descriptor = setup_detector.resolve_descriptor(
        service, intelligence_status, hardware_intel.to_dict()
    )
    provider = str(intelligence.get("recommended_provider", "ollama") or "ollama")
    ollama_required = provider == "ollama"

    emit_progress(
        on_progress,
        phase="detect",
        message=(
            f"Hardware gedetecteerd: tier {intelligence.get('tier')} — "
            f"aanbevolen model {descriptor.display_name} ({provider})"
        ),
        detail={"adaptive_intelligence": intelligence, "hardware": hardware_intel.to_dict()},
    )

    for phase, runner in (
        ("launcher_deps", service._setup_service.install_launcher_dependencies),
        ("runtime_deps", service._setup_service.install_runtime_dependencies),
    ):
        result = runner()
        steps.append(result.to_dict())
        emit_progress(
            on_progress,
            phase=phase,
            message=result.message,
            level="error" if not result.success else "info",
            detail={"success": result.success, "command": result.command},
        )
        logger.info("smart_setup.step name=%s success=%s", result.name, result.success)
        if not result.success:
            return finalize_run(
                service,
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
            ollama_result, ollama_manual = service._install_ollama_subprocess()
            steps.append(ollama_result.to_dict())
            manual_steps.extend(ollama_manual)
            emit_progress(
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
                    return finalize_run(
                        service,
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
            emit_progress(on_progress, phase="ollama", message=skip_ollama, detail={})

        verify_result = service._verify_ollama_runtime()
        steps.append(verify_result.to_dict())
        emit_progress(
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
                return finalize_run(
                    service,
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
            pull_result = service._pull_model_subprocess(descriptor, on_progress=on_progress)
            steps.append(pull_result.to_dict())
            emit_progress(
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
                manual_steps.extend(manual_steps_for_model(descriptor.ollama_tag))
                if not opts.graceful_degrade:
                    return finalize_run(
                        service,
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
            emit_progress(on_progress, phase="model_pull", message=skip_model, detail={})

        if opts.pull_extra_models:
            catalog = service._intelligence_manager.hardware_manager.catalog
            for extra in catalog.upgrade_targets(descriptor.key):
                if extra.recommended_provider != "ollama":
                    continue
                extra_result = service._pull_model_subprocess(extra, on_progress=on_progress)
                steps.append(extra_result.to_dict())
                emit_progress(
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
                        return finalize_run(
                            service,
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
        emit_progress(
            on_progress,
            phase="skipped_vllm_provider",
            message=skip_message,
            detail={"provider": provider},
        )
        logger.info("smart_setup.step name=skipped_vllm_provider success=True")

    hardware_snapshot = HardwareInspector.capture()
    config_result = service._setup_service.apply_recommended_config(
        hardware=hardware_snapshot,
        model=descriptor,
    )
    steps.append(config_result.to_dict())
    emit_progress(
        on_progress,
        phase="config",
        message=config_result.message,
        level="error" if not config_result.success else "info",
        detail={"success": config_result.success, "command": config_result.command},
    )
    logger.info("smart_setup.step name=%s success=%s", config_result.name, config_result.success)
    if not config_result.success:
        return finalize_run(
            service,
            success=False,
            steps=steps,
            intelligence=intelligence,
            on_progress=on_progress,
            failure_message=config_result.message,
            warnings=warnings,
            manual_steps=manual_steps,
            degraded=degraded,
        )

    return complete_run(
        service,
        steps=steps,
        intelligence=intelligence,
        descriptor=descriptor,
        on_progress=on_progress,
        mark_complete=mark_complete,
        degraded=degraded,
        warnings=warnings,
        manual_steps=manual_steps,
    )

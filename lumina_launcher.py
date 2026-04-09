from __future__ import annotations

import base64
import hashlib
import hmac
import json
import os
import secrets
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path
from types import ModuleType
from types import SimpleNamespace
from typing import Any, cast

import pandas as pd
import requests
# ── Headless detection: must precede any Streamlit initialisation ──────────────
_IS_HEADLESS = "--headless" in sys.argv

if not _IS_HEADLESS:
    import streamlit as st  # type: ignore[import]
else:
    st = None  # type: ignore[assignment]  # placeholder; unused in headless path
import yaml

from lumina_core.container import create_application_container
from lumina_core.engine.engine_config import EngineConfig
from lumina_core.engine.hardware_inspector import HardwareInspector, HardwareSnapshot
from lumina_core.engine.lumina_engine import LuminaEngine
from lumina_core.engine.model_catalog import ModelCatalog, ModelDescriptor
from lumina_core.engine.model_trainer import ModelTrainer
from lumina_core.engine.performance_validator import PerformanceValidator
from lumina_core.engine.setup_service import SetupService, SetupStepResult
from lumina_core.runtime_context import RuntimeContext

if not _IS_HEADLESS:
    st.set_page_config(page_title="LUMINA OS Launcher", layout="wide")

ENV_PATH = Path(".env")
CONFIG_PATH = Path("config.yaml")
RUNTIME_ENTRY = Path("lumina_v45.1.1.py")
LUMINA_LOG_PATH = Path("logs/lumina_full_log.csv")
STATE_PATH = Path("state/lumina_sim_state.json")
ADMIN_PASSWORD_HASH_PATH = Path("state/launcher_admin_password.json")
MODEL_CATALOG_STATE_PATH = Path("state/model_catalog_state.json")
SUPPORT_EVENTS_PATH = Path("state/launcher_support_events.jsonl")
BACKEND_BASE_URL = os.getenv("LUMINA_BACKEND_URL", "http://localhost:8000").rstrip("/")


def _load_admin_password_record() -> dict[str, Any] | None:
    if not ADMIN_PASSWORD_HASH_PATH.exists():
        return None
    try:
        payload = json.loads(ADMIN_PASSWORD_HASH_PATH.read_text(encoding="utf-8"))
        if not isinstance(payload, dict):
            return None
        required = {"salt_b64", "hash_b64", "iterations"}
        if not required.issubset(set(payload.keys())):
            return None
        return payload
    except Exception:
        return None


def _derive_password_hash(password: str, salt_bytes: bytes, iterations: int) -> bytes:
    return hashlib.pbkdf2_hmac("sha256", password.encode("utf-8"), salt_bytes, iterations)


def _verify_admin_password(candidate: str) -> bool:
    record = _load_admin_password_record()
    if not record:
        return False
    try:
        salt_bytes = base64.b64decode(str(record.get("salt_b64", "")))
        expected_hash = base64.b64decode(str(record.get("hash_b64", "")))
        iterations = int(record.get("iterations", 0))
    except Exception:
        return False
    if iterations < 100_000 or not salt_bytes or not expected_hash:
        return False
    candidate_hash = _derive_password_hash(candidate, salt_bytes, iterations)
    return hmac.compare_digest(candidate_hash, expected_hash)


def _set_admin_password(new_password: str) -> None:
    salt_bytes = secrets.token_bytes(16)
    iterations = 240_000
    pwd_hash = _derive_password_hash(new_password, salt_bytes, iterations)
    ADMIN_PASSWORD_HASH_PATH.parent.mkdir(parents=True, exist_ok=True)
    payload = {
        "algo": "pbkdf2_sha256",
        "iterations": iterations,
        "salt_b64": base64.b64encode(salt_bytes).decode("ascii"),
        "hash_b64": base64.b64encode(pwd_hash).decode("ascii"),
    }
    ADMIN_PASSWORD_HASH_PATH.write_text(json.dumps(payload, indent=2), encoding="utf-8")


def _parse_env_file(path: Path) -> dict[str, str]:
    if not path.exists():
        return {}
    values: dict[str, str] = {}
    for raw_line in path.read_text(encoding="utf-8").splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        values[key.strip()] = value.strip()
    return values


def _write_env_file(path: Path, updates: dict[str, str]) -> None:
    merged = _parse_env_file(path)
    merged.update({k: str(v) for k, v in updates.items()})
    content = "\n".join(f"{k}={v}" for k, v in sorted(merged.items())) + "\n"
    path.write_text(content, encoding="utf-8")


def _load_yaml_config() -> dict[str, Any]:
    if not CONFIG_PATH.exists():
        return {}
    payload = yaml.safe_load(CONFIG_PATH.read_text(encoding="utf-8"))
    return payload if isinstance(payload, dict) else {}


def _runtime_command() -> list[str]:
    python_cmd = os.getenv("LUMINA_PYTHON", sys.executable)
    return [python_cmd, str(RUNTIME_ENTRY)]


def _process_is_alive() -> bool:
    proc = st.session_state.get("bot_process")
    return proc is not None and proc.poll() is None


def _start_bot_process() -> tuple[bool, str]:
    if not RUNTIME_ENTRY.exists():
        return False, f"Runtime entry not found: {RUNTIME_ENTRY}"
    if _process_is_alive():
        return True, "Bot is already running"
    command = _runtime_command()
    env = os.environ.copy()
    env.setdefault("PYTHONUNBUFFERED", "1")
    try:
        proc = subprocess.Popen(
            command,
            cwd=str(Path.cwd()),
            env=env,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
        )
        st.session_state.bot_process = proc
        return True, f"Bot started (pid={proc.pid})"
    except Exception as exc:
        return False, f"Failed to start bot: {exc}"


def _stop_bot_process() -> tuple[bool, str]:
    proc = st.session_state.get("bot_process")
    if proc is None:
        return True, "No running bot process"
    if proc.poll() is not None:
        st.session_state.bot_process = None
        return True, "Bot process already stopped"
    try:
        proc.terminate()
        proc.wait(timeout=15)
        st.session_state.bot_process = None
        return True, "Bot stopped"
    except Exception as exc:
        return False, f"Failed to stop bot: {exc}"


def _tail_file(path: Path, max_chars: int = 4000) -> str:
    if not path.exists():
        return ""
    text = path.read_text(encoding="utf-8", errors="replace")
    return text[-max_chars:]


def _load_runtime_state() -> dict[str, Any]:
    if not STATE_PATH.exists():
        return {}
    try:
        payload = json.loads(STATE_PATH.read_text(encoding="utf-8"))
        return payload if isinstance(payload, dict) else {}
    except Exception:
        return {}


def _backend_get(path: str, timeout: float = 3.0) -> dict[str, Any]:
    url = f"{BACKEND_BASE_URL}{path}"
    response = requests.get(url, timeout=timeout)
    response.raise_for_status()
    payload = response.json()
    return payload if isinstance(payload, dict) else {}


def _build_validation_context() -> RuntimeContext:
    """Bootstrap a validation-only container via ApplicationContainer (single bootstrap path)."""
    container = create_application_container()
    return container.runtime_context


def _load_catalog_state() -> dict[str, Any]:
    if not MODEL_CATALOG_STATE_PATH.exists():
        return {}
    try:
        payload = json.loads(MODEL_CATALOG_STATE_PATH.read_text(encoding="utf-8"))
        return payload if isinstance(payload, dict) else {}
    except Exception:
        return {}


def _save_catalog_state(catalog: ModelCatalog, current_model_key: str) -> None:
    MODEL_CATALOG_STATE_PATH.parent.mkdir(parents=True, exist_ok=True)
    MODEL_CATALOG_STATE_PATH.write_text(
        json.dumps({"catalog_version": catalog.version(), "current_model_key": current_model_key}, indent=2),
        encoding="utf-8",
    )


def _status_badge(label: str, status: str) -> str:
    palette = {
        "available": "#0f766e",
        "blocked": "#b45309",
        "ready": "#1d4ed8",
        "warning": "#92400e",
        "neutral": "#374151",
    }
    color = palette.get(status, "#374151")
    return (
        f"<span style='display:inline-block;padding:0.2rem 0.55rem;border-radius:999px;"
        f"background:{color};color:white;font-size:0.78rem;font-weight:600;'>{label}</span>"
    )


def _append_support_event(*, event_type: str, payload: dict[str, Any]) -> None:
    SUPPORT_EVENTS_PATH.parent.mkdir(parents=True, exist_ok=True)
    event = {
        "ts_utc": datetime.now(timezone.utc).isoformat(),
        "event_type": event_type,
        **payload,
    }
    with SUPPORT_EVENTS_PATH.open("a", encoding="utf-8") as handle:
        handle.write(json.dumps(event, ensure_ascii=True) + "\n")


def _render_guarded_action_button(
    *,
    label: str,
    allowed: bool,
    reason: str,
    command: list[str],
    trainer: ModelTrainer,
    current_model: ModelDescriptor,
    snapshot: HardwareSnapshot,
    action_key: str,
) -> None:
    if st.button(label, use_container_width=True):
        if not allowed:
            _append_support_event(
                event_type="blocked_launcher_action",
                payload={
                    "action": action_key,
                    "reason": reason,
                    "hardware_tier": snapshot.profile_tier,
                    "os": snapshot.os_name,
                    "gpu": snapshot.gpu_name or "unknown",
                    "gpu_vram_gb": snapshot.gpu_vram_gb,
                    "ram_gb": snapshot.ram_gb,
                    "model_key": current_model.key,
                    "model_tag": current_model.ollama_tag,
                },
            )
            st.warning(f"{label} is blocked: {reason}")
            st.caption(f"Support event logged to {SUPPORT_EVENTS_PATH}")
            return
        ok, output = trainer.run_command(command)
        if ok:
            st.success(output)
        else:
            st.error(output)


def _find_model_key_for_reasoning_model(catalog: ModelCatalog, config_payload: dict[str, Any]) -> str:
    models = config_payload.get("models", {}) if isinstance(config_payload.get("models"), dict) else {}
    reasoning_model = str(models.get("reasoning", "")).strip()
    for descriptor in catalog.models():
        if descriptor.ollama_tag == reasoning_model or descriptor.key == reasoning_model:
            return descriptor.key
    return catalog.models()[0].key


def _refresh_hardware_snapshot() -> HardwareSnapshot:
    snapshot = HardwareInspector.capture()
    st.session_state["hardware_snapshot"] = snapshot
    return snapshot


def _get_hardware_snapshot() -> HardwareSnapshot:
    snapshot = st.session_state.get("hardware_snapshot")
    if isinstance(snapshot, HardwareSnapshot):
        return snapshot
    cached = HardwareInspector.load_cached()
    if cached is not None:
        st.session_state["hardware_snapshot"] = cached
        return cached
    return _refresh_hardware_snapshot()


def _render_step_result(result: SetupStepResult) -> None:
    if result.success:
        st.success(f"{result.name}: {result.message}")
    else:
        st.error(f"{result.name}: {result.message}")
    if result.command:
        st.caption(result.command)


def _render_tier_requirements(snapshot: HardwareSnapshot) -> None:
    rows: list[dict[str, Any]] = []
    for tier, requirements in HardwareInspector.tier_requirements().items():
        rows.append(
            {
                "Tier": tier,
                "RAM Needed (GB)": requirements["ram_gb"],
                "VRAM Needed (GB)": requirements["gpu_vram_gb"],
                "Primary Provider": requirements["provider"],
                "Best Model": requirements["best_model_key"],
                "Current Machine Fits": "yes"
                if snapshot.ram_gb >= requirements["ram_gb"] and snapshot.gpu_vram_gb >= requirements["gpu_vram_gb"]
                else "no",
            }
        )
    st.dataframe(pd.DataFrame(rows), use_container_width=True)


def _render_hardware_summary(snapshot: HardwareSnapshot, recommended: ModelDescriptor) -> None:
    st.subheader("Hardware Snapshot")
    col1, col2, col3, col4 = st.columns(4)
    col1.metric("Hardware Tier", snapshot.profile_tier.upper())
    col2.metric("RAM", f"{snapshot.ram_gb:.1f} GB")
    col3.metric("GPU VRAM", f"{snapshot.gpu_vram_gb:.1f} GB")
    col4.metric("Recommended Model", recommended.display_name)
    st.write(
        {
            "os": snapshot.os_name,
            "cpu": snapshot.cpu_name,
            "cpu_physical_cores": snapshot.cpu_cores_physical,
            "cpu_logical_cores": snapshot.cpu_cores_logical,
            "gpu": snapshot.gpu_name or "No NVIDIA GPU detected",
            "compute_capability": snapshot.compute_capability,
            "ollama_installed": snapshot.ollama_installed,
            "ollama_running": snapshot.ollama_running,
            "vllm_supported": snapshot.vllm_supported,
        }
    )
    for note in snapshot.notes:
        st.info(note)
    st.write("What you need for better variants")
    _render_tier_requirements(snapshot)


def _run_guided_setup(
    *,
    setup_service: SetupService,
    snapshot: HardwareSnapshot,
    recommended_model: ModelDescriptor,
    install_unsloth: bool,
    admin_password: str,
) -> list[SetupStepResult]:
    results: list[SetupStepResult] = []
    results.append(setup_service.install_launcher_dependencies())
    results.append(setup_service.install_runtime_dependencies())
    results.append(setup_service.ensure_ollama())
    if results[-1].success:
        results.append(setup_service.pull_model(recommended_model))
    results.append(setup_service.apply_recommended_config(hardware=snapshot, model=recommended_model))
    if install_unsloth:
        results.append(setup_service.install_unsloth_dependencies())
    if admin_password and len(admin_password) >= 12:
        _set_admin_password(admin_password)
        results.append(SetupStepResult("admin_password", True, "Admin password configured"))
    elif admin_password:
        results.append(SetupStepResult("admin_password", False, "Admin password must be at least 12 characters"))
    setup_service.save_status({"steps": [result.to_dict() for result in results]})
    required_ok = all(
        result.success
        for result in results
        if result.name in {"launcher_dependencies", "runtime_dependencies", "ollama", "model_pull", "config_update"}
    )
    if required_ok:
        setup_service.mark_complete(hardware=snapshot, model=recommended_model)
    return results


def _render_setup_wizard(setup_service: SetupService, catalog: ModelCatalog) -> None:
    st.title("LUMINA OS - First Use Setup")
    st.markdown("Deze wizard maakt een nieuwe machine klaar voor de launcher, inference en toekomstig modelbeheer.")
    snapshot = _get_hardware_snapshot()
    recommended_model = catalog.recommended_for(
        ram_gb=snapshot.ram_gb,
        gpu_vram_gb=snapshot.gpu_vram_gb,
        vllm_supported=snapshot.vllm_supported,
    )
    _render_hardware_summary(snapshot, recommended_model)
    st.subheader("Recommended installation plan")
    st.write(
        {
            "provider": recommended_model.recommended_provider,
            "model": recommended_model.display_name,
            "ollama_tag": recommended_model.ollama_tag,
            "context_length": recommended_model.context_length,
            "supports_unsloth": recommended_model.supports_unsloth,
        }
    )
    install_unsloth = st.checkbox(
        "Install optional Unsloth fine-tuning dependencies",
        value=False,
        help="Only useful on Linux/WSL2 with CUDA. On Windows this normally remains a future step.",
    )
    admin_password = st.text_input(
        "Initial Admin Password",
        type="password",
        help="Optional but strongly recommended during first setup.",
    )
    if st.button("Run Guided Installation", type="primary", use_container_width=True):
        results = _run_guided_setup(
            setup_service=setup_service,
            snapshot=snapshot,
            recommended_model=recommended_model,
            install_unsloth=install_unsloth,
            admin_password=admin_password,
        )
        for result in results:
            _render_step_result(result)
        if all(result.success for result in results if result.name != "unsloth_dependencies"):
            st.success("Guided setup completed. Rerun the launcher if newly installed packages were added to the environment.")
    previous_status = setup_service.load_status()
    if previous_status:
        st.subheader("Last setup run")
        steps = previous_status.get("steps", [])
        if isinstance(steps, list) and steps:
            st.dataframe(pd.DataFrame(steps), use_container_width=True)
    st.info("If package installation changed the environment, rerun Streamlit once so the launcher loads those packages cleanly.")
    st.stop()


def _render_hardware_tab(snapshot: HardwareSnapshot, catalog: ModelCatalog, current_model: ModelDescriptor) -> None:
    recommended = catalog.recommended_for(
        ram_gb=snapshot.ram_gb,
        gpu_vram_gb=snapshot.gpu_vram_gb,
        vllm_supported=snapshot.vllm_supported,
    )
    hardware_fit_badge = _status_badge(snapshot.profile_tier.upper(), "ready")
    ollama_badge = _status_badge("Ready" if snapshot.ollama_running else "Needs Attention", "available" if snapshot.ollama_running else "warning")
    vllm_badge = _status_badge("Ready" if snapshot.vllm_supported else "Blocked", "available" if snapshot.vllm_supported else "blocked")
    st.markdown(f"Hardware Tier {hardware_fit_badge}", unsafe_allow_html=True)
    st.markdown(f"Ollama Runtime {ollama_badge}", unsafe_allow_html=True)
    st.markdown(f"vLLM Path {vllm_badge}", unsafe_allow_html=True)
    _render_hardware_summary(snapshot, recommended)
    if st.button("Refresh Hardware Scan", use_container_width=True, key="refresh_hardware_scan"):
        refreshed = _refresh_hardware_snapshot()
        st.success(f"Hardware scan refreshed: {refreshed.profile_tier}")
        st.rerun()
    st.subheader("Current model alignment")
    alignment_badge = _status_badge(
        "Recommended" if current_model.key == recommended.key else "Upgrade Suggested",
        "available" if current_model.key == recommended.key else "warning",
    )
    st.markdown(f"Model Alignment {alignment_badge}", unsafe_allow_html=True)
    st.write(
        {
            "current_model": current_model.display_name,
            "recommended_model": recommended.display_name,
            "provider": recommended.recommended_provider,
        }
    )


def _render_model_management_tab(
    *,
    setup_service: SetupService,
    catalog: ModelCatalog,
    snapshot: HardwareSnapshot,
    current_model: ModelDescriptor,
) -> None:
    installed_models = ModelCatalog.installed_ollama_models()
    recommended_model = catalog.recommended_for(
        ram_gb=snapshot.ram_gb,
        gpu_vram_gb=snapshot.gpu_vram_gb,
        vllm_supported=snapshot.vllm_supported,
    )
    st.subheader("Model Management")
    current_badge = _status_badge(current_model.recommended_tier.upper(), "ready")
    recommended_badge = _status_badge(
        "Installed" if recommended_model.ollama_tag in installed_models else "Not Installed",
        "available" if recommended_model.ollama_tag in installed_models else "warning",
    )
    upgrade_badge = _status_badge(
        "On Track" if current_model.key == recommended_model.key else "Heavier Option Available",
        "available" if current_model.key == recommended_model.key else "warning",
    )
    st.markdown(f"Current Tier Target {current_badge}", unsafe_allow_html=True)
    st.markdown(f"Recommended Model Status {recommended_badge}", unsafe_allow_html=True)
    st.markdown(f"Upgrade Outlook {upgrade_badge}", unsafe_allow_html=True)
    st.write(
        {
            "catalog_version": catalog.version(),
            "current_model": current_model.display_name,
            "installed_ollama_models": installed_models,
            "recommended_model": recommended_model.display_name,
        }
    )
    rows = [
        {
            "Key": model.key,
            "Name": model.display_name,
            "Tier": model.recommended_tier,
            "Provider": model.recommended_provider,
            "Min RAM GB": model.ram_min_gb,
            "Min VRAM GB": model.vram_min_gb,
            "Tested": model.tested_by_lumina,
        }
        for model in catalog.models()
    ]
    st.dataframe(pd.DataFrame(rows), use_container_width=True)
    upgrade_targets = catalog.upgrade_targets(current_model.key)
    if not upgrade_targets:
        st.info("No higher upgrade targets registered for the current model.")
    else:
        target_labels = {f"{item.display_name} ({item.ollama_tag})": item.key for item in upgrade_targets}
        selected_label = st.selectbox("Upgrade target", list(target_labels.keys()))
        selected_model = catalog.get(target_labels[selected_label])
        if selected_model is not None:
            fits_hardware = snapshot.ram_gb >= selected_model.ram_min_gb and snapshot.gpu_vram_gb >= selected_model.vram_min_gb
            if fits_hardware:
                st.success("This upgrade fits the current machine.")
            else:
                st.warning("This upgrade is heavier than the current machine recommendation. The launcher still shows what hardware is needed.")
            st.write(selected_model.upgrade_notes)
            if st.button("Install or Upgrade Selected Model", type="primary", use_container_width=True):
                results = setup_service.upgrade_model(selected_model)
                for result in results:
                    _render_step_result(result)
                _save_catalog_state(catalog, selected_model.key)
    if st.button("Install Recommended Model For This Hardware", use_container_width=True):
        results = setup_service.upgrade_model(recommended_model)
        for result in results:
            _render_step_result(result)
        _save_catalog_state(catalog, recommended_model.key)


def _render_training_panel(current_model: ModelDescriptor, snapshot: HardwareSnapshot) -> None:
    trainer = ModelTrainer()
    report = trainer.inspect_environment()
    pipeline = trainer.build_full_pipeline_commands(
        base_model=current_model.ollama_tag,
        output_dir=Path("state/unsloth-output"),
        model_name="lumina-qwen-custom",
    )
    llama_cpp = trainer.inspect_llama_cpp_toolchain()
    gate = trainer.action_gate_status(
        gguf_path=Path(str(pipeline["gguf"])),
        modelfile_path=Path(str(pipeline["modelfile"])),
    )
    st.subheader("Unsloth Fine-Tuning")
    st.write(report.to_dict())
    if report.supported:
        st.success("Training environment supports the next Unsloth step.")
    else:
        for reason in report.reasons:
            st.warning(reason)
    if st.button("Build Dataset Preview", use_container_width=True):
        preview_path = trainer.build_training_dataset()
        st.success(f"Dataset preview written to {preview_path}")
    preview_path = Path("state/finetune_dataset_preview.jsonl")
    if preview_path.exists():
        st.code(preview_path.read_text(encoding="utf-8", errors="replace")[:4000])
    st.write("Prepared training, export, and registration commands")
    st.code(" ".join(pipeline["train"]))
    st.code(" ".join(pipeline["export"]))
    st.code(" ".join(pipeline["register"]))
    st.caption(f"Modelfile: {pipeline['modelfile']}")
    st.caption(f"GGUF target: {pipeline['gguf']}")
    st.write("llama.cpp toolchain")
    st.write(llama_cpp)
    prepare_badge = _status_badge("Available" if gate["can_prepare_toolchain"] else "Blocked", "available" if gate["can_prepare_toolchain"] else "blocked")
    export_badge = _status_badge("Available" if gate["can_export"] else "Blocked", "available" if gate["can_export"] else "blocked")
    register_badge = _status_badge("Ready" if gate["can_register"] else "Blocked", "ready" if gate["can_register"] else "blocked")
    if not gate["linux_or_wsl2"]:
        st.info("Toolchain, export, and registration actions are blocked on this runtime. Use Linux or WSL2 to continue.")
    st.markdown(f"Prepare llama.cpp Toolchain {prepare_badge}", unsafe_allow_html=True)
    _render_guarded_action_button(
        label="Prepare llama.cpp Toolchain",
        allowed=bool(gate["can_prepare_toolchain"]),
        reason=str(gate["prepare_reason"]),
        command=list(llama_cpp["setup_command"]),
        trainer=trainer,
        current_model=current_model,
        snapshot=snapshot,
        action_key="prepare_llama_cpp_toolchain",
    )
    st.caption(str(gate["prepare_reason"]))
    st.markdown(f"Run GGUF Export {export_badge}", unsafe_allow_html=True)
    _render_guarded_action_button(
        label="Run GGUF Export",
        allowed=bool(gate["can_export"]),
        reason=str(gate["export_reason"]),
        command=list(pipeline["export"]),
        trainer=trainer,
        current_model=current_model,
        snapshot=snapshot,
        action_key="run_gguf_export",
    )
    st.caption(str(gate["export_reason"]))
    st.markdown(f"Register Model In Ollama {register_badge}", unsafe_allow_html=True)
    _render_guarded_action_button(
        label="Register Model In Ollama",
        allowed=bool(gate["can_register"]),
        reason=str(gate["register_reason"]),
        command=list(pipeline["register"]),
        trainer=trainer,
        current_model=current_model,
        snapshot=snapshot,
        action_key="register_model_in_ollama",
    )
    st.caption(str(gate["register_reason"]))
    st.write("What still depends on the correct environment")
    for instruction in trainer.create_export_instructions(base_model=current_model.ollama_tag, output_dir=Path("state/unsloth-output")):
        st.write(f"- {instruction}")


# ── Headless entry point (injected before Streamlit UI body) ───────────────────
# ── Headless helpers ──────────────────────────────────────────────────────────

def _parse_duration_minutes(value: str) -> float:
    """Parse "15m", "5m", "30s", "1h" → float minutes."""
    from lumina_core.runtime.headless_runtime import parse_duration_minutes
    return parse_duration_minutes(value)


def _headless_main() -> None:
    """
    CLI entry point for headless paper/live-mock trade-loop validation.

    Invoked when ``--headless`` is present in sys.argv.  Parses the remaining
    flags, creates an ApplicationContainer (best-effort), and delegates to
    HeadlessRuntime.run().  The structured JSON summary is printed to stdout
    and persisted to state/last_run_summary.json.

    Usage::

        python -m lumina_launcher --headless --mode=paper --duration=15m --broker=paper
        python -m lumina_launcher --headless --mode=paper --duration=5m  --broker=live
    """
    import argparse
    import logging

    from lumina_core.runtime.headless_runtime import HeadlessRuntime

    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(name)s: %(message)s")

    headless_cfg = _load_yaml_config().get("headless", {})
    if not isinstance(headless_cfg, dict):
        headless_cfg = {}

    raw_duration = headless_cfg.get("default_duration_minutes", 15)
    try:
        duration_value = float(raw_duration)
    except (TypeError, ValueError):
        duration_value = 15.0
    default_duration = f"{int(duration_value)}m" if duration_value.is_integer() else f"{duration_value}m"

    raw_mode = str(headless_cfg.get("default_mode", "paper")).strip().lower()
    default_mode = raw_mode if raw_mode in {"paper", "sim", "real"} else "paper"

    raw_broker = str(headless_cfg.get("default_broker", "paper")).strip().lower()
    default_broker = raw_broker if raw_broker in {"paper", "live"} else "paper"

    parser = argparse.ArgumentParser(
        prog="lumina_launcher",
        description="LUMINA OS Launcher – headless trade-loop validation mode",
    )
    parser.add_argument(
        "--headless",
        action="store_true",
        default=False,
        help="Run in headless (non-UI) mode; output structured JSON summary.",
    )
    parser.add_argument(
        "--mode",
        choices=["paper", "sim", "real"],
        default=default_mode,
        help=f"Trading mode (default: {default_mode}).",
    )
    parser.add_argument(
        "--duration",
        default=default_duration,
        metavar="DURATION",
        help=f"Simulated session length, e.g. 15m, 5m, 1h (default: {default_duration}).",
    )
    parser.add_argument(
        "--broker",
        choices=["paper", "live"],
        default=default_broker,
        help=f"Broker backend to validate: paper or live (default: {default_broker}).",
    )
    parser.add_argument(
        "--aggressive-sim",
        action="store_true",
        default=False,
        help="Enable aggressive SIM learning profile (extended duration + elevated proposal cadence).",
    )

    args, _ = parser.parse_known_args()

    # CLI mode override: writes runtime mode into process env for downstream
    # services that resolve mode from config/env.
    os.environ["LUMINA_MODE"] = str(args.mode).strip().lower()
    os.environ["LUMINA_AGGRESSIVE_SIM"] = "true" if bool(args.aggressive_sim) else "false"

    duration_minutes = _parse_duration_minutes(args.duration)

    # Suppress TTS and voice in headless mode.
    os.environ.setdefault("VOICE_ENABLED", "False")

    # For live-broker validation without real credentials, inject a stub token
    # so the container config-validation gate does not reject the init.
    if args.broker == "live":
        os.environ.setdefault("CROSSTRADE_TOKEN", "headless-validation-stub")

    # Optional: try to initialise the full ApplicationContainer for richer
    # metrics.  Most environments (CI, Docker sandbox) will succeed for paper
    # mode; live mode may fail the connectivity check but the simulation still
    # runs (broker_status reflects the outcome).
    container = None
    try:
        container = create_application_container()
    except Exception as exc:  # noqa: BLE001
        logging.getLogger("lumina.launcher").warning(
            "Container init skipped in headless mode (%s: %s). "
            "Running with lightweight simulation only.",
            type(exc).__name__,
            exc,
        )

    runtime = HeadlessRuntime(container=container)
    runtime.run(
        duration_minutes=duration_minutes,
        mode=args.mode,
        broker_mode=args.broker,
        aggressive_sim=bool(args.aggressive_sim),
    )


# ── Headless entry point (injected before Streamlit UI body) ───────────────────
if _IS_HEADLESS:
    _headless_main()
    sys.exit(0)

setup_service = SetupService(config_path=CONFIG_PATH, env_path=ENV_PATH)
catalog = ModelCatalog()
if setup_service.is_first_run():
    _render_setup_wizard(setup_service, catalog)

snapshot = _get_hardware_snapshot()
config_payload = _load_yaml_config()
current_model_key = _find_model_key_for_reasoning_model(catalog, config_payload)
current_model = catalog.get(current_model_key) or catalog.models()[0]
catalog_state = _load_catalog_state()
if catalog_state.get("catalog_version") != catalog.version():
    _save_catalog_state(catalog, current_model.key)

st.title("LUMINA OS - Start Screen")
st.markdown("**Trading runtime, guided setup, hardware-aware model selection, and future-ready fine-tuning in one control plane.**")

with st.sidebar:
    st.header("Bot Configuration")
    trade_mode = st.selectbox(
        "Trading Mode",
        options=["paper", "sim", "real"],
        index=0,
        help="Paper = simulatie | Sim = demo account | Real = echt geld",
    )
    risk_profile = st.selectbox("Risk Profile", options=["Conservative", "Balanced", "Aggressive"], index=1)
    instrument = st.selectbox("Instrument", options=["MES JUN26", "MNQ JUN26", "MYM JUN26", "ES JUN26"], index=0)
    voice_enabled = st.checkbox("Voice (TTS + input)", value=True)
    screen_share_enabled = st.checkbox("Live Chart Screen Share", value=True)
    dashboard_enabled = st.checkbox("Dashboard", value=True)
    st.divider()
    if st.button("Save Config and Start Bot", type="primary", use_container_width=True):
        cfg_updates = {
            "TRADE_MODE": trade_mode,
            "LUMINA_RISK_PROFILE": risk_profile.lower(),
            "INSTRUMENT": instrument,
            "VOICE_ENABLED": str(voice_enabled).lower(),
            "SCREEN_SHARE_ENABLED": str(screen_share_enabled).lower(),
            "DASHBOARD_ENABLED": str(dashboard_enabled).lower(),
        }
        _write_env_file(ENV_PATH, cfg_updates)
        ok, msg = _start_bot_process()
        if ok:
            st.success(msg)
        else:
            st.error(msg)
    if st.button("Stop Bot", use_container_width=True):
        ok, msg = _stop_bot_process()
        if ok:
            st.info(msg)
        else:
            st.error(msg)
    st.divider()
    st.subheader("Current Hardware")
    recommended_model = catalog.recommended_for(
        ram_gb=snapshot.ram_gb,
        gpu_vram_gb=snapshot.gpu_vram_gb,
        vllm_supported=snapshot.vllm_supported,
    )
    st.caption(f"Tier: {snapshot.profile_tier} | GPU VRAM: {snapshot.gpu_vram_gb:.1f} GB | RAM: {snapshot.ram_gb:.1f} GB")
    st.caption(f"Recommended model: {recommended_model.display_name}")
    st.divider()
    st.subheader("Admin Access")
    if "admin_authenticated" not in st.session_state:
        st.session_state.admin_authenticated = False
    admin_record_exists = _load_admin_password_record() is not None
    if not admin_record_exists:
        st.warning("Admin password is not configured")
    else:
        admin_password_input = st.text_input("Admin Password", type="password", key="admin_access_password")
        col_admin_a, col_admin_b = st.columns(2)
        if col_admin_a.button("Unlock", use_container_width=True):
            if _verify_admin_password(admin_password_input):
                st.session_state.admin_authenticated = True
                st.success("Admin unlocked")
            else:
                st.error("Invalid admin password")
        if col_admin_b.button("Lock", use_container_width=True):
            st.session_state.admin_authenticated = False
            st.info("Admin locked")
    admin_mode = bool(st.session_state.get("admin_authenticated", False))
    st.caption(f"Mode: {'Admin' if admin_mode else 'User'}")

alive = _process_is_alive()
if alive:
    bot_proc = st.session_state.get("bot_process")
    pid = getattr(bot_proc, "pid", "unknown")
    st.success(f"BOT IS LIVE - pid={pid}")
else:
    st.info("Configureer links in de sidebar en klik op START BOT om te beginnen.")

st.info(
    f"This machine is {snapshot.profile_tier.upper()}. Sweet requires 32 GB RAM and 8 GB VRAM; beast requires 64 GB RAM, 20 GB VRAM, and Linux or WSL2 CUDA support for vLLM and Unsloth."
)

state = _load_runtime_state()
current_dream = state.get("current_dream", {}) if isinstance(state.get("current_dream"), dict) else {}
tab_labels = [
    "Live Trader View",
    "Hardware & Install",
    "Model Management",
    "Trader League",
    "Community Bibles",
    "Performance Reports",
]
if admin_mode:
    tab_labels.append("Admin / Backend")
tabs = st.tabs(tab_labels)
tab1 = tabs[0]
tab2 = tabs[1]
tab3 = tabs[2]
tab4 = tabs[3]
tab5 = tabs[4]
tab6 = tabs[5]
tab7 = tabs[6] if admin_mode and len(tabs) > 6 else None

with tab1:
    st.subheader("Live Dream + Runtime State")
    if current_dream:
        st.json(current_dream)
    else:
        st.info("Nog geen runtime state gevonden in state/lumina_sim_state.json")
    col1, col2, col3 = st.columns(3)
    col1.metric("Sim Position Qty", value=state.get("sim_position_qty", 0))
    col2.metric("Live Position Qty", value=state.get("live_position_qty", 0))
    col3.metric("Pending Reconciliations", value=len(state.get("pending_trade_reconciliations", []) or []))

with tab2:
    _render_hardware_tab(snapshot, catalog, current_model)

with tab3:
    _render_model_management_tab(setup_service=setup_service, catalog=catalog, snapshot=snapshot, current_model=current_model)

with tab4:
    st.subheader("Trader League Leaderboard")
    try:
        leaderboard_payload = _backend_get("/leaderboard")
        leaderboard = leaderboard_payload.get("leaderboard", [])
        if isinstance(leaderboard, list) and leaderboard:
            st.dataframe(pd.DataFrame(leaderboard), use_container_width=True)
        else:
            st.info("Leaderboard is leeg")
    except Exception as exc:
        st.info(f"Leaderboard backend nog niet gestart ({exc})")

with tab5:
    st.subheader("Global Community Bibles")
    try:
        wisdom_payload = _backend_get("/global_wisdom")
        top_bibles = wisdom_payload.get("top_bibles", [])
        if isinstance(top_bibles, list) and top_bibles:
            st.dataframe(pd.DataFrame(top_bibles), use_container_width=True)
        else:
            st.info("Nog geen community bible data")
    except Exception as exc:
        st.info(f"Community backend nog niet gestart ({exc})")

with tab6:
    st.subheader("Ultimate Performance Validation")
    if st.button("Run 3-Year Validation Now"):
        try:
            runtime_context = _build_validation_context()
            validator = PerformanceValidator(engine=runtime_context.engine)  # engine via ApplicationContainer
            report = validator.run_3year_validation()
            st.json(report)
        except Exception as exc:
            st.error(f"Validation failed: {exc}")
    reports_dir = Path("journal/reports")
    if reports_dir.exists():
        files = sorted([p.name for p in reports_dir.iterdir() if p.is_file()], reverse=True)
        if files:
            st.write("Recent reports:")
            st.write("\n".join(files[:10]))

if tab7 is not None:
    with tab7:
        st.subheader("Admin Backend")
        st.write("Runtime entry:")
        st.code(str(RUNTIME_ENTRY))
        st.write("Log tail (lumina_full_log.csv):")
        log_tail = _tail_file(LUMINA_LOG_PATH, max_chars=6000)
        if log_tail:
            st.code(log_tail)
        else:
            st.info("Nog geen logdata gevonden")
        st.divider()
        support_log_tail = _tail_file(SUPPORT_EVENTS_PATH, max_chars=4000)
        if support_log_tail:
            st.write("Recent blocked action support log:")
            st.code(support_log_tail)
            st.caption(str(SUPPORT_EVENTS_PATH))
        _render_training_panel(current_model, snapshot)
        st.divider()
        st.write("Wijzig admin wachtwoord")
        current_password = st.text_input("Current Password", type="password", key="admin_pwd_current")
        new_password = st.text_input("New Password", type="password", key="admin_pwd_new")
        confirm_password = st.text_input("Confirm New Password", type="password", key="admin_pwd_confirm")
        if st.button("Update Admin Password", use_container_width=True):
            if not _verify_admin_password(current_password):
                st.error("Current password is incorrect")
            elif len(new_password) < 12:
                st.error("New password must be at least 12 characters")
            elif new_password != confirm_password:
                st.error("New password confirmation does not match")
            else:
                _set_admin_password(new_password)
                st.success("Admin wachtwoord is bijgewerkt")

st.caption("LUMINA OS v3.6 - guided setup, hardware-aware models, and future-ready fine-tuning.")

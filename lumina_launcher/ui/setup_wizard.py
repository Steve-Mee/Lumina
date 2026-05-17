"""Guided first-run setup wizard for the Streamlit launcher."""

from __future__ import annotations

import secrets
from pathlib import Path
from typing import Any

import streamlit as st

from lumina_core.config_loader import ConfigLoader
from lumina_core.engine.setup_service import SetupService
from lumina_launcher.core.admin_auth import AdminAuth
from lumina_launcher.core.config_manager import ConfigManager
from lumina_launcher.core.first_boot import FirstBootManager
from lumina_launcher.services.hardware_service import HardwareService
from lumina_launcher.services.model_service import ModelService

_WIZARD_STATE_KEY = "lumina_setup_wizard_state"
_WIZARD_STEP_KEY = "lumina_setup_wizard_step"
_WIZARD_STEPS = ("welcome", "credentials", "mode", "model", "training", "review")


def resolve_mode_matrix(selection: str) -> tuple[str, str]:
    normalized = str(selection or "paper").strip().lower()
    if normalized == "paper":
        return "paper", "paper"
    if normalized in {"sim", "sim_real_guard", "real"}:
        return normalized, "live"
    return "paper", "paper"


def persist_setup_configuration(
    *,
    workspace_root: Path,
    setup_service: SetupService,
    config_manager: ConfigManager,
    first_boot_manager: FirstBootManager,
    model_service: ModelService,
    snapshot: Any,
    selected_model_key: str,
    mode_selection: str,
    credentials: dict[str, str],
    training: dict[str, Any],
    admin_password: str = "",
) -> list[dict[str, Any]]:
    mode_value, broker_backend = resolve_mode_matrix(mode_selection)
    admin_api_key = str(credentials.get("LUMINA_ADMIN_API_KEY", "")).strip() or f"sk_{secrets.token_hex(32)}"
    env_updates = {
        "TRADE_MODE": mode_value,
        "LUMINA_MODE": mode_value,
        "BROKER_BACKEND": broker_backend,
        "LUMINA_ADMIN_API_KEY": admin_api_key,
    }
    for key in (
        "CROSSTRADE_TOKEN",
        "CROSSTRADE_ACCOUNT",
        "XAI_API_KEY",
        "TELEGRAM_BOT_TOKEN",
        "TELEGRAM_CHAT_ID",
        "LUMINA_JWT_SECRET_KEY",
    ):
        value = str(credentials.get(key, "")).strip()
        if value:
            env_updates[key] = value

    steps: list[dict[str, Any]] = []
    config_manager.write_env_file(env_updates)
    steps.append({"name": "env_update", "success": True, "message": "Environment values written"})
    if not str(credentials.get("LUMINA_ADMIN_API_KEY", "")).strip():
        steps.append(
            {
                "name": "admin_api_key",
                "success": True,
                "message": "Admin API key auto-generated and stored in .env",
            }
        )

    config_payload = config_manager.load_yaml_config()
    config_payload["mode"] = mode_value
    broker = config_payload.get("broker")
    if not isinstance(broker, dict):
        broker = {}
    broker["backend"] = broker_backend
    config_payload["broker"] = broker
    config_manager.save_yaml_config(config_payload)
    steps.append({"name": "runtime_mode", "success": True, "message": f"Mode set to {mode_value}/{broker_backend}"})

    first_boot_manager.save_full_settings(
        training_trades=int(training["training_trades"]),
        prefer_real_data_only=bool(training["prefer_real_data_only"]),
        max_real_days=int(training["max_real_days"]),
        allow_minimal_synthetic_fallback=bool(training["allow_minimal_synthetic_fallback"]),
        require_real_simulator_data=bool(
            training.get("require_real_simulator_data", training["prefer_real_data_only"])
        ),
        mark_user_configured=True,
    )
    first_boot_manager.save_neuro_require_real_simulator_data(
        bool(training.get("require_real_simulator_data", training["prefer_real_data_only"]))
    )
    steps.append({"name": "first_boot_config", "success": True, "message": "First-boot training settings saved"})

    if admin_password:
        if len(admin_password) >= 12:
            AdminAuth(workspace_root / "state" / "launcher_admin_password.json").set_password(admin_password)
            steps.append({"name": "admin_password", "success": True, "message": "Admin password configured"})
        else:
            steps.append(
                {
                    "name": "admin_password",
                    "success": False,
                    "message": "Admin password skipped (must be at least 12 characters).",
                }
            )

    model = model_service.get_model(selected_model_key) or model_service.get_catalog().models()[0]
    model_result = setup_service.apply_recommended_config(hardware=snapshot, model=model)
    steps.append(model_result.to_dict())
    model_service.save_state(workspace_root / "state" / "model_catalog_state.json", model.key)

    ConfigLoader.invalidate()
    setup_service.save_status(
        {
            "steps": steps,
            "selected_mode": mode_value,
            "selected_model": model.key,
            "hardware_tier": getattr(snapshot, "profile_tier", "unknown"),
        }
    )

    required = {"env_update", "runtime_mode", "first_boot_config", "config_update"}
    ok_names = {step.get("name") for step in steps if step.get("success")}
    if required.issubset(ok_names):
        setup_service.mark_complete(hardware=snapshot, model=model)
    return steps


def _init_wizard_state(
    *,
    config_manager: ConfigManager,
    first_boot_manager: FirstBootManager,
    hardware_service: HardwareService,
    model_service: ModelService,
) -> None:
    if _WIZARD_STATE_KEY in st.session_state:
        return
    env_values = config_manager.parse_env_file()
    first_boot = first_boot_manager.read_settings()
    snapshot = hardware_service.get_snapshot()
    recommended = model_service.get_recommended(
        ram_gb=snapshot.ram_gb,
        gpu_vram_gb=snapshot.gpu_vram_gb,
        vllm_supported=snapshot.vllm_supported,
    )
    st.session_state[_WIZARD_STATE_KEY] = {
        "credentials": {
            "CROSSTRADE_TOKEN": str(env_values.get("CROSSTRADE_TOKEN", "")),
            "CROSSTRADE_ACCOUNT": str(env_values.get("CROSSTRADE_ACCOUNT", "")),
            "XAI_API_KEY": str(env_values.get("XAI_API_KEY", "")),
            "TELEGRAM_BOT_TOKEN": str(env_values.get("TELEGRAM_BOT_TOKEN", "")),
            "TELEGRAM_CHAT_ID": str(env_values.get("TELEGRAM_CHAT_ID", "")),
            "LUMINA_JWT_SECRET_KEY": str(env_values.get("LUMINA_JWT_SECRET_KEY", "")),
            "LUMINA_ADMIN_API_KEY": str(env_values.get("LUMINA_ADMIN_API_KEY", "")) or f"sk_{secrets.token_hex(32)}",
        },
        "mode_selection": str(env_values.get("TRADE_MODE", "sim") or "sim").strip().lower(),
        "selected_model_key": recommended.key,
        "training": {
            "training_trades": int(first_boot["training_trades"]),
            "prefer_real_data_only": bool(first_boot["prefer_real_data_only"]),
            "max_real_days": int(first_boot["max_real_days"]),
            "allow_minimal_synthetic_fallback": bool(first_boot["allow_minimal_synthetic_fallback"]),
            "require_real_simulator_data": bool(first_boot["require_real_simulator_data"]),
        },
        "admin_password": "",
    }
    st.session_state[_WIZARD_STEP_KEY] = 0


def _mask_secret(value: str) -> str:
    text = str(value or "")
    if not text:
        return "(empty)"
    if len(text) <= 8:
        return "*" * len(text)
    return f"{text[:4]}...{text[-2:]}"


def _render_status_rows(status_payload: dict[str, Any]) -> None:
    steps = status_payload.get("steps", [])
    if not isinstance(steps, list) or not steps:
        return
    st.caption("Laatste setup-run")
    st.dataframe(steps, use_container_width=True)


def render_setup_wizard(
    *,
    workspace_root: Path,
    setup_service: SetupService,
    config_manager: ConfigManager,
    first_boot_manager: FirstBootManager,
    hardware_service: HardwareService,
    model_service: ModelService,
) -> None:
    _init_wizard_state(
        config_manager=config_manager,
        first_boot_manager=first_boot_manager,
        hardware_service=hardware_service,
        model_service=model_service,
    )
    state = st.session_state[_WIZARD_STATE_KEY]
    step_index = int(st.session_state.get(_WIZARD_STEP_KEY, 0))
    step_name = _WIZARD_STEPS[step_index]
    snapshot = hardware_service.get_snapshot()
    recommended_model = model_service.get_recommended(
        ram_gb=snapshot.ram_gb,
        gpu_vram_gb=snapshot.gpu_vram_gb,
        vllm_supported=snapshot.vllm_supported,
    )

    st.title("LUMINA Guided Setup")
    st.caption("Voltooi eerst de configuratiewizard voordat de launcher tabs worden geladen.")
    st.progress((step_index + 1) / len(_WIZARD_STEPS), text=f"Stap {step_index + 1} van {len(_WIZARD_STEPS)}")

    if step_name == "welcome":
        st.subheader("1) Welkom")
        st.markdown(
            "Deze wizard configureert je runtime mode, modelkeuze en first-boot training. "
            "Gevoelige gegevens worden opgeslagen in `.env`; operationele instellingen in `config.yaml`."
        )
        st.info("Na afronden wordt `state/lumina_setup_complete.json` geschreven en start de hoofdapp automatisch.")

    elif step_name == "credentials":
        st.subheader("2) API Keys en Credentials")
        creds = state["credentials"]
        creds["CROSSTRADE_TOKEN"] = st.text_input("Crosstrade token", value=creds["CROSSTRADE_TOKEN"], type="password")
        creds["CROSSTRADE_ACCOUNT"] = st.text_input("Crosstrade account", value=creds["CROSSTRADE_ACCOUNT"])
        creds["XAI_API_KEY"] = st.text_input("xAI API key (optioneel)", value=creds["XAI_API_KEY"], type="password")
        creds["TELEGRAM_BOT_TOKEN"] = st.text_input(
            "Telegram bot token (optioneel)", value=creds["TELEGRAM_BOT_TOKEN"], type="password"
        )
        creds["TELEGRAM_CHAT_ID"] = st.text_input("Telegram chat id (optioneel)", value=creds["TELEGRAM_CHAT_ID"])
        col_a, col_b = st.columns([3, 2])
        with col_a:
            creds["LUMINA_JWT_SECRET_KEY"] = st.text_input(
                "JWT secret key", value=creds["LUMINA_JWT_SECRET_KEY"], type="password"
            )
        with col_b:
            if st.button("Genereer veilige JWT sleutel", use_container_width=True):
                creds["LUMINA_JWT_SECRET_KEY"] = secrets.token_urlsafe(32)
                st.rerun()
        admin_col_a, admin_col_b = st.columns([3, 2])
        with admin_col_a:
            creds["LUMINA_ADMIN_API_KEY"] = st.text_input(
                "LUMINA Admin API key (voor emergency backend acties)",
                value=creds["LUMINA_ADMIN_API_KEY"],
                type="password",
            )
        with admin_col_b:
            if st.button("Genereer Admin API key", use_container_width=True):
                creds["LUMINA_ADMIN_API_KEY"] = f"sk_{secrets.token_hex(32)}"
                st.rerun()
        st.caption(
            "TradingView-gegevens worden hier niet apart opgeslagen; in deze stack lopen signalen en data via broker/Crosstrade."
        )
        state["admin_password"] = st.text_input(
            "Admin wachtwoord (optioneel, min 12 tekens)",
            value=state["admin_password"],
            type="password",
        )

    elif step_name == "mode":
        st.subheader("3) Trading mode")
        mode_options = ["paper", "sim", "real"]
        labels = {"paper": "Paper", "sim": "SIM", "real": "REAL"}
        if state["mode_selection"] not in mode_options:
            state["mode_selection"] = "sim"
        selected = st.radio(
            "Kies runtime mode",
            options=mode_options,
            index=mode_options.index(state["mode_selection"]),
            format_func=lambda item: labels[item],
        )
        state["mode_selection"] = selected
        mode_value, backend = resolve_mode_matrix(selected)
        st.info(f"Config matrix: `TRADE_MODE={mode_value}` + `BROKER_BACKEND={backend}`")
        if selected == "real":
            st.warning("REAL mode routeert op live backend en vereist volledige risicocontroles en geldige secrets.")
        with st.expander("Advanced mode (optioneel): sim_real_guard"):
            enabled = st.checkbox(
                "Gebruik sim_real_guard in plaats van sim",
                value=state["mode_selection"] == "sim_real_guard",
            )
            if enabled:
                state["mode_selection"] = "sim_real_guard"
                st.caption("Vergeet niet: `ENABLE_SIM_REAL_GUARD=true` vereist voor startup-validatie.")
            elif state["mode_selection"] == "sim_real_guard":
                state["mode_selection"] = "sim"

    elif step_name == "model":
        st.subheader("4) Model selectie")
        st.metric("Hardware tier", str(snapshot.profile_tier).upper())
        st.metric("Aanbevolen model", recommended_model.display_name)
        options = model_service.get_all_models()
        selectable = []
        for model in options:
            label = f"{model.display_name} ({model.ollama_tag})"
            selectable.append((label, model))
        current_key = str(state.get("selected_model_key", recommended_model.key))
        index = 0
        for i, (_, model) in enumerate(selectable):
            if model.key == current_key:
                index = i
                break
        chosen_label = st.selectbox("Kies model", options=[item[0] for item in selectable], index=index)
        selected_model = next(model for label, model in selectable if label == chosen_label)
        state["selected_model_key"] = selected_model.key
        fits = hardware_service.fits_hardware(selected_model)
        if selected_model.key == recommended_model.key:
            st.success("Je gebruikt de hardware-aware aanbeveling.")
        elif fits:
            st.info("Dit model past op huidige hardware, maar wijkt af van de aanbevolen standaard.")
        else:
            st.warning("Dit model is zwaarder dan de huidige hardware-aanbeveling.")

    elif step_name == "training":
        st.subheader("5) Eerste training parameters")
        training = state["training"]
        training["training_trades"] = int(
            st.number_input(
                "Aantal training trades",
                min_value=500,
                max_value=2_000_000,
                value=int(training["training_trades"]),
                step=500,
            )
        )
        training["prefer_real_data_only"] = bool(
            st.checkbox("Voorkeur: alleen echte historische data", value=bool(training["prefer_real_data_only"]))
        )
        training["max_real_days"] = int(
            st.number_input(
                "Maximale historische dagen voor first-boot",
                min_value=30,
                max_value=3650,
                value=int(training["max_real_days"]),
                step=5,
            )
        )
        training["allow_minimal_synthetic_fallback"] = bool(
            st.checkbox(
                "Sta minimale synthetische fallback toe",
                value=bool(training["allow_minimal_synthetic_fallback"]),
            )
        )
        training["require_real_simulator_data"] = bool(
            st.checkbox(
                "Neuro/simulator vereist echte data (fail-closed)",
                value=bool(training["require_real_simulator_data"]),
            )
        )
        from lumina_core.first_boot_ui import (
            estimate_first_boot_duration,
            estimate_first_boot_real_days,
            exceeds_max_real_days_window,
            format_duration_range,
        )

        estimate = estimate_first_boot_real_days(training["training_trades"])
        st.caption(f"Geschatte historische vensterbehoefte: ongeveer {estimate} dagen.")
        duration_estimate = estimate_first_boot_duration(
            training_trades=int(training["training_trades"]),
            max_real_days=int(training["max_real_days"]),
            prefer_real_data_only=bool(training["prefer_real_data_only"]),
            allow_minimal_synthetic_fallback=bool(training["allow_minimal_synthetic_fallback"]),
            workspace_root=workspace_root,
        )
        st.caption(
            "Geschatte trainingsduur: "
            f"{format_duration_range(duration_estimate)} "
            f"({duration_estimate.confidence} confidence, bron: {duration_estimate.method})."
        )
        for note in duration_estimate.notes[:2]:
            st.caption(f"- {note}")
        if exceeds_max_real_days_window(estimate, training["max_real_days"]):
            st.warning("De schatting ligt boven `max_real_days`; verhoog venster of verlaag training trades.")

    elif step_name == "review":
        st.subheader("6) Review en opslaan")
        creds = state["credentials"]
        mode_value, backend = resolve_mode_matrix(state["mode_selection"])
        selected_model = model_service.get_model(state["selected_model_key"]) or recommended_model
        training = state["training"]
        st.markdown("### Samenvatting")
        st.write(f"- Mode: `{mode_value}` (broker: `{backend}`)")
        st.write(f"- Model: `{selected_model.display_name}`")
        st.write(f"- Training trades: `{training['training_trades']}`")
        st.write(f"- Prefer real data only: `{training['prefer_real_data_only']}`")
        st.write(f"- Require real simulator data: `{training['require_real_simulator_data']}`")
        st.write("- Credentials")
        st.write(f"  - CROSSTRADE_TOKEN: `{_mask_secret(creds['CROSSTRADE_TOKEN'])}`")
        st.write(f"  - CROSSTRADE_ACCOUNT: `{creds['CROSSTRADE_ACCOUNT'] or '(empty)'}`")
        st.write(f"  - XAI_API_KEY: `{_mask_secret(creds['XAI_API_KEY'])}`")
        st.write(f"  - TELEGRAM_BOT_TOKEN: `{_mask_secret(creds['TELEGRAM_BOT_TOKEN'])}`")
        st.write(f"  - TELEGRAM_CHAT_ID: `{creds['TELEGRAM_CHAT_ID'] or '(empty)'}`")
        st.write(f"  - LUMINA_JWT_SECRET_KEY: `{_mask_secret(creds['LUMINA_JWT_SECRET_KEY'])}`")
        st.write(f"  - LUMINA_ADMIN_API_KEY: `{_mask_secret(creds['LUMINA_ADMIN_API_KEY'])}`")
        with st.expander("Optionele guided dependency install"):
            st.caption("Deze acties zijn optioneel en blokkeren setup-voltooiing niet.")
            if st.button("Install launcher dependencies", use_container_width=True):
                st.json(setup_service.install_launcher_dependencies().to_dict())
            if st.button("Install runtime dependencies", use_container_width=True):
                st.json(setup_service.install_runtime_dependencies().to_dict())
            if st.button("Ensure Ollama", use_container_width=True):
                st.json(setup_service.ensure_ollama().to_dict())
            if st.button("Pull geselecteerd model", use_container_width=True):
                st.json(setup_service.pull_model(selected_model).to_dict())
        if st.button("Setup voltooien", type="primary", use_container_width=True):
            result_steps = persist_setup_configuration(
                workspace_root=workspace_root,
                setup_service=setup_service,
                config_manager=config_manager,
                first_boot_manager=first_boot_manager,
                model_service=model_service,
                snapshot=snapshot,
                selected_model_key=selected_model.key,
                mode_selection=state["mode_selection"],
                credentials=creds,
                training=training,
                admin_password=state["admin_password"],
            )
            has_failures = any(not bool(item.get("success")) for item in result_steps if item.get("name") != "admin_password")
            if has_failures:
                st.warning("Setup deels opgeslagen, maar er zijn fouten in één of meer stappen.")
            else:
                st.success("Setup voltooid. Birth Phase training start automatisch...")
                st.session_state["lumina_auto_start_birth_after_setup"] = True
            st.session_state.pop(_WIZARD_STATE_KEY, None)
            st.session_state.pop(_WIZARD_STEP_KEY, None)
            st.rerun()

    with st.container():
        left, right = st.columns(2)
        with left:
            if st.button("Vorige stap", disabled=step_index == 0, use_container_width=True):
                st.session_state[_WIZARD_STEP_KEY] = max(0, step_index - 1)
                st.rerun()
        with right:
            if st.button(
                "Volgende stap",
                disabled=step_index == (len(_WIZARD_STEPS) - 1),
                use_container_width=True,
            ):
                if step_name == "credentials":
                    creds = state["credentials"]
                    if not creds["CROSSTRADE_TOKEN"] or not creds["CROSSTRADE_ACCOUNT"]:
                        st.error("CROSSTRADE_TOKEN en CROSSTRADE_ACCOUNT zijn verplicht.")
                        st.stop()
                    if not creds["LUMINA_JWT_SECRET_KEY"]:
                        st.error("LUMINA_JWT_SECRET_KEY is verplicht voor startup-validatie.")
                        st.stop()
                    if not creds["LUMINA_ADMIN_API_KEY"]:
                        creds["LUMINA_ADMIN_API_KEY"] = f"sk_{secrets.token_hex(32)}"
                        st.info("LUMINA_ADMIN_API_KEY ontbrak en is automatisch veilig gegenereerd.")
                st.session_state[_WIZARD_STEP_KEY] = min(len(_WIZARD_STEPS) - 1, step_index + 1)
                st.rerun()

    _render_status_rows(setup_service.load_status())

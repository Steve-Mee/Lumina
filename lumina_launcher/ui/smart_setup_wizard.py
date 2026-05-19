"""Smart Setup Wizard — phase 1 intelligence stack (hardware, Ollama, models)."""

from __future__ import annotations

from pathlib import Path
from typing import Any

import streamlit as st

from lumina_launcher.core.setup_config import SetupConfig
from lumina_launcher.services.smart_setup_service import (
    SetupProgressEvent,
    SmartSetupOptions,
    SmartSetupService,
)

_STEP_KEY = "lumina_smart_setup_step"
_OPTIONS_KEY = "lumina_smart_setup_options"
_RESULT_KEY = "lumina_smart_setup_result"
_SCAN_KEY = "lumina_smart_setup_scan"

_PHASE_LABELS: dict[str, str] = {
    "detect": "Hardware",
    "launcher_deps": "Launcher dependencies",
    "runtime_deps": "Runtime dependencies",
    "ollama": "Ollama",
    "ollama_verify": "Ollama controle",
    "model_pull": "Model",
    "model_pull_progress": "Model download",
    "extra_models": "Extra modellen",
    "skipped_vllm_provider": "vLLM provider",
    "config": "Configuratie",
    "complete": "Voltooid",
    "failed": "Mislukt",
}

_SMART_SETUP_CSS = """
<style>
.lumina-smart-hero {
  border: 1px solid rgba(0, 240, 255, 0.28);
  border-radius: 16px;
  padding: 1.5rem 1.75rem;
  margin-bottom: 1rem;
  background: linear-gradient(135deg, rgba(0, 240, 255, 0.08), rgba(0, 255, 159, 0.05));
}
.lumina-smart-card {
  border: 1px solid rgba(0, 240, 255, 0.18);
  border-radius: 12px;
  padding: 1rem 1.25rem;
  background: rgba(12, 14, 20, 0.85);
  margin-bottom: 0.75rem;
}
.lumina-tier-pill {
  display: inline-block;
  padding: 0.25rem 0.75rem;
  border-radius: 999px;
  font-size: 0.75rem;
  font-weight: 700;
  letter-spacing: 0.06em;
  border: 1px solid rgba(0, 240, 255, 0.45);
  color: #00f0ff;
  background: rgba(0, 240, 255, 0.12);
}
.lumina-metric-grid {
  display: grid;
  grid-template-columns: repeat(3, 1fr);
  gap: 0.75rem;
  margin-top: 0.75rem;
}
.lumina-metric {
  border: 1px solid rgba(0, 240, 255, 0.14);
  border-radius: 10px;
  padding: 0.75rem;
  background: rgba(9, 10, 15, 0.9);
}
.lumina-metric-label {
  color: #9aa4b6;
  font-size: 0.72rem;
  text-transform: uppercase;
  letter-spacing: 0.04em;
}
.lumina-metric-value {
  color: #e8e6e3;
  font-size: 1.1rem;
  font-weight: 600;
  margin-top: 0.25rem;
}
</style>
"""


def _default_options(status: dict[str, Any], setup_cfg: SetupConfig) -> dict[str, bool]:
    missing = set(status.get("missing", []))
    ollama_installed = bool(status.get("ollama_installed"))
    model_present = bool(status.get("recommended_model_present"))
    install_ollama = setup_cfg.default_install_ollama() and (
        "ollama" in missing or not ollama_installed
    )
    download_model = setup_cfg.default_download_model() and not model_present
    return {
        "install_ollama": install_ollama,
        "download_recommended_model": download_model,
        "force_high_tier": setup_cfg.default_force_high_tier(),
        "pull_extra_models": False,
    }


def _init_session(status: dict[str, Any], setup_cfg: SetupConfig) -> None:
    if _STEP_KEY not in st.session_state:
        st.session_state[_STEP_KEY] = "welcome"
    if _OPTIONS_KEY not in st.session_state:
        st.session_state[_OPTIONS_KEY] = _default_options(status, setup_cfg)


def _tier_pill_html(tier: str) -> str:
    normalized = str(tier or "light").strip().upper()
    return f'<span class="lumina-tier-pill">{normalized}</span>'


def _render_hardware_summary(status: dict[str, Any]) -> None:
    intelligence = status.get("adaptive_intelligence", {})
    hardware = status.get("hardware", {})
    tier = str(intelligence.get("tier", "light"))
    model_key = str(status.get("recommended_model_key", ""))
    provider = str(status.get("recommended_provider", "ollama"))
    ram = float(hardware.get("ram_gb", 0.0) or 0.0)
    vram = float(hardware.get("gpu_vram_gb", 0.0) or 0.0)
    profile = hardware.get("profile_tier", "—")
    st.markdown(
        f"""
        <div class="lumina-smart-card">
          {_tier_pill_html(tier)}
          <p style="margin:0.75rem 0 0;color:#e8e6e3;">
            Aanbevolen: <strong>{model_key}</strong> via <strong>{provider}</strong>
          </p>
          <div class="lumina-metric-grid">
            <div class="lumina-metric">
              <div class="lumina-metric-label">RAM</div>
              <div class="lumina-metric-value">{ram:.0f} GB</div>
            </div>
            <div class="lumina-metric">
              <div class="lumina-metric-label">GPU VRAM</div>
              <div class="lumina-metric-value">{vram:.1f} GB</div>
            </div>
            <div class="lumina-metric">
              <div class="lumina-metric-label">Profiel</div>
              <div class="lumina-metric-value">{profile}</div>
            </div>
          </div>
        </div>
        """,
        unsafe_allow_html=True,
    )


def _render_welcome(smart_setup: SmartSetupService) -> None:
    st.markdown(
        """
        <div class="lumina-smart-hero">
          <h2 style="margin:0;color:#e8e6e3;">Welkom bij LUMINA Smart Setup</h2>
          <p style="margin:0.5rem 0 0;color:#9aa4b6;">
            We scannen je hardware en bereiden de beste lokale AI-stack voor.
            Volgende stap daarna: API-keys en training.
          </p>
        </div>
        """,
        unsafe_allow_html=True,
    )
    if st.button("Hardware scannen", type="primary", use_container_width=True):
        smart_setup._intelligence_manager.refresh(refresh_hardware=True)
        st.session_state[_SCAN_KEY] = smart_setup.get_setup_status()
        st.session_state[_STEP_KEY] = "configure"
        st.rerun()

    scan = st.session_state.get(_SCAN_KEY)
    if isinstance(scan, dict) and scan:
        st.subheader("Scanresultaat")
        _render_hardware_summary(scan)
        if st.button("Doorgaan naar installatie", use_container_width=True):
            st.session_state[_STEP_KEY] = "configure"
            st.rerun()


def _render_configure(smart_setup: SmartSetupService, status: dict[str, Any]) -> None:
    setup_cfg = smart_setup.setup_config
    st.subheader("Smart Setup")
    if setup_cfg.mode == "manual":
        st.caption(
            "Handmatige modus: automatische installatie staat uit in config.yaml. "
            "Vink opties aan om toch automatisch te installeren, of volg de handmatige stappen."
        )
    else:
        st.caption("Kies wat automatisch geïnstalleerd wordt. Eén klik — minimale wrijving.")
    _render_hardware_summary(status)

    opts = st.session_state[_OPTIONS_KEY]
    ollama_installed = bool(status.get("ollama_installed"))
    intelligence = status.get("adaptive_intelligence", {})

    install_ollama = st.checkbox(
        "Ollama installeren (indien nodig)",
        value=bool(opts.get("install_ollama", True)),
        disabled=ollama_installed and "ollama" not in status.get("missing", []),
        help="Al geïnstalleerd op deze machine." if ollama_installed else None,
    )
    download_model = st.checkbox(
        "Beste model downloaden",
        value=bool(opts.get("download_recommended_model", setup_cfg.default_download_model())),
    )
    force_high = False
    if setup_cfg.allow_force_tier:
        force_high = st.checkbox(
            "Geavanceerde modus (High Tier)",
            value=bool(opts.get("force_high_tier", False)),
            help="Forceert intelligence.mode=force_high in config.yaml.",
        )
    extra_models = st.checkbox(
        "Extra modellen",
        value=bool(opts.get("pull_extra_models", False)),
        help="Download upgrade-paden uit het modelcatalogus (kan lang duren).",
    )

    if force_high and bool(intelligence.get("degraded_state")):
        st.warning(
            "High Tier is aangevraagd maar hardware ondersteunt dit mogelijk niet volledig. "
            "LUMINA valt fail-closed terug naar een lager tier indien nodig."
        )

    st.session_state[_OPTIONS_KEY] = {
        "install_ollama": install_ollama,
        "download_recommended_model": download_model,
        "force_high_tier": force_high,
        "pull_extra_models": extra_models,
    }

    if st.button("🚀 Alles Automatisch Instellen", type="primary", use_container_width=True):
        st.session_state[_STEP_KEY] = "running"
        st.rerun()


def _run_installation(smart_setup: SmartSetupService) -> None:
    st.subheader("Installatie bezig")
    progress_bar = st.progress(0.0)
    status_slot = st.empty()
    log_slot = st.empty()
    events: list[SetupProgressEvent] = []

    def on_progress(event: SetupProgressEvent) -> None:
        events.append(event)
        label = _PHASE_LABELS.get(event.phase, event.phase)
        if event.percent is not None:
            progress_bar.progress(min(max(event.percent, 0), 100) / 100.0)
        prefix = ""
        if event.level == "warning":
            prefix = "⚠️ "
        elif event.level == "error":
            prefix = "❌ "
        status_slot.markdown(f"**{prefix}{label}** — {event.message}")

    setup_cfg = smart_setup.setup_config
    raw_opts = st.session_state.get(_OPTIONS_KEY, {})
    options = SmartSetupOptions(
        install_ollama=bool(raw_opts.get("install_ollama", setup_cfg.default_install_ollama())),
        download_recommended_model=bool(
            raw_opts.get("download_recommended_model", setup_cfg.default_download_model())
        ),
        force_high_tier=(
            bool(raw_opts.get("force_high_tier", False)) if setup_cfg.allow_force_tier else False
        ),
        pull_extra_models=bool(raw_opts.get("pull_extra_models", False)),
        graceful_degrade=True,
    )

    result = smart_setup.run_smart_setup(
        on_progress=on_progress,
        options=options,
        mark_complete=False,
    )
    st.session_state[_RESULT_KEY] = result.to_dict()

    if result.success:
        if result.degraded:
            st.warning("Setup afgerond met waarschuwingen. Controleer de stappen op het succescherm.")
            for warning in result.warnings:
                st.caption(f"- {warning}")
        st.session_state[_STEP_KEY] = "success"
        st.rerun()
    else:
        st.error("Installatie mislukt. Controleer de stappen hieronder en probeer opnieuw.")
        if events:
            log_slot.dataframe(
                [{"phase": e.phase, "message": e.message, "percent": e.percent} for e in events],
                use_container_width=True,
            )
        if st.button("Terug naar opties", use_container_width=True):
            st.session_state[_STEP_KEY] = "configure"
            st.rerun()


def _render_success(status: dict[str, Any]) -> None:
    result = st.session_state.get(_RESULT_KEY, {})
    degraded = bool(result.get("degraded")) if isinstance(result, dict) else False
    warnings = list(result.get("warnings", [])) if isinstance(result, dict) else []
    manual_steps = list(result.get("manual_steps", [])) if isinstance(result, dict) else []

    intelligence = status.get("adaptive_intelligence", {})
    tier = str(intelligence.get("tier", "light"))
    model_key = str(status.get("recommended_model_key", ""))
    ollama_tag = str(status.get("recommended_ollama_tag", ""))
    provider = str(status.get("recommended_provider", "ollama"))
    reasoning = str(intelligence.get("reasoning_mode", ""))

    if degraded:
        st.warning("Smart Setup afgerond met waarschuwingen (inference-stack mogelijk incompleet).")
    else:
        st.success("Smart Setup voltooid")
    if warnings:
        st.markdown("**Waarschuwingen**")
        for item in warnings:
            st.caption(f"- {item}")
    if manual_steps:
        st.markdown("**Handmatige vervolgstappen**")
        for step in manual_steps:
            title = str(step.get("title", step.get("id", "stap")))
            command = str(step.get("command", ""))
            manual = str(step.get("manual", ""))
            st.markdown(f"- **{title}**")
            if command:
                st.code(command)
            if manual:
                st.caption(manual)
    st.markdown(
        f"""
        <div class="lumina-smart-card">
          {_tier_pill_html(tier)}
          <ul style="color:#c8d3e2;margin:1rem 0 0;padding-left:1.2rem;">
            <li><strong>Model:</strong> {model_key} ({ollama_tag})</li>
            <li><strong>Backend:</strong> {provider}</li>
            <li><strong>Reasoning:</strong> {reasoning}</li>
          </ul>
        </div>
        """,
        unsafe_allow_html=True,
    )
    st.caption("Volgende stap: API-keys, trading mode en Birth Phase-instellingen.")

    if st.button("Ga door naar configuratie", type="primary", use_container_width=True):
        for key in (_STEP_KEY, _OPTIONS_KEY, _RESULT_KEY, _SCAN_KEY):
            st.session_state.pop(key, None)
        st.rerun()


def render_smart_setup_wizard(
    *,
    workspace_root: Path,
    smart_setup_service: SmartSetupService,
) -> None:
    """Render the Smart Setup Wizard (intelligence stack, phase 1)."""
    del workspace_root  # SSOT already bound on service
    st.markdown(_SMART_SETUP_CSS, unsafe_allow_html=True)

    status = smart_setup_service.get_setup_status()
    setup_cfg = smart_setup_service.setup_config
    _init_session(status, setup_cfg)
    step = str(st.session_state.get(_STEP_KEY, "welcome"))

    st.title("LUMINA Smart Setup")
    st.caption("Fase 1 van 2 — Intelligence stack")

    if step == "welcome":
        _render_welcome(smart_setup_service)
    elif step == "configure":
        scan = st.session_state.get(_SCAN_KEY)
        display_status = scan if isinstance(scan, dict) and scan else status
        _render_configure(smart_setup_service, display_status)
    elif step == "running":
        _run_installation(smart_setup_service)
    elif step == "success":
        result = st.session_state.get(_RESULT_KEY, {})
        final_status = result.get("status", status) if isinstance(result, dict) else status
        _render_success(final_status if isinstance(final_status, dict) else status)
    else:
        st.session_state[_STEP_KEY] = "welcome"
        st.rerun()

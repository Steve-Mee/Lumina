from __future__ import annotations

from pathlib import Path

from lumina_launcher.streamlit_main import LauncherPhase, _resolve_launcher_phase
from lumina_launcher.ui.tab_registry import TabRenderContext, launcher_tab_specs


class _FakeFirstBootManager:
    def __init__(self, completed: bool, should_enter_operations: bool | None = None) -> None:
        self._completed = completed
        self._should_enter_operations = completed if should_enter_operations is None else should_enter_operations

    def is_completed(self) -> bool:
        return self._completed

    def should_enter_operations(self) -> bool:
        return self._should_enter_operations


def _ctx(*, first_boot_completed: bool, mode: str = "sim") -> TabRenderContext:
    return TabRenderContext(
        launcher_root=Path("."),
        services=None,
        state={},
        current_dream={},
        snapshot=None,
        process_alive=False,
        current_mode=mode,
        first_boot_completed=first_boot_completed,
    )


def test_phase_resolver_strict_completion_rule() -> None:
    assert _resolve_launcher_phase(first_boot_manager=_FakeFirstBootManager(True)) == LauncherPhase.OPERATIONS_READY
    assert _resolve_launcher_phase(first_boot_manager=_FakeFirstBootManager(False)) == LauncherPhase.FIRST_BOOT_REQUIRED


def test_tab_visibility_first_boot_phase() -> None:
    ctx = _ctx(first_boot_completed=False)
    visible_ids = {spec.tab_id for spec in launcher_tab_specs() if spec.visible(ctx)}
    assert "first_boot" in visible_ids
    assert "dashboard" not in visible_ids
    assert "live_activity" not in visible_ids


def test_tab_visibility_operations_phase() -> None:
    ctx = _ctx(first_boot_completed=True)
    visible_ids = {spec.tab_id for spec in launcher_tab_specs() if spec.visible(ctx)}
    assert "first_boot" not in visible_ids
    assert "dashboard" in visible_ids
    assert "live_activity" in visible_ids


def test_start_script_defaults_to_single_screen_mode() -> None:
    root = Path(__file__).resolve().parents[1]
    script = (root / "scripts" / "start_lumina_with_training_dashboard.ps1").read_text(encoding="utf-8")
    assert "StartLegacyDashboard" in script
    assert "Backend API" in script
    assert "run_launcher.py" in script
    assert "legacy standalone dashboard" in script.lower()


def test_training_dashboard_no_longer_links_to_8502() -> None:
    root = Path(__file__).resolve().parents[1]
    source = (root / "lumina_launcher" / "ui" / "tabs" / "training_dashboard.py").read_text(encoding="utf-8")
    assert "Full dashboard (8502)" not in source


def test_first_boot_home_uses_tabs_not_expanders() -> None:
    root = Path(__file__).resolve().parents[1]
    source = (root / "lumina_launcher" / "streamlit_main.py").read_text(encoding="utf-8")
    assert "st.tabs(" in source and "Setup" in source and "phase_label" in source
    assert "render_first_boot_command_center(" in source
    dashboard_source = (root / "lumina_launcher" / "ui" / "tabs" / "training_dashboard.py").read_text(encoding="utf-8")
    assert '"Birth Phase"' in dashboard_source
    assert '"Overview", "Monitoring", "Evolution approvals"' in dashboard_source
    assert 'with st.expander("Guided setup wizard"' not in source
    assert 'with st.expander("Monitoring and training overview"' not in source


def test_first_boot_home_never_auto_starts_birth() -> None:
    root = Path(__file__).resolve().parents[1]
    source = (root / "lumina_launcher" / "streamlit_main.py").read_text(encoding="utf-8")
    assert "lumina_auto_start_birth_after_setup" not in source
    assert "lumina_birth_auto_start_attempted" not in source
    assert "birth_service.start_birth" not in source


def test_first_boot_tab_has_stop_training_guard() -> None:
    root = Path(__file__).resolve().parents[1]
    source = (root / "lumina_launcher" / "ui" / "tabs" / "first_boot.py").read_text(encoding="utf-8")
    assert "first_boot_stop_training" in source
    assert "_stop_birth_training" in source
    assert "stop_birth" in source


def test_stop_all_activities_stops_birth_service() -> None:
    root = Path(__file__).resolve().parents[1]
    source = (root / "lumina_launcher" / "core" / "process_manager.py").read_text(encoding="utf-8")
    assert "birth_service.stop_birth" in source


def test_first_boot_tab_separates_save_from_start() -> None:
    root = Path(__file__).resolve().parents[1]
    source = (root / "lumina_launcher" / "ui" / "tabs" / "first_boot.py").read_text(encoding="utf-8")
    assert "first_boot_save_settings" in source
    assert "first_boot_start_birth_phase" in source
    assert "_persist_first_boot_settings" in source
    assert "explicit_user_start=True" in source
    assert "first_boot_start_requested" in source


def test_training_dashboard_uses_tabs_for_embedded_sections() -> None:
    root = Path(__file__).resolve().parents[1]
    source = (root / "lumina_launcher" / "ui" / "tabs" / "training_dashboard.py").read_text(encoding="utf-8")
    assert '"Overview", "Monitoring", "Evolution approvals", "SIM evolution", "React dashboard"' in source
    assert 'with st.expander("Monitoring (embedded)"' not in source
    assert 'with st.expander("Evolution approvals"' not in source
    assert 'with st.expander("SIM evolution (full panel)"' not in source


def test_react_dashboard_tab_validates_embedded_build_before_iframe() -> None:
    root = Path(__file__).resolve().parents[1]
    source = (root / "lumina_launcher" / "ui" / "tabs" / "training_dashboard.py").read_text(encoding="utf-8")
    react_section = source.split("def _render_react_tab_content", 1)[1].split("def _render_luxury_status_bar_live", 1)[0]
    assert "embedded_react_ui_status(" in react_section
    assert 'reason == "wrong_base_path"' in react_section
    assert "if ready and react_url:" in react_section


def test_monitoring_dashboard_uses_inline_tabs_not_sidebar_select() -> None:
    root = Path(__file__).resolve().parents[1]
    source = (root / "lumina_os" / "frontend" / "monitoring_dashboard.py").read_text(encoding="utf-8")
    assert "tab_debug, tab_a, tab_b, tab_c, tab_d, tab_e, tab_f, tab_g, tab_h = st.tabs" in source
    assert "st.sidebar.selectbox(" not in source
    assert "time.sleep" not in source


def test_first_boot_command_center_uses_shared_autorefresh() -> None:
    root = Path(__file__).resolve().parents[1]
    source = (root / "lumina_launcher" / "ui" / "tabs" / "training_dashboard.py").read_text(encoding="utf-8")
    fb_section = source.split("def render_first_boot_command_center", 1)[1].split(
        "def render_training_dashboard_tab", 1
    )[0]
    assert "render_command_center_autorefresh_controls" in fb_section
    assert "run_with_autorefresh" in fb_section
    assert "lumina_command_center_autorefresh" in source
    assert "lumina_training_autorefresh" not in source


def test_status_bar_no_longer_shows_react_open_button() -> None:
    root = Path(__file__).resolve().parents[1]
    source = (root / "lumina_os" / "frontend" / "dashboard_views.py").read_text(encoding="utf-8")
    status_bar_section = source.split("def render_luxury_status_bar", 1)[1].split(
        "def render_shared_monitoring_dashboard", 1
    )[0]
    assert "Open React Dashboard" not in status_bar_section
    assert "st.link_button(" not in status_bar_section
    assert "Birth Phase SSOT" in source


def test_first_boot_slider_input_state_sync_and_adjust_button_present() -> None:
    root = Path(__file__).resolve().parents[1]
    source = (root / "lumina_launcher" / "ui" / "tabs" / "first_boot.py").read_text(encoding="utf-8")
    assert "on_change=_on_slider_change" in source
    assert "on_change=_on_input_change" in source
    assert "Pas max days aan" in source


def test_blank_reset_script_exists_with_backup_and_policy_cleanup() -> None:
    root = Path(__file__).resolve().parents[1]
    script = (root / "scripts" / "reset_lumina_blank_state.ps1").read_text(encoding="utf-8")
    assert "Backup saved to" in script
    assert "lumina_agents\\ppo\\lumina_ppo_policy.zip" in script
    assert "state\\first_boot_completed.flag" in script


def test_streamlit_presence_strip_hides_target_before_training_start() -> None:
    root = Path(__file__).resolve().parents[1]
    source = (root / "lumina_launcher" / "streamlit_main.py").read_text(encoding="utf-8")
    assert '"tpm_label": (' in source
    assert 'else "Not started"' in source


def test_react_metrics_no_longer_fallback_to_5000_target() -> None:
    root = Path(__file__).resolve().parents[1]
    hook_source = (root / "frontend" / "src" / "hooks" / "useLuminaMetrics.ts").read_text(encoding="utf-8")
    component_source = (
        root / "frontend" / "src" / "components" / "MonitoringDashboard.tsx"
    ).read_text(encoding="utf-8")
    assert "training_target_trades: 5000" not in hook_source
    assert "training_target_trades: 0" in hook_source
    assert "if (!merged.training_target_applicable) {" in hook_source
    assert "targetTrades = liveMetrics?.training_target_trades ?? 0" in component_source


def test_react_dashboard_includes_idle_hard_gate_and_provenance_stamp() -> None:
    root = Path(__file__).resolve().parents[1]
    source = (root / "frontend" / "src" / "components" / "MonitoringDashboard.tsx").read_text(encoding="utf-8")
    assert "if (!metrics.session_active) {" in source
    assert "src {METRICS_SOURCE_PATH} | build {BUILD_MARKER}" in source
    assert "target not configured yet" in source


def test_streamlit_main_uses_launcher_setup_gate() -> None:
    root = Path(__file__).resolve().parents[1]
    source = (root / "lumina_launcher" / "streamlit_main.py").read_text(encoding="utf-8")
    assert "resolve_launcher_setup_state" in source
    assert "_render_launcher_setup_sidebar_status" in source


def test_admin_tab_contains_setup_training_configuration_section() -> None:
    root = Path(__file__).resolve().parents[1]
    source = (root / "lumina_launcher" / "ui" / "tabs" / "admin.py").read_text(encoding="utf-8")
    assert "Setup & Training Configuration" in source
    assert "lumina_setup_complete.json" in source
    assert "RESET FIRST BOOT" in source
    assert "Reset stap {current_step}/3" in source


def test_first_boot_tab_contains_strict_save_start_and_summary_actions() -> None:
    root = Path(__file__).resolve().parents[1]
    source = (root / "lumina_launcher" / "ui" / "tabs" / "first_boot.py").read_text(encoding="utf-8")
    assert "Start Birth Phase is pas actief nadat je op Save Settings hebt geklikt." in source
    assert "Instellingen zijn vergrendeld tijdens/na gestart Birth Phase training." in source
    assert "Historische data tijdelijk niet beschikbaar." in source
    assert "Practice met synthetic" in source
    assert "Extra trainen" in source
    assert "Ga naar bot" in source


def test_launcher_contains_stop_all_and_go_to_bot_phase_gate() -> None:
    root = Path(__file__).resolve().parents[1]
    source = (root / "lumina_launcher" / "streamlit_main.py").read_text(encoding="utf-8")
    assert "should_enter_operations()" in source
    assert "Stop alles & afsluiten" in source
    assert "emergency_flatten_and_cancel" in source


def test_first_boot_pause_is_checkpoint_based() -> None:
    root = Path(__file__).resolve().parents[1]
    source = (root / "lumina_launcher" / "ui" / "tabs" / "first_boot.py").read_text(encoding="utf-8")
    assert "Pauzeer training" in source
    assert "resolve_pause_policy" in source
    assert "pause_trading_safely" not in source

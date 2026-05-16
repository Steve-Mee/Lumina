# Launcher Feature Parity Registry

Deze registry is de contractbron voor launcher-parity met `lumina_launcher.py.old`.
Elke feature hieronder moet beschikbaar blijven in de modulaire launcher.

## Pre-start configuratie

- `trading_mode_select` -> `lumina_launcher/streamlit_main.py` (`paper/sim/sim_real_guard/real`)
- `risk_profile_select` -> `lumina_launcher/streamlit_main.py`
- `instrument_select` -> `lumina_launcher/streamlit_main.py`
- `voice_toggle` -> `lumina_launcher/streamlit_main.py`
- `screen_share_toggle` -> `lumina_launcher/streamlit_main.py`
- `dashboard_toggle` -> `lumina_launcher/streamlit_main.py`
- `runtime_trace_toggle` -> `lumina_launcher/streamlit_main.py`
- `runtime_trace_interval_select` -> `lumina_launcher/streamlit_main.py`
- `latency_sla_select` -> `lumina_launcher/streamlit_main.py`
- `save_config_and_start_bot` -> `lumina_launcher/streamlit_main.py` + `lumina_launcher/core/process_manager.py`

## First-boot detail

- `first_boot_training_trades` -> `lumina_launcher/ui/tabs/first_boot.py` + `lumina_launcher/core/first_boot.py`
- `first_boot_prefer_real_data_only` -> `lumina_launcher/ui/tabs/first_boot.py` + `lumina_launcher/core/first_boot.py`
- `first_boot_max_real_days` -> `lumina_launcher/ui/tabs/first_boot.py` + `lumina_launcher/core/first_boot.py`
- `first_boot_allow_minimal_synthetic_fallback` -> `lumina_launcher/ui/tabs/first_boot.py` + `lumina_launcher/core/first_boot.py`
- `first_boot_require_real_simulator_data` -> `lumina_launcher/ui/tabs/first_boot.py` + `lumina_launcher/core/first_boot.py`
- `first_boot_pause_resume_controls` -> `lumina_launcher/ui/tabs/first_boot.py`

## SIM/REAL operaties

- `sim_evolution_dashboard` -> `lumina_launcher/ui/tabs/sim_evolution.py` + `lumina_os/frontend/dashboard_views.py`
- `real_operations_dashboard` -> `lumina_launcher/ui/tabs/real_operations.py` + `lumina_os/frontend/dashboard_views.py`
- `real_mode_gating_visibility` -> `lumina_launcher/streamlit_main.py`

## Tooltips en help

- `help_text_registry` -> `lumina_launcher/ui/help_texts.py`
- `kv_tooltips_rendering` -> `lumina_launcher/ui/components/kv_section.py`
- `first_boot_tooltips_coverage` -> `lumina_launcher/ui/tabs/first_boot.py`
- `prestart_tooltips_coverage` -> `lumina_launcher/streamlit_main.py`

## Logging en observability

- `launcher_run_context` -> `lumina_launcher/streamlit_main.py`
- `process_start_stop_logs` -> `lumina_launcher/core/process_manager.py`
- `backend_request_logs` -> `lumina_launcher/services/backend_client.py`
- `admin_mutation_logs` -> `lumina_launcher/ui/tabs/admin.py`

## Performance contract

- `single_active_tab_render` -> `lumina_launcher/streamlit_main.py`
- `cached_services_and_snapshot` -> `lumina_launcher/streamlit_main.py`
- `fast_log_tail_reader` -> `lumina_launcher/ui/tabs/live_activity.py`
- `cached_stability_report` -> `lumina_os/frontend/dashboard_views.py`

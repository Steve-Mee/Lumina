# Launcher Feature Parity Registry

Contract source for launcher parity with `lumina_launcher.py.old` and the **Neural Command Deck** (`tauri-app/`).

| Feature key | Streamlit | Tauri Command Deck |
|-------------|-----------|-------------------|
| `trading_mode_select` | `lumina_launcher/streamlit_main.py` | `tauri-app/src/components/config/BotConfigForm.tsx` |
| `risk_profile_select` | `lumina_launcher/streamlit_main.py` | `BotConfigForm` (risk section) |
| `instrument_select` | `lumina_launcher/streamlit_main.py` | `BotConfigForm` preferences |
| `voice_toggle` | `lumina_launcher/streamlit_main.py` | `BotConfigForm` |
| `screen_share_toggle` | `lumina_launcher/streamlit_main.py` | `BotConfigForm` |
| `dashboard_toggle` | `lumina_launcher/streamlit_main.py` | `BotConfigForm` diagnostics |
| `runtime_trace_toggle` | `lumina_launcher/streamlit_main.py` | `BotConfigForm` diagnostics |
| `runtime_trace_interval_select` | `lumina_launcher/streamlit_main.py` | `BotConfigForm` diagnostics |
| `latency_sla_select` | `lumina_launcher/streamlit_main.py` | `BotConfigForm` diagnostics |
| `save_config_and_start_bot` | `streamlit_main.py` + `process_manager.py` | `CommandHud.tsx` Save & Start |
| `pause_live_trading` | `streamlit_main.py` | `CommandHud.tsx` Safety → Pause live trading |
| `first_boot_training_trades` | `lumina_launcher/ui/tabs/first_boot.py` | `BirthSettingsPanel.tsx` |
| `first_boot_prefer_real_data_only` | `first_boot.py` | `BirthSettingsPanel.tsx` |
| `first_boot_max_real_days` | `first_boot.py` | `BirthSettingsPanel.tsx` + adjust-max-days API |
| `first_boot_allow_minimal_synthetic_fallback` | `first_boot.py` | `BirthSettingsPanel.tsx` |
| `first_boot_require_real_simulator_data` | `first_boot.py` | `BirthSettingsPanel.tsx` |
| `first_boot_pause_resume_controls` | `first_boot.py` | `TrainingControlBar.tsx` |
| `sim_evolution_dashboard` | `sim_evolution.py` | `SimReadinessPanel.tsx` |
| `real_operations_dashboard` | `real_operations.py` | `RealOperationsPanel.tsx` |
| `monitoring_dashboard_a_h` | `monitoring_dashboard.py` | `MonitoringDeepPanel.tsx` |
| `embedded_react_dashboard` | `training_dashboard.py` | `ReactDashboardButton.tsx` |
| `presence_strip` | `presence_strip.py` | `PresenceRail.tsx` |
| `backend_health_banner` | `streamlit_main.py` | `PresenceRail.tsx` recovery chip via `deckStatusOrchestrator` |
| `hud_signal_layout` | — | `hudSignalLayout.ts` + `CommandHud.tsx` (max 2 hero; annex hint) |
| `intelligence_lazy_tabs` | `streamlit_main.py` (one tab at a time) | `IntelligenceTabContent.tsx` (active tab only) |
| `evolution_lazy_tabs` | — | `EvolutionTabContent.tsx` (active center tab only) |
| `hud_overflow_max_5` | — | `hudOverflowLayout.ts` + `CommandHud.tsx` overflow menu |
| `observation_deck_frame` | — | `ObservationDeckFrame.tsx` + ops annex panels |
| `deck_transition_orchestrator` | — | `deckTransitionOrchestrator.ts` + `useDeckTransition.ts` |
| `help_text_registry` | `help_texts.py` | `tauri-app/src/lib/helpTexts.ts` |
| `panel_autorefresh_interval` | `training_dashboard.py` | `SettingsDialog` refresh tab |
| `single_active_tab_render` | `streamlit_main.py` (one tab at a time) | `deckPanelStore.ts` (single active deck tab) |
| `organism_vitality_model` | — | `organismVitalityModel.ts` + `PresenceRail.tsx` (unified tier labels) |
| `deck_status_orchestrator` | — | `deckStatusOrchestrator.ts` + `DeckBlockingOverlay.tsx` / `PresenceRail` statusChip |
| `backend_health_fail_closed` | — | `backendHealthStore.ts` (default false until probe) |
| `hud_metrics_annex_hint` | — | `hudMetricsHintStore.ts` + `IntelligenceDeckPanel.tsx` Performance tab |
| `cinematic_tier_contract` | — | `docs/lumina-deck-cinematic-tiers.md` (T0–T3 tier contract) |
| `subsystems_drawer_airlock` | — | `SubsystemsDrawer.tsx` + mode-tinted scrim / airlock CSS |
| `pulse_language` | — | `pulseLanguage.ts` + presence/engine pulse CSS in `cockpit.css` |
| `panel_tab_transition` | — | `usePanelTabTransition.ts` + `deckTransitionOrchestrator.ts` (`panelTab` 0.35s) |
| `organism_clock_store` | — | `organismClockStore.ts` + `useOrganismShellVars.ts` (shared CSS/R3F breath) |
| `distress_panel_grammar` | — | `distressPanelClass()` + `warnOverlay*Class()` in onboarding/birth |
| `decision_theater_real_palette` | — | `ReasoningSpine.tsx` + REAL CSS overrides in `cockpit.css` |
| `birth_shell_envelope_parity` | — | `birthPhase.css` vignette + organism cycle on CSS fallback |
| `backend_health_single_poller` | — | `backendHealthStore.ts` + `useBackendHealth.ts` |
| `decision_stage_hero_cap_2` | — | `decisionTheaterLayout.ts` + `DecisionTheaterStage.tsx` (max 2 stage heroes) |
| `sync_single_surface` | — | `deckStatusOrchestrator.ts` + `PresenceRail.tsx` (rail secondary only) |
| `birth_diagnostics_off_hero` | — | `BirthPhaseScreen.tsx` ops block + tier doc rule 1 |
| `distress_grammar_unified` | — | `distressPanelClass()` across Evolution/PPO/onboarding alerts |
| `real_rim_glow_family` | — | REAL `hud-signal` rim/breathe CSS in `cockpit.css` |
| `runtime_status_poll_singleton` | — | `useRuntimeStatusPoll.ts` shared 5s poll |
| `glass_stack_budget_enforced` | — | `glassStackBudget.test.ts` + muted StatusBar/deck frames |
| `decision_theater_de_dashboard` | — | `decisionTheaterLayout.ts` trade preview cap + mode action grammar |
| `real_chrome_identity_pass` | — | `modePresentation.ts` helpers + `realChromeIdentity.test.ts` |
| `three_scene_differentiation` | — | `helixPrimitives.tsx` + `threeSceneIdentity.test.ts` |
| `birth_finale_organism_summary` | — | `BirthPhaseScreen.tsx` finale summary + REAL preview veil |
| `distress_grammar_complete` | — | `distressGrammarSweep.test.ts` component-wide amber purge |

Backend APIs added for Command Deck: `/api/runtime/pause-trading`, `/api/monitoring/diagnostics`, `/api/monitoring/workspace-snapshot`, `/api/monitoring/react-dashboard-status`, `/api/monitoring/admin-setup-snapshot`, `/api/birth/settings`, `/api/birth/adjust-max-days`, `/api/birth/logs-tail`.

"""Declarative launcher tab registry with grouped navigation."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any, Callable

from lumina_core.first_boot_progress import resolve_first_boot_stage
from lumina_core.runtime_session import resolve_runtime_session_state

@dataclass(frozen=True)
class TabRenderContext:
    launcher_root: Path
    services: Any
    state: dict[str, Any]
    current_dream: dict[str, Any]
    snapshot: Any
    process_alive: bool
    current_mode: str
    first_boot_completed: bool


RenderFn = Callable[[TabRenderContext], None]
VisibleFn = Callable[[TabRenderContext], bool]


@dataclass(frozen=True)
class LauncherTabSpec:
    tab_id: str
    label: str
    group: str
    render: RenderFn
    visible: VisibleFn


def _always(_ctx: TabRenderContext) -> bool:
    return True


def _real_only(ctx: TabRenderContext) -> bool:
    return ctx.current_mode == "real"


def _ops_only(ctx: TabRenderContext) -> bool:
    return ctx.first_boot_completed


def _first_boot_only(ctx: TabRenderContext) -> bool:
    return not ctx.first_boot_completed


def _render_live_activity(ctx: TabRenderContext) -> None:
    from lumina_launcher.ui.tabs.live_activity import render_live_activity_tab

    proc_state = ctx.services.process_manager._load_process_state()
    first_boot_progress = ctx.services.first_boot_manager.read_progress()
    runtime_session = resolve_runtime_session_state(
        first_boot_stage=resolve_first_boot_stage(first_boot_progress),
        process_alive=ctx.process_alive,
        current_mode=ctx.current_mode,
        first_boot_timestamp=str(first_boot_progress.get("timestamp") or ""),
    )
    render_live_activity_tab(
        ctx.launcher_root,
        alive=ctx.process_alive,
        pid=int(proc_state.get("pid", 0) or 0) or None,
        session_kind=runtime_session.session_kind,
        session_active=runtime_session.session_active,
        activity_stale=runtime_session.activity_stale,
    )


def _render_first_boot(ctx: TabRenderContext) -> None:
    from lumina_launcher.ui.tabs.first_boot import render_first_boot_tab

    render_first_boot_tab(
        ctx.services.first_boot_manager,
        process_manager=ctx.services.process_manager,
        backend_client=ctx.services.backend_client,
    )


def _render_live_trader(ctx: TabRenderContext) -> None:
    from lumina_launcher.ui.tabs.live_trader import render_live_trader_tab

    render_live_trader_tab(ctx.state, ctx.current_dream)


def _render_hardware(ctx: TabRenderContext) -> None:
    from lumina_launcher.ui.tabs.hardware_tab import render_hardware_tab

    render_hardware_tab(ctx.services.hardware_service, ctx.services.model_service, ctx.snapshot)


def _render_model_mgmt(ctx: TabRenderContext) -> None:
    from lumina_launcher.ui.tabs.model_management_tab import render_model_management_tab

    render_model_management_tab(
        ctx.services.hardware_service,
        ctx.services.model_service,
        ctx.snapshot,
        setup_service=ctx.services.setup_service,
    )


def _render_trader_league(ctx: TabRenderContext) -> None:
    from lumina_launcher.ui.tabs.trader_league import render_trader_league_tab

    render_trader_league_tab(ctx.services.backend_client)


def _render_sim_evolution(ctx: TabRenderContext) -> None:
    from lumina_launcher.ui.tabs.sim_evolution import render_sim_evolution_tab

    render_sim_evolution_tab(ctx.launcher_root)


def _render_dashboard(ctx: TabRenderContext) -> None:
    from lumina_launcher.ui.tabs.training_dashboard import render_training_dashboard_tab

    render_training_dashboard_tab(
        ctx.launcher_root,
        first_boot_manager=ctx.services.first_boot_manager,
        hardware_service=ctx.services.hardware_service,
        process_manager=ctx.services.process_manager,
        backend_base_url=ctx.services.backend_client.base_url,
    )


def _render_community(ctx: TabRenderContext) -> None:
    from lumina_launcher.ui.tabs.community_bibles import render_community_bibles_tab

    render_community_bibles_tab(ctx.services.backend_client)


def _render_admin(ctx: TabRenderContext) -> None:
    from lumina_launcher.ui.tabs.admin import render_admin_tab

    render_admin_tab(
        ctx.services.backend_client,
        workspace_root=ctx.launcher_root,
        process_manager=ctx.services.process_manager,
    )


def _render_real_ops(ctx: TabRenderContext) -> None:
    from lumina_launcher.ui.tabs.real_operations import render_real_operations_tab

    render_real_operations_tab(ctx.launcher_root)


def launcher_tab_specs() -> list[LauncherTabSpec]:
    return [
        LauncherTabSpec("live_activity", "📡 Live Activity", "Operate", _render_live_activity, _ops_only),
        LauncherTabSpec("first_boot", "🚀 First Boot", "Operate", _render_first_boot, _first_boot_only),
        LauncherTabSpec("live_trader", "Live Trader", "Operate", _render_live_trader, _ops_only),
        LauncherTabSpec("hardware", "Hardware", "Monitoring", _render_hardware, _ops_only),
        LauncherTabSpec("model_mgmt", "Model Mgmt", "Monitoring", _render_model_mgmt, _ops_only),
        LauncherTabSpec("sim_evolution", "SIM Evolution", "Monitoring", _render_sim_evolution, _ops_only),
        LauncherTabSpec("dashboard", "📊 LUMINA OS Dashboard", "Monitoring", _render_dashboard, _ops_only),
        LauncherTabSpec("trader_league", "Trader League", "Community", _render_trader_league, _ops_only),
        LauncherTabSpec("community_bibles", "📖 Community Bibles", "Community", _render_community, _ops_only),
        LauncherTabSpec("admin", "🛠️ Admin", "Admin", _render_admin, _ops_only),
        LauncherTabSpec("real_ops", "🛡️ REAL Operations", "Operate", _render_real_ops, lambda ctx: _ops_only(ctx) and _real_only(ctx)),
    ]

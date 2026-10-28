"""Attach OverlayPort + non-blocking MDS fan-out to the engine (K1/K5)."""

from __future__ import annotations

import threading
from pathlib import Path
from typing import Any

from lumina_core.code_evolution.runtime_overlay import bind_overlay_to_engine
from lumina_core.code_evolution.runtime_role import is_real_like_capital, normalize_runtime_role
from lumina_core.evolution.challenger_venue.isolation import (
    require_own_process,
    run_with_fault_boundary,
    spawn_venue_process,
    venue_process_main,
)
from lumina_core.evolution.challenger_venue.mds_fanout import ChampionSafeFanout
from lumina_core.evolution.challenger_venue.runtime import VenueRuntime


def _venue_cfg() -> dict[str, Any]:
    try:
        from lumina_core.config_loader import ConfigLoader

        evo = ConfigLoader.section("evolution", default={}) or {}
    except Exception:
        return {}
    if not isinstance(evo, dict):
        return {}
    raw = evo.get("challenger_venue", {})
    return dict(raw) if isinstance(raw, dict) else {}


def _drain_loop(fanout: ChampionSafeFanout, runtime: VenueRuntime, stop: threading.Event) -> None:
    while not stop.is_set():
        tick = fanout.get_challenger()
        if tick is None:
            stop.wait(0.05)
            continue
        run_with_fault_boundary(runtime.on_tick, tick)


def attach_challenger_surfaces(
    engine: Any,
    *,
    workspace: Path | str = ".",
    role: str | None = None,
    enabled: bool | None = None,
) -> dict[str, Any]:
    """Champion overlay stays empty unless CHAMPION.json points at a frozen bundle."""
    resolved = normalize_runtime_role(role if role is not None else getattr(engine, "runtime_role", None))
    bind_overlay_to_engine(engine, workspace=workspace, role=resolved)
    cfg = _venue_cfg()
    on = bool(cfg.get("enabled", False)) if enabled is None else bool(enabled)
    if not on:
        return {"attached": True, "venue": False, "role": resolved}
    capacity = int(cfg.get("mds_buffer", 64) or 64)
    fanout = ChampionSafeFanout(capacity=capacity)
    engine.challenger_fanout = fanout
    market = getattr(engine, "market_data", None)
    if market is not None:
        market.on_quote_tick = lambda tick: run_with_fault_boundary(fanout.publish_to_challenger, tick)

    mode = str(getattr(getattr(engine, "config", None), "trade_mode", "") or "")
    own_proc = require_own_process(
        real_champion=is_real_like_capital(mode),
        configured=bool(cfg.get("require_own_process_when_real_champion", True)),
    )
    if own_proc:
        import multiprocessing

        queue: Any = multiprocessing.Queue(maxsize=capacity)
        proc = spawn_venue_process(venue_process_main, str(workspace), queue)
        engine.challenger_venue_process = proc
        market = getattr(engine, "market_data", None)
        if market is not None:
            def _put(tick: Any) -> None:
                try:
                    queue.put_nowait(tick)
                except Exception:
                    try:
                        queue.get_nowait()
                    except Exception:
                        pass
                    try:
                        queue.put_nowait(tick)
                    except Exception:
                        pass

            market.on_quote_tick = lambda tick: run_with_fault_boundary(_put, tick)
        return {"attached": True, "venue": True, "own_process": True, "role": resolved}

    runtime = VenueRuntime(workspace)
    stop = threading.Event()
    worker = threading.Thread(target=_drain_loop, args=(fanout, runtime, stop), daemon=True)
    worker.start()
    engine.challenger_venue_stop = stop
    engine.challenger_venue_runtime = runtime
    return {"attached": True, "venue": True, "own_process": False, "role": resolved}

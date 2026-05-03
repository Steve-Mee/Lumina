from __future__ import annotations

import json
from collections import deque
from dataclasses import dataclass
from types import ModuleType
from typing import Any, Protocol


class SupportsEnginePersistence(Protocol):
    config: Any
    app: ModuleType | None
    economic_truth: Any
    sim_position_qty: int
    sim_entry_price: float
    sim_unrealized: float
    sim_peak: float
    live_position_qty: int
    last_entry_price: float
    last_realized_pnl_snapshot: float
    live_trade_signal: str
    pending_trade_reconciliations: list[dict[str, Any]]
    pnl_history: list[float]
    equity_curve: list[float]
    memory_buffer: deque
    narrative_memory: deque
    regime_history: deque
    trade_reflection_history: deque
    world_model: dict[str, Any]
    AI_DRAWN_FIBS: dict[str, Any]
    cost_tracker: dict[str, Any]
    rate_limit_backoff_seconds: int
    restart_count: int
    dashboard_last_chart_ts: float
    dashboard_last_has_image: bool
    ohlc_1min: Any
    live_quotes: Any
    current_candle: Any
    candle_start_ts: Any
    prev_volume_cum: float

    def bind_app(self, app: ModuleType) -> None: ...

    def get_current_dream_snapshot(self) -> dict[str, Any]: ...

    def set_current_dream_fields(self, updates: dict[str, Any]) -> None: ...

    def evolve_bible(self, updates: dict[str, Any]) -> None: ...

    def serialize_state_snapshot(self) -> dict[str, Any]: ...


@dataclass(slots=True)
class EngineStatePersistenceService:
    """Persist and restore mutable runtime state for LuminaEngine."""

    def hydrate_from_legacy(self, engine: SupportsEnginePersistence, app: ModuleType) -> None:
        engine.bind_app(app)
        attrs = [
            "regime_history",
            "narrative_memory",
            "memory_buffer",
            "trade_reflection_history",
            "pnl_history",
            "equity_curve",
            "trade_log",
            "performance_log",
            "sim_position_qty",
            "sim_entry_price",
            "sim_unrealized",
            "sim_peak",
            "live_position_qty",
            "last_entry_price",
            "last_realized_pnl_snapshot",
            "live_trade_signal",
            "pending_trade_reconciliations",
            "account_balance",
            "account_equity",
            "realized_pnl_today",
            "open_pnl",
            "world_model",
            "AI_DRAWN_FIBS",
            "COST_TRACKER",
            "RATE_LIMIT_BACKOFF",
            "restart_count",
            "DASHBOARD_LAST_CHART_TS",
            "DASHBOARD_LAST_HAS_IMAGE",
            "ohlc_1min",
            "live_quotes",
            "current_candle",
            "candle_start_ts",
            "prev_volume_cum",
        ]
        for name in attrs:
            if not hasattr(app, name):
                continue
            value = getattr(app, name)
            if name == "COST_TRACKER":
                engine.cost_tracker = dict(value) if isinstance(value, dict) else dict(engine.cost_tracker)
            elif name == "RATE_LIMIT_BACKOFF":
                engine.rate_limit_backoff_seconds = int(value)
            elif name == "DASHBOARD_LAST_CHART_TS":
                engine.dashboard_last_chart_ts = float(value)
            elif name == "DASHBOARD_LAST_HAS_IMAGE":
                engine.dashboard_last_has_image = bool(value)
            else:
                setattr(engine, name, value)
        engine.economic_truth.version_all_pnl_sources(engine)

    def save_state(self, engine: SupportsEnginePersistence) -> None:
        economic_truth_snapshot = engine.economic_truth.version_all_pnl_sources(engine)
        state = {
            "sim_position_qty": engine.sim_position_qty,
            "sim_entry_price": engine.sim_entry_price,
            "sim_unrealized": engine.sim_unrealized,
            "sim_peak": engine.sim_peak,
            "live_position_qty": engine.live_position_qty,
            "last_entry_price": engine.last_entry_price,
            "last_realized_pnl_snapshot": engine.last_realized_pnl_snapshot,
            "live_trade_signal": engine.live_trade_signal,
            "pending_trade_reconciliations": engine.pending_trade_reconciliations[-20:],
            "pnl_history": engine.pnl_history[-200:],
            "equity_curve": engine.equity_curve[-200:],
            "current_dream": engine.get_current_dream_snapshot(),
            "bible_evolvable": engine.evolvable_layer,
            "memory_buffer": list(engine.memory_buffer),
            "narrative_memory": list(engine.narrative_memory),
            "regime_history": list(engine.regime_history),
            "trade_reflection_history": list(engine.trade_reflection_history),
            "state_snapshot": engine.serialize_state_snapshot(),
            "economic_truth": engine.economic_truth.to_dict(),
            "economic_truth_snapshot": economic_truth_snapshot,
        }
        try:
            engine.config.state_file.write_text(json.dumps(state, ensure_ascii=False, indent=2), encoding="utf-8")
        except Exception as exc:
            if engine.app is not None and hasattr(engine.app, "logger"):
                engine.app.logger.error(f"Save state error: {exc}")

    def load_state(self, engine: SupportsEnginePersistence) -> None:
        if not engine.config.state_file.exists():
            return
        try:
            state = json.loads(engine.config.state_file.read_text(encoding="utf-8"))
            engine.sim_position_qty = int(state.get("sim_position_qty", 0))
            engine.sim_entry_price = float(state.get("sim_entry_price", 0.0))
            engine.sim_unrealized = float(state.get("sim_unrealized", 0.0))
            engine.sim_peak = float(state.get("sim_peak", 50000.0))
            engine.live_position_qty = int(state.get("live_position_qty", 0))
            engine.last_entry_price = float(state.get("last_entry_price", 0.0))
            engine.last_realized_pnl_snapshot = float(state.get("last_realized_pnl_snapshot", 0.0))
            engine.live_trade_signal = str(state.get("live_trade_signal", "HOLD"))
            engine.pending_trade_reconciliations = list(state.get("pending_trade_reconciliations", []))
            engine.pnl_history = list(state.get("pnl_history", []))
            engine.equity_curve = list(state.get("equity_curve", [50000.0]))
            loaded_dream = state.get("current_dream")
            if isinstance(loaded_dream, dict):
                engine.set_current_dream_fields(loaded_dream)
            bible_evolvable = state.get("bible_evolvable")
            if isinstance(bible_evolvable, dict):
                engine.evolve_bible(bible_evolvable)
            engine.memory_buffer = deque(state.get("memory_buffer", []), maxlen=5)
            engine.narrative_memory = deque(state.get("narrative_memory", []), maxlen=8)
            engine.regime_history = deque(state.get("regime_history", []), maxlen=10)
            engine.trade_reflection_history = deque(state.get("trade_reflection_history", []), maxlen=20)
        except Exception as exc:
            if engine.app is not None and hasattr(engine.app, "logger"):
                engine.app.logger.error(f"Load state error: {exc}")

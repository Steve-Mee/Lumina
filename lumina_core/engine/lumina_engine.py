from __future__ import annotations

from collections import deque
import json
import logging
import time
from dataclasses import dataclass, field
from datetime import datetime
from types import ModuleType
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from .FastPathEngine import FastPathEngine

from lumina_bible import BibleEngine
from .dream_state import DreamState
from .engine_config import EngineConfig
from .market_data_manager import MarketDataManager
from .analysis_helpers import (
    build_pa_signature,
    calculate_dynamic_confluence,
    detect_candle_patterns,
    detect_market_regime,
    detect_market_structure,
    generate_price_action_summary,
    is_significant_event,
    parse_json_loose,
    run_async_safely,
    update_cost_tracker_from_usage,
)


@dataclass(slots=True)
class LuminaEngine:
    """Main orchestrator that holds all mutable runtime subsystems."""

    config: EngineConfig
    app: ModuleType | None = None
    dream_state: DreamState = field(default_factory=DreamState)
    bible_engine: BibleEngine | None = None
    market_data: MarketDataManager = field(default_factory=MarketDataManager)

    # Runtime mutable state moved from module globals.
    regime_history: deque = field(default_factory=lambda: deque(maxlen=10))
    narrative_memory: deque = field(default_factory=lambda: deque(maxlen=8))
    memory_buffer: deque = field(default_factory=lambda: deque(maxlen=5))
    trade_reflection_history: deque = field(default_factory=lambda: deque(maxlen=20))

    pnl_history: list[float] = field(default_factory=list)
    equity_curve: list[float] = field(default_factory=lambda: [50000.0])
    trade_log: list[dict[str, Any]] = field(default_factory=list)
    performance_log: list[dict[str, Any]] = field(default_factory=list)

    sim_position_qty: int = 0
    sim_entry_price: float = 0.0
    sim_unrealized: float = 0.0
    sim_peak: float = 50000.0

    account_balance: float = 50000.0
    account_equity: float = 50000.0
    realized_pnl_today: float = 0.0
    open_pnl: float = 0.0

    world_model: dict[str, Any] = field(default_factory=dict)
    AI_DRAWN_FIBS: dict[str, Any] = field(default_factory=dict)
    cost_tracker: dict[str, Any] = field(
        default_factory=lambda: {
            "today": 0.0,
            "reasoning_tokens": 0,
            "vision_tokens": 0,
            "cached_analyses": 0,
        }
    )
    rate_limit_backoff_seconds: int = 0
    restart_count: int = 0
    dashboard_last_chart_ts: float = 0.0
    dashboard_last_has_image: bool = False
    rl_policy_model: Any | None = None
    rl_policy_enabled: bool = False
    rl_confidence_threshold: float = 0.78
    # Lokale Ollama inference engine – wordt na constructie gekoppeld in lumina_v45.1.1.py
    local_engine: Any | None = None
    # Rule-based fast-path engine (< 200 ms, geen LLM)
    fast_path: Any | None = None
    # Runtime logger – standaard een module-level logger; kan vervangen worden
    logger: Any = field(default_factory=lambda: logging.getLogger("lumina"))
    # Realistische backtester – lazy geladen in __post_init__
    backtester: Any | None = None
    # Advanced backtester (walk-forward + regime OOS + full Monte Carlo)
    advanced_backtester: Any | None = None
    # RL omgeving + PPO trainer (nightly learning / live bias)
    rl_env: Any | None = None
    ppo_trainer: Any | None = None
    # Infinite simulator (nachtelijke miljoenen-trade simulatie)
    infinite_simulator: Any | None = None
    infinite_sim_last_run_date: str | None = None
    # Emotional twin (mentale bias-correctie)
    emotional_twin: Any | None = None
    emotional_twin_agent: Any | None = None
    emotional_twin_last_train_date: str | None = None
    # Multi-symbol swarm manager
    swarm: Any | None = None

    def __post_init__(self) -> None:
        if self.bible_engine is None:
            self.bible_engine = BibleEngine(str(self.config.bible_file))
            self.bible_engine.bible = self.bible_engine.load()

        # FastPathEngine wordt hier lazy geladen om circulaire imports te vermijden
        if self.fast_path is None:
            from .FastPathEngine import FastPathEngine  # noqa: PLC0415
            self.fast_path = FastPathEngine(engine=self)

        # RealisticBacktesterEngine lazy init
        if self.backtester is None:
            from lumina_core.runtime_context import RuntimeContext  # noqa: PLC0415
            from .RealisticBacktesterEngine import RealisticBacktesterEngine  # noqa: PLC0415
            self.backtester = RealisticBacktesterEngine(RuntimeContext(engine=self))

        # AdvancedBacktesterEngine lazy init
        if self.advanced_backtester is None:
            from lumina_core.runtime_context import RuntimeContext  # noqa: PLC0415
            from .AdvancedBacktesterEngine import AdvancedBacktesterEngine  # noqa: PLC0415
            self.advanced_backtester = AdvancedBacktesterEngine(RuntimeContext(engine=self))

        # RLTradingEnvironment + PPOTrainer lazy init
        if self.rl_env is None or self.ppo_trainer is None:
            from lumina_core.runtime_context import RuntimeContext  # noqa: PLC0415
            from .rl.ppo_trainer import PPOTrainer  # noqa: PLC0415
            from .rl.rl_trading_environment import RLTradingEnvironment  # noqa: PLC0415

            runtime_context = RuntimeContext(engine=self)
            if self.rl_env is None:
                self.rl_env = RLTradingEnvironment(runtime_context)
            if self.ppo_trainer is None:
                self.ppo_trainer = PPOTrainer(runtime_context)

        # InfiniteSimulator lazy init
        if self.infinite_simulator is None:
            from lumina_core.runtime_context import RuntimeContext  # noqa: PLC0415
            from .infinite_simulator import InfiniteSimulator  # noqa: PLC0415

            runtime_context = RuntimeContext(engine=self)
            self.infinite_simulator = InfiniteSimulator(runtime_context)

        # EmotionalTwinAgent lazy init
        if self.emotional_twin is None:
            from lumina_core.runtime_context import RuntimeContext  # noqa: PLC0415
            from .emotional_twin_agent import EmotionalTwinAgent  # noqa: PLC0415

            runtime_context = RuntimeContext(engine=self)
            self.emotional_twin = EmotionalTwinAgent(runtime_context)
            self.emotional_twin_agent = self.emotional_twin

        if self.swarm is None and bool(getattr(self.config, "swarm_enabled", True)):
            from .swarm_manager import SwarmManager  # noqa: PLC0415

            self.swarm = SwarmManager(self)

        if self.config.trade_mode not in {"paper", "sim", "real"}:
            raise ValueError("TRADE_MODE must be one of: paper, sim, real")

        if self.config.max_risk_percent <= 0:
            raise ValueError("MAX_RISK_PERCENT must be > 0")
        if self.config.drawdown_kill_percent <= 0:
            raise ValueError("DRAWDOWN_KILL_PERCENT must be > 0")

    def hydrate_from_legacy(self, app: ModuleType) -> None:
        """Import legacy runtime state into engine-managed fields."""
        self.bind_app(app)
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
            if hasattr(app, name):
                value = getattr(app, name)
                if name == "COST_TRACKER":
                    self.cost_tracker = dict(value) if isinstance(value, dict) else dict(self.cost_tracker)
                elif name == "RATE_LIMIT_BACKOFF":
                    self.rate_limit_backoff_seconds = int(value)
                elif name == "DASHBOARD_LAST_CHART_TS":
                    self.dashboard_last_chart_ts = float(value)
                elif name == "DASHBOARD_LAST_HAS_IMAGE":
                    self.dashboard_last_has_image = bool(value)
                else:
                    setattr(self, name, value)

    def save_state(self) -> None:
        state = {
            "sim_position_qty": self.sim_position_qty,
            "sim_entry_price": self.sim_entry_price,
            "sim_unrealized": self.sim_unrealized,
            "sim_peak": self.sim_peak,
            "pnl_history": self.pnl_history[-200:],
            "equity_curve": self.equity_curve[-200:],
            "current_dream": self.get_current_dream_snapshot(),
            "bible_evolvable": self.evolvable_layer,
            "memory_buffer": list(self.memory_buffer),
            "narrative_memory": list(self.narrative_memory),
            "regime_history": list(self.regime_history),
            "trade_reflection_history": list(self.trade_reflection_history),
        }
        try:
            self.config.state_file.write_text(json.dumps(state, ensure_ascii=False, indent=2), encoding="utf-8")
        except Exception as exc:
            if self.app is not None and hasattr(self.app, "logger"):
                self.app.logger.error(f"Save state error: {exc}")

    def load_state(self) -> None:
        if not self.config.state_file.exists():
            return
        try:
            state = json.loads(self.config.state_file.read_text(encoding="utf-8"))
            self.sim_position_qty = int(state.get("sim_position_qty", 0))
            self.sim_entry_price = float(state.get("sim_entry_price", 0.0))
            self.sim_unrealized = float(state.get("sim_unrealized", 0.0))
            self.sim_peak = float(state.get("sim_peak", 50000.0))
            self.pnl_history = list(state.get("pnl_history", []))
            self.equity_curve = list(state.get("equity_curve", [50000.0]))
            loaded_dream = state.get("current_dream")
            if isinstance(loaded_dream, dict):
                self.set_current_dream_fields(loaded_dream)
            bible_evolvable = state.get("bible_evolvable")
            if isinstance(bible_evolvable, dict):
                self.evolve_bible(bible_evolvable)
            self.memory_buffer = deque(state.get("memory_buffer", []), maxlen=5)
            self.narrative_memory = deque(state.get("narrative_memory", []), maxlen=8)
            self.regime_history = deque(state.get("regime_history", []), maxlen=10)
            self.trade_reflection_history = deque(state.get("trade_reflection_history", []), maxlen=20)
        except Exception as exc:
            if self.app is not None and hasattr(self.app, "logger"):
                self.app.logger.error(f"Load state error: {exc}")

    def evolve_bible(self, updates: dict[str, Any]) -> None:
        assert self.bible_engine is not None
        self.bible_engine.evolve(updates)

    def calculate_adaptive_risk_and_qty(self, price: float, regime: str, stop_price: float) -> int:
        multiplier = float(self.config.regime_risk_multipliers.get(regime, 1.0))
        adaptive_risk_percent = self.config.max_risk_percent * multiplier
        risk_dollars = self.account_equity * (adaptive_risk_percent / 100)

        stop_distance = abs(price - stop_price)
        if stop_distance <= 0:
            stop_distance = price * 0.005

        qty = max(1, int(risk_dollars / (stop_distance * 5)))
        if self.app is not None and hasattr(self.app, "logger"):
            self.app.logger.info(
                f"ADAPTIVE_RISK,regime={regime},risk_percent={adaptive_risk_percent:.2f},qty={qty}"
            )
        return qty

    def update_performance_log(self, trade_data: dict[str, Any]) -> None:
        self.performance_log.append(
            {
                "ts": datetime.now().isoformat(),
                "signal": trade_data.get("signal"),
                "chosen_strategy": trade_data.get("chosen_strategy", "unknown"),
                "regime": trade_data.get("regime", "NEUTRAL"),
                "confluence": trade_data.get("confluence", 0),
                "pnl": trade_data.get("pnl", 0),
                "drawdown": trade_data.get("drawdown", 0),
            }
        )
        if len(self.performance_log) > 500:
            self.performance_log.pop(0)

    def detect_candle_patterns(self, df, tf: str = "1min") -> dict[str, str]:
        return detect_candle_patterns(df, tf)

    def generate_price_action_summary(self) -> str:
        return generate_price_action_summary(self.market_data.copy_ohlc(), self.config.timeframes)

    def detect_market_regime(self, df) -> str:
        return detect_market_regime(df)

    def detect_market_structure(self, df) -> dict[str, Any]:
        return detect_market_structure(df)

    def calculate_dynamic_confluence(self, regime: str, recent_winrate: float) -> float:
        return calculate_dynamic_confluence(regime, recent_winrate)

    def is_significant_event(self, current_price: float, previous_price: float, regime: str) -> bool:
        return is_significant_event(current_price, previous_price, regime, self.config.event_threshold)

    def update_cost_tracker_from_usage(self, usage: dict[str, Any] | None, channel: str = "reasoning") -> None:
        update_cost_tracker_from_usage(self.cost_tracker, usage, channel)

    def run_async_safely(self, coro):
        return run_async_safely(coro)

    def parse_json_loose(self, raw_text: str) -> dict[str, Any]:
        return parse_json_loose(raw_text)

    def build_pa_signature(self, pa_summary: str) -> str:
        return build_pa_signature(pa_summary)

    @property
    def bible(self) -> dict[str, Any]:
        assert self.bible_engine is not None
        assert self.bible_engine.bible is not None
        return self.bible_engine.bible

    @property
    def evolvable_layer(self) -> dict[str, Any]:
        assert self.bible_engine is not None
        return self.bible_engine.evolvable_layer

    @property
    def ohlc_1min(self):
        return self.market_data.ohlc_1min

    @ohlc_1min.setter
    def ohlc_1min(self, value) -> None:
        self.market_data.ohlc_1min = value

    @property
    def live_quotes(self):
        return self.market_data.live_quotes

    @live_quotes.setter
    def live_quotes(self, value) -> None:
        self.market_data.live_quotes = value

    @property
    def live_data_lock(self):
        return self.market_data.live_data_lock

    @property
    def current_candle(self):
        return self.market_data.current_candle

    @current_candle.setter
    def current_candle(self, value) -> None:
        self.market_data.current_candle = value

    @property
    def candle_start_ts(self):
        return self.market_data.candle_start_ts

    @candle_start_ts.setter
    def candle_start_ts(self, value) -> None:
        self.market_data.candle_start_ts = value

    @property
    def prev_volume_cum(self) -> float:
        return self.market_data.prev_volume_cum

    @prev_volume_cum.setter
    def prev_volume_cum(self, value: float) -> None:
        self.market_data.prev_volume_cum = value

    def get_current_dream_snapshot(self) -> dict[str, Any]:
        return self.dream_state.snapshot()

    def set_current_dream_fields(self, updates: dict[str, Any]) -> None:
        self.dream_state.update(updates)

    def set_current_dream_value(self, key: str, value: Any) -> None:
        self.dream_state.set_value(key, value)

    def bind_app(self, app: ModuleType) -> None:
        self.app = app

    def set_rl_policy(self, model: Any, confidence_threshold: float = 0.78) -> None:
        self.rl_policy_model = model
        self.rl_policy_enabled = model is not None
        self.rl_confidence_threshold = float(confidence_threshold)

    def clear_rl_policy(self) -> None:
        self.rl_policy_model = None
        self.rl_policy_enabled = False

    def apply_rl_live_decision(
        self,
        action_payload: dict[str, Any],
        current_price: float,
        regime: str,
    ) -> bool:
        if not bool(action_payload):
            return False

        signal = str(action_payload.get("signal", "HOLD")).upper()
        confidence = float(action_payload.get("confidence", 0.0))
        qty = int(action_payload.get("qty", 1))
        stop = float(action_payload.get("stop", 0.0))
        target = float(action_payload.get("target", 0.0))

        if signal not in {"BUY", "SELL", "HOLD"}:
            return False
        if signal == "HOLD" or confidence < self.rl_confidence_threshold:
            return False

        if stop <= 0.0:
            stop = current_price * (0.997 if signal == "BUY" else 1.003)
        if target <= 0.0:
            rr = max(1.2, min(3.0, 1.0 + confidence * 1.8))
            if signal == "BUY":
                target = current_price + (current_price - stop) * rr
            else:
                target = current_price - (stop - current_price) * rr

        self.set_current_dream_fields(
            {
                "signal": signal,
                "confidence": confidence,
                "confluence_score": confidence,
                "stop": round(float(stop), 2),
                "target": round(float(target), 2),
                "reason": str(action_payload.get("reason", "PPO policy decision")),
                "chosen_strategy": "ppo_live_policy",
                "regime": regime,
                "qty": qty,
                "policy_ts": time.time(),
            }
        )
        return True

    def __getattr__(self, name: str) -> Any:
        if name in {"dream_state", "bible_engine", "market_data", "config", "app"}:
            raise AttributeError(name)

        if self.app is not None and hasattr(self.app, name):
            return getattr(self.app, name)
        raise AttributeError(name)

    def __setattr__(self, name: str, value: Any) -> None:
        core_fields = {
            "config",
            "app",
            "dream_state",
            "bible_engine",
            "market_data",
        }
        if name in core_fields:
            object.__setattr__(self, name, value)
            return

        descriptor = type(self).__dict__.get(name)
        if descriptor is not None and hasattr(descriptor, "__set__"):
            descriptor.__set__(self, value)
            return

        if getattr(self, "app", None) is not None and hasattr(self.app, name):
            setattr(self.app, name, value)
            return
        object.__setattr__(self, name, value)

# CANONICAL IMPLEMENTATION – v50 Living Organism
from __future__ import annotations

from collections import deque
import json
import logging
import os
import time
from dataclasses import dataclass, field
from datetime import datetime
from types import ModuleType
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from .fast_path_engine import FastPathEngine

from lumina_bible import BibleEngine
from .dream_state import DreamState
from .engine_config import EngineConfig
from .market_data_manager import MarketDataManager
from .risk_controller import HardRiskController, risk_limits_from_config
from .session_guard import SessionGuard
from .valuation_engine import ValuationEngine
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
class MarketStateContext:
    quote_count: int
    has_current_candle: bool
    last_candle_start_ts: float


@dataclass(slots=True)
class PositionStateContext:
    sim_position_qty: int
    live_position_qty: int
    last_entry_price: float
    live_trade_signal: str


@dataclass(slots=True)
class RiskStateContext:
    account_equity: float
    realized_pnl_today: float
    open_pnl: float
    pending_reconciliations: int


@dataclass(slots=True)
class AgentStateContext:
    regime: str
    confidence: float
    chosen_strategy: str
    memory_size: int


@dataclass(slots=True)
class LuminaEngine:
    """Main orchestrator that holds all mutable runtime subsystems."""

    config: EngineConfig
    app: ModuleType | None = None
    dream_state: DreamState = field(default_factory=DreamState)
    bible_engine: BibleEngine | None = None
    market_data: MarketDataManager = field(default_factory=MarketDataManager)
    valuation_engine: ValuationEngine = field(default_factory=ValuationEngine)

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
    live_position_qty: int = 0
    last_entry_price: float = 0.0
    last_realized_pnl_snapshot: float = 0.0
    live_trade_signal: str = "HOLD"
    pending_trade_reconciliations: list[dict[str, Any]] = field(default_factory=list)
    trade_reconciler_status: dict[str, Any] = field(default_factory=dict)

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
    current_regime_snapshot: dict[str, Any] = field(default_factory=dict)
    regime_detector: Any | None = None
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
    # Hard Risk Controller – unbreakable safety layer (fail-closed)
    risk_controller: HardRiskController | None = None
    # Infinite simulator (nachtelijke miljoenen-trade simulatie)
    infinite_simulator: Any | None = None
    infinite_sim_last_run_date: str | None = None
    # Emotional twin (mentale bias-correctie)
    emotional_twin: Any | None = None
    emotional_twin_agent: Any | None = None
    emotional_twin_last_train_date: str | None = None
    # Multi-symbol swarm manager
    swarm: Any | None = None
    # Monthly/ultimate performance validation
    validator: Any | None = None
    last_validation: datetime | None = None
    # Optional runtime observability sink
    observability_service: Any | None = None
    # Calendar-aware trading session guard
    session_guard: SessionGuard | None = None
    # Portfolio-level VaR allocator
    portfolio_var_allocator: Any | None = None
    # Immutable agent decision log sink
    decision_log: Any | None = None
    # ReasoningService (AI layer – injected by container)
    reasoning_service: Any | None = None
    # Market data service for bar/candle loading
    market_data_service: Any | None = None
    # Memory service for persistent state
    memory_service: Any | None = None
    # Operations service for trade/risk workflows
    operations_service: Any | None = None
    # Human/AI analysis service
    analysis_service: Any | None = None
    # Dashboard service (Streamlit)
    dashboard_service: Any | None = None
    # Visualization service
    visualization_service: Any | None = None
    # Reporting service (PDF/CSV export)
    reporting_service: Any | None = None
    # Trade reconciler (post-trade settlement)
    trade_reconciler: Any | None = None
    mode_risk_profile: dict[str, float] = field(default_factory=dict)

    def __post_init__(self) -> None:
        if self.bible_engine is None:
            self.bible_engine = BibleEngine(str(self.config.bible_file))
            if callable(getattr(self.bible_engine, "load", None)):
                self.bible_engine.bible = self.bible_engine.load()

        # FastPathEngine wordt hier lazy geladen om circulaire imports te vermijden
        if self.fast_path is None:
            from .fast_path_engine import FastPathEngine  # noqa: PLC0415
            self.fast_path = FastPathEngine(engine=self)

        # RealisticBacktesterEngine lazy init
        if self.backtester is None:
            from lumina_core.runtime_context import RuntimeContext  # noqa: PLC0415
            from .realistic_backtester_engine import RealisticBacktesterEngine  # noqa: PLC0415
            self.backtester = RealisticBacktesterEngine(RuntimeContext(engine=self))

        # AdvancedBacktesterEngine lazy init
        if self.advanced_backtester is None:
            from lumina_core.runtime_context import RuntimeContext  # noqa: PLC0415
            from .advanced_backtester_engine import AdvancedBacktesterEngine  # noqa: PLC0415
            self.advanced_backtester = AdvancedBacktesterEngine(RuntimeContext(engine=self))

        # RLTradingEnvironment, PPOTrainer, InfiniteSimulator, EmotionalTwinAgent,
        # SwarmManager and PerformanceValidator are built exclusively by
        # ApplicationContainer._init_services() which then assigns them back via
        # engine.ppo_trainer, engine.emotional_twin_agent, engine.infinite_simulator,
        # engine.swarm, engine.validator.  Constructing them here was dead-weight
        # double construction (Fase 3.1 clean-up).

        if self.session_guard is None:
            try:
                self.session_guard = SessionGuard(calendar_name="CME")
            except Exception as exc:
                logging.getLogger(__name__).error("SessionGuard init failed: %s", exc)
                self.session_guard = None

        # Hard Risk Controller initialization
        if self.risk_controller is None:
            session_config = getattr(self.config, 'session', {})
            if not isinstance(session_config, dict):
                session_config = {}
            limits = risk_limits_from_config()

            # Keep session calendar as source-of-truth for REAL mode behavior.
            limits.enforce_session_guard = bool(
                session_config.get(
                    'enforce_calendar',
                    limits.enforce_session_guard,
                )
            )
            
            state_file = getattr(self.config, 'state_dir', None)
            if state_file:
                from pathlib import Path  # noqa: PLC0415
                state_file = Path(state_file) / 'risk_controller_state.json'
            
            # Rules are enforced in REAL mode only. SIM is unconstrained learning.
            enforce_rules = self.config.trade_mode == "real"

            self.risk_controller = HardRiskController(
                limits,
                state_file=state_file,
                enforce_rules=enforce_rules,
                session_guard=self.session_guard,
            )

        if self.config.trade_mode not in {"paper", "sim", "real"}:
            raise ValueError("TRADE_MODE must be one of: paper, sim, real")

        if self.config.max_risk_percent <= 0:
            raise ValueError("MAX_RISK_PERCENT must be > 0")
        if self.config.drawdown_kill_percent <= 0:
            raise ValueError("DRAWDOWN_KILL_PERCENT must be > 0")

        # Mode-aware sizing profile (SIM vs REAL) loaded once at startup.
        self.mode_risk_profile = self._load_mode_risk_profile()

    def _load_mode_risk_profile(self) -> dict[str, float]:
        """Load Kelly sizing profile from config.yaml with safe defaults."""
        profile = {
            "sim_kelly_fraction": 1.0,
            "real_kelly_fraction": 0.25,
            "kelly_min_confidence": 0.65,
            "kelly_baseline": 0.25,
        }
        try:
            from lumina_core.config_loader import ConfigLoader  # noqa: PLC0415
            data = ConfigLoader.get()

            sim_cfg = data.get("sim", {}) if isinstance(data.get("sim"), dict) else {}
            real_cfg = data.get("real", {}) if isinstance(data.get("real"), dict) else {}
            trading_cfg = data.get("trading", {}) if isinstance(data.get("trading"), dict) else {}

            sim_kelly = float(sim_cfg.get("kelly_fraction", 1.0) or 1.0)
            real_kelly = float(
                real_cfg.get(
                    "kelly_fraction",
                    trading_cfg.get("kelly_fraction_max", 0.25),
                )
                or 0.25
            )
            min_conf = float(trading_cfg.get("kelly_min_confidence", 0.65) or 0.65)

            profile["sim_kelly_fraction"] = max(0.05, sim_kelly)
            profile["real_kelly_fraction"] = max(0.01, min(1.0, real_kelly))
            profile["kelly_min_confidence"] = max(0.0, min(1.0, min_conf))
        except Exception:
            # Keep defaults when config parsing fails.
            pass

        return profile

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
            "live_position_qty": self.live_position_qty,
            "last_entry_price": self.last_entry_price,
            "last_realized_pnl_snapshot": self.last_realized_pnl_snapshot,
            "live_trade_signal": self.live_trade_signal,
            "pending_trade_reconciliations": self.pending_trade_reconciliations[-20:],
            "pnl_history": self.pnl_history[-200:],
            "equity_curve": self.equity_curve[-200:],
            "current_dream": self.get_current_dream_snapshot(),
            "bible_evolvable": self.evolvable_layer,
            "memory_buffer": list(self.memory_buffer),
            "narrative_memory": list(self.narrative_memory),
            "regime_history": list(self.regime_history),
            "trade_reflection_history": list(self.trade_reflection_history),
            "state_snapshot": self.serialize_state_snapshot(),
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
            self.live_position_qty = int(state.get("live_position_qty", 0))
            self.last_entry_price = float(state.get("last_entry_price", 0.0))
            self.last_realized_pnl_snapshot = float(state.get("last_realized_pnl_snapshot", 0.0))
            self.live_trade_signal = str(state.get("live_trade_signal", "HOLD"))
            self.pending_trade_reconciliations = list(state.get("pending_trade_reconciliations", []))
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

    def build_state_contexts(self) -> dict[str, Any]:
        dream = self.get_current_dream_snapshot()
        market = MarketStateContext(
            quote_count=int(len(self.live_quotes) if self.live_quotes is not None else 0),
            has_current_candle=bool(self.current_candle),
            last_candle_start_ts=float(self.candle_start_ts or 0.0),
        )
        position = PositionStateContext(
            sim_position_qty=int(self.sim_position_qty),
            live_position_qty=int(self.live_position_qty),
            last_entry_price=float(self.last_entry_price),
            live_trade_signal=str(self.live_trade_signal),
        )
        risk = RiskStateContext(
            account_equity=float(self.account_equity),
            realized_pnl_today=float(self.realized_pnl_today),
            open_pnl=float(self.open_pnl),
            pending_reconciliations=int(len(self.pending_trade_reconciliations)),
        )
        agent = AgentStateContext(
            regime=str(dream.get("regime", "NEUTRAL")),
            confidence=float(dream.get("confidence", 0.0) or 0.0),
            chosen_strategy=str(dream.get("chosen_strategy", "unknown")),
            memory_size=int(len(self.memory_buffer)),
        )
        return {
            "market": market,
            "position": position,
            "risk": risk,
            "agent": agent,
        }

    def serialize_state_snapshot(self) -> dict[str, Any]:
        contexts = self.build_state_contexts()
        serialized = {
            "market": {
                "quote_count": contexts["market"].quote_count,
                "has_current_candle": contexts["market"].has_current_candle,
                "last_candle_start_ts": round(contexts["market"].last_candle_start_ts, 3),
            },
            "position": {
                "sim_position_qty": contexts["position"].sim_position_qty,
                "live_position_qty": contexts["position"].live_position_qty,
                "last_entry_price": round(contexts["position"].last_entry_price, 4),
                "live_trade_signal": contexts["position"].live_trade_signal,
            },
            "risk": {
                "account_equity": round(contexts["risk"].account_equity, 2),
                "realized_pnl_today": round(contexts["risk"].realized_pnl_today, 2),
                "open_pnl": round(contexts["risk"].open_pnl, 2),
                "pending_reconciliations": contexts["risk"].pending_reconciliations,
            },
            "agent": {
                "regime": contexts["agent"].regime,
                "confidence": round(contexts["agent"].confidence, 4),
                "chosen_strategy": contexts["agent"].chosen_strategy,
                "memory_size": contexts["agent"].memory_size,
            },
        }
        # Normalize key order to keep snapshots deterministic across runs.
        return json.loads(json.dumps(serialized, sort_keys=True, ensure_ascii=True))

    def evolve_bible(self, updates: dict[str, Any]) -> None:
        assert self.bible_engine is not None
        self.bible_engine.evolve(updates)

    def calculate_adaptive_risk_and_qty(
        self,
        price: float,
        regime: str,
        stop_price: float,
        confidence: float | None = None,
    ) -> int:
        multiplier = float(self.config.regime_risk_multipliers.get(regime, 1.0))
        profile = self.mode_risk_profile if isinstance(self.mode_risk_profile, dict) else {}
        baseline_kelly = max(1e-6, float(profile.get("kelly_baseline", 0.25) or 0.25))
        mode = str(getattr(self.config, "trade_mode", "paper") or "paper").strip().lower()

        if mode == "sim":
            kelly_fraction = float(profile.get("sim_kelly_fraction", 1.0) or 1.0)
            kelly_multiplier = max(1.0, kelly_fraction / baseline_kelly)
        elif mode == "real":
            kelly_fraction = float(profile.get("real_kelly_fraction", 0.25) or 0.25)
            kelly_multiplier = max(0.05, min(1.0, kelly_fraction / baseline_kelly))
        else:
            # Paper defaults to conservative sizing unless explicitly in SIM mode.
            kelly_fraction = float(profile.get("real_kelly_fraction", 0.25) or 0.25)
            kelly_multiplier = max(0.05, min(1.0, kelly_fraction / baseline_kelly))

        kelly_min_conf = max(0.0, min(1.0, float(profile.get("kelly_min_confidence", 0.65) or 0.65)))
        conf_val = 1.0 if confidence is None else max(0.0, min(1.0, float(confidence)))
        if conf_val >= kelly_min_conf or kelly_min_conf <= 0.0:
            confidence_scale = 1.0
        else:
            confidence_scale = max(0.1, conf_val / max(kelly_min_conf, 1e-6))

        adaptive_risk_percent = self.config.max_risk_percent * multiplier * kelly_multiplier * confidence_scale
        if mode == "real":
            # REAL mode remains conservative: never exceed configured max_risk_percent.
            adaptive_risk_percent = min(adaptive_risk_percent, float(self.config.max_risk_percent))

        risk_dollars = self.account_equity * (adaptive_risk_percent / 100)

        stop_distance = abs(price - stop_price)
        if stop_distance <= 0:
            stop_distance = price * 0.005

        instrument = str(getattr(self.config, "instrument", "MES"))
        point_value = self.valuation_engine.point_value_for(instrument)
        risk_per_contract = max(1e-9, stop_distance * point_value)
        qty = max(1, int(risk_dollars / risk_per_contract))
        if self.app is not None and hasattr(self.app, "logger"):
            self.app.logger.info(
                f"ADAPTIVE_RISK,mode={mode},regime={regime},kelly={kelly_fraction:.2f},"
                f"risk_percent={adaptive_risk_percent:.2f},qty={qty}"
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
        if self.regime_detector is not None:
            try:
                structure = None
                if hasattr(df, "__len__") and len(df) >= 20:
                    structure = detect_market_structure(df)
                snapshot = self.regime_detector.detect(
                    df,
                    instrument=str(getattr(self.config, "instrument", "MES JUN26")),
                    confluence_score=float(self.get_current_dream_snapshot().get("confluence_score", 0.0) or 0.0),
                    structure=structure,
                )
                self.current_regime_snapshot = snapshot.to_dict()
                return snapshot.label
            except Exception:
                pass
        regime = detect_market_regime(df)
        self.current_regime_snapshot = {
            "label": str(regime),
            "confidence": 0.5,
            "risk_state": "NORMAL",
            "adaptive_policy": {
                "fast_path_weight": 0.5,
                "agent_route": ["risk", "scalper", "swing"],
                "risk_multiplier": 1.0,
                "emotional_twin_sensitivity": 1.0,
                "cooldown_minutes": 30,
                "high_risk": False,
                "nightly_evolution_focus": str(regime).lower(),
            },
        }
        return regime

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
        # Fase 3.3: guard against accidentally accessing early-init slots.
        if name in {"dream_state", "bible_engine", "market_data", "config", "app"}:
            raise AttributeError(name)

        if self.app is not None and hasattr(self.app, name):
            import warnings  # noqa: PLC0415
            warnings.warn(
                f"LuminaEngine: accessing '{name}' via app-delegation shim is deprecated. "
                f"Add an explicit attribute to LuminaEngine or access self.app.{name} directly.",
                DeprecationWarning,
                stacklevel=2,
            )
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
            import warnings  # noqa: PLC0415
            warnings.warn(
                f"LuminaEngine: setting '{name}' via app-delegation shim is deprecated. "
                f"Add an explicit attribute to LuminaEngine or set self.app.{name} directly.",
                DeprecationWarning,
                stacklevel=2,
            )
            setattr(self.app, name, value)
            return
        object.__setattr__(self, name, value)

from __future__ import annotations

import os
from pathlib import Path
import json
from functools import lru_cache
from typing import Any

from pydantic import BaseModel, ConfigDict, Field, field_validator
import yaml


@lru_cache(maxsize=1)
def _load_yaml_config() -> dict:
    config_path = Path("config.yaml")
    if not config_path.exists():
        return {}
    try:
        raw = yaml.safe_load(config_path.read_text(encoding="utf-8"))
    except Exception:
        return {}
    return raw if isinstance(raw, dict) else {}


def _config_yaml_value(key: str, default):
    config = _load_yaml_config()
    if key in config:
        return config[key]
    trading_cfg = config.get("trading", {}) if isinstance(config.get("trading"), dict) else {}
    return trading_cfg.get(key, default)


def _config_yaml_section_value(section: str, key: str, default):
    config = _load_yaml_config()
    section_cfg = config.get(section)
    if isinstance(section_cfg, dict) and key in section_cfg:
        return section_cfg.get(key, default)
    return default


def _config_yaml_section(section: str) -> dict:
    config = _load_yaml_config()
    section_cfg = config.get(section)
    return section_cfg if isinstance(section_cfg, dict) else {}


def _config_yaml_nested(default, *keys: str):
    current: Any = _load_yaml_config()
    for key in keys:
        if not isinstance(current, dict):
            return default
        current = current.get(key)
    return default if current is None else current


def _env_or_yaml(env_name: str, yaml_key: str, default):
    raw = os.getenv(env_name)
    if raw is not None:
        return raw
    return _config_yaml_value(yaml_key, default)


def _env_or_yaml_bool(env_name: str, yaml_key: str, default: bool) -> bool:
    raw = _env_or_yaml(env_name, yaml_key, default)
    if isinstance(raw, bool):
        return raw
    return str(raw).strip().lower() == "true"


def _env_or_yaml_float(env_name: str, yaml_key: str, default: float) -> float:
    raw = _env_or_yaml(env_name, yaml_key, default)
    try:
        return float(raw)
    except (TypeError, ValueError):
        return float(default)


def _safe_dict(value) -> dict:
    return value if isinstance(value, dict) else {}


def _parse_swarm_symbols() -> list[str]:
    raw = os.getenv("SWARM_SYMBOLS", "MES JUN26,MNQ JUN26,MYM JUN26,ES JUN26").strip()
    if not raw:
        return ["MES JUN26", "MNQ JUN26", "MYM JUN26", "ES JUN26"]

    symbols: list[str]
    if raw.startswith("["):
        try:
            parsed = json.loads(raw)
            symbols = [str(s).strip().upper() for s in parsed if str(s).strip()]
        except Exception:
            symbols = []
    else:
        symbols = [part.strip().upper() for part in raw.split(",") if part.strip()]

    return symbols or ["MES JUN26", "MNQ JUN26", "MYM JUN26", "ES JUN26"]


class EngineConfig(BaseModel):
    """Validated runtime configuration for the OOP engine."""

    model_config = ConfigDict(arbitrary_types_allowed=True)

    state_file: Path = Field(default_factory=lambda: Path("state/lumina_sim_state.json"))
    thought_log: Path = Field(default_factory=lambda: Path("state/lumina_thought_log.jsonl"))
    bible_file: Path = Field(default_factory=lambda: Path("state/lumina_daytrading_bible.json"))
    live_jsonl: Path = Field(default_factory=lambda: Path("state/live_stream.jsonl"))
    trade_reconciler_status_file: Path = Field(
        default_factory=lambda: Path(os.getenv("TRADE_RECONCILER_STATUS_FILE", "state/trade_reconciler_status.json"))
    )
    trade_reconciler_audit_log: Path = Field(
        default_factory=lambda: Path(os.getenv("TRADE_RECONCILER_AUDIT_LOG", "logs/trade_fill_audit.jsonl"))
    )
    trade_decision_audit_log: Path = Field(
        default_factory=lambda: Path(
            str(
                os.getenv("TRADE_DECISION_AUDIT_LOG")
                or _config_yaml_nested("logs/trade_decision_audit.jsonl", "audit", "trade_decision_jsonl")
                or "logs/trade_decision_audit.jsonl"
            )
        )
    )
    trade_decision_audit_fail_closed_real: bool = Field(
        default_factory=lambda: str(
            os.getenv("TRADE_DECISION_AUDIT_FAIL_CLOSED_REAL") or _config_yaml_nested(True, "audit", "fail_closed_real")
        )
        .strip()
        .lower()
        == "true"
    )

    instrument: str = Field(default_factory=lambda: os.getenv("INSTRUMENT", "MES JUN26"))
    swarm_symbols: list[str] = Field(default_factory=_parse_swarm_symbols)
    swarm_enabled: bool = Field(default_factory=lambda: os.getenv("SWARM_ENABLED", "True").lower() == "true")
    supported_swarm_roots: list[str] = Field(default_factory=lambda: ["MES", "MNQ", "MYM", "ES"])
    xai_key: str | None = Field(
        default_factory=lambda: str(
            os.getenv("XAI_API_KEY") or _config_yaml_section_value("xai", "api_key", "")
        ).strip()
        or None
    )
    xai_model: str = Field(
        default_factory=lambda: str(_config_yaml_section_value("xai", "model", "grok-4.1-fast")).strip()
        or "grok-4.1-fast"
    )
    xai_update_interval_sec: int = Field(
        default_factory=lambda: int(_config_yaml_section_value("xai", "update_interval_sec", 60) or 60)
    )
    finnhub_api_key: str | None = Field(default_factory=lambda: os.getenv("FINNHUB_API_KEY"))
    broker_backend: str = Field(
        default_factory=lambda: str(
            os.getenv("BROKER_BACKEND") or _config_yaml_nested("paper", "broker", "backend") or "paper"
        )
        .strip()
        .lower()
    )
    broker_crosstrade_api_key: str | None = Field(
        default_factory=lambda: str(
            os.getenv("BROKER_CROSSTRADE_API_KEY")
            or os.getenv("CROSSTRADE_TOKEN")
            or _config_yaml_nested("", "broker", "crosstrade", "api_key")
            or ""
        ).strip()
        or None
    )
    broker_crosstrade_websocket_url: str = Field(
        default_factory=lambda: str(
            os.getenv("BROKER_CROSSTRADE_WEBSOCKET_URL")
            or os.getenv("CROSSTRADE_FILL_WS_URL")
            or _config_yaml_nested("wss://app.crosstrade.io/ws/stream", "broker", "crosstrade", "websocket_url")
            or "wss://app.crosstrade.io/ws/stream"
        ).strip()
    )
    broker_crosstrade_base_url: str = Field(
        default_factory=lambda: str(
            os.getenv("BROKER_CROSSTRADE_BASE_URL")
            or _config_yaml_nested("https://app.crosstrade.io", "broker", "crosstrade", "base_url")
            or "https://app.crosstrade.io"
        ).strip()
    )
    crosstrade_token: str | None = Field(
        default_factory=lambda: str(
            os.getenv("CROSSTRADE_TOKEN") or os.getenv("BROKER_CROSSTRADE_API_KEY") or ""
        ).strip()
        or None
    )
    crosstrade_account: str = Field(default_factory=lambda: os.getenv("CROSSTRADE_ACCOUNT", "DEMO5042070"))
    reconcile_fills: bool = Field(default_factory=lambda: _env_or_yaml_bool("RECONCILE_FILLS", "reconcile_fills", True))
    reconciliation_method: str = Field(
        default_factory=lambda: str(_env_or_yaml("RECONCILIATION_METHOD", "reconciliation_method", "websocket"))
        .strip()
        .lower()
    )
    reconciliation_timeout_seconds: float = Field(
        default_factory=lambda: _env_or_yaml_float(
            "RECONCILIATION_TIMEOUT_SECONDS", "reconciliation_timeout_seconds", 15.0
        )
    )
    use_real_fill_for_pnl: bool = Field(
        default_factory=lambda: _env_or_yaml_bool("USE_REAL_FILL_FOR_PNL", "use_real_fill_for_pnl", True)
    )
    crosstrade_fill_ws_url: str = Field(
        default_factory=lambda: str(
            os.getenv("CROSSTRADE_FILL_WS_URL")
            or os.getenv("BROKER_CROSSTRADE_WEBSOCKET_URL")
            or "wss://app.crosstrade.io/ws/stream"
        ).strip()
    )
    crosstrade_fill_poll_url: str = Field(
        default_factory=lambda: str(os.getenv("CROSSTRADE_FILL_POLL_URL", "")).strip()
    )

    trade_mode: str = Field(
        default_factory=lambda: str(
            os.getenv("LUMINA_MODE")
            or os.getenv("TRADE_MODE")
            or _config_yaml_value("mode", "")
            or (
                "real"
                if str(os.getenv("BROKER_BACKEND") or _config_yaml_nested("paper", "broker", "backend") or "paper")
                .strip()
                .lower()
                == "live"
                else "paper"
            )
        )
        .strip()
        .lower()
    )

    @field_validator("trade_mode")
    @classmethod
    def _validate_trade_mode(cls, value: str) -> str:
        normalized = str(value or "").strip().lower()
        allowed = {"paper", "sim", "sim_real_guard", "real"}
        if normalized not in allowed:
            raise ValueError("TRADE_MODE must be one of: paper, sim, sim_real_guard, real")
        return normalized

    max_risk_percent: float = Field(default_factory=lambda: float(os.getenv("MAX_RISK_PERCENT", 1.0)))
    drawdown_kill_percent: float = Field(default_factory=lambda: float(os.getenv("DRAWDOWN_KILL_PERCENT", 8.0)))

    use_human_main_loop: bool = Field(
        default_factory=lambda: os.getenv("USE_HUMAN_MAIN_LOOP", "True").lower() == "true"
    )
    start_pre_dream_backup: bool = Field(
        default_factory=lambda: os.getenv("START_PRE_DREAM_BACKUP", "False").lower() == "true"
    )
    screen_share_enabled: bool = Field(
        default_factory=lambda: os.getenv("SCREEN_SHARE_ENABLED", "True").lower() == "true"
    )
    dashboard_enabled: bool = Field(default_factory=lambda: os.getenv("DASHBOARD_ENABLED", "True").lower() == "true")
    voice_input_enabled: bool = Field(
        default_factory=lambda: os.getenv("VOICE_INPUT_ENABLED", "True").lower() == "true"
    )
    vision_model: str = Field(default_factory=lambda: os.getenv("VISION_MODEL", "grok-4-vision-0309"))
    voice_wake_word: str = Field(default_factory=lambda: os.getenv("VOICE_WAKE_WORD", "lumina").strip().lower())
    dashboard_chart_refresh_sec: int = Field(
        default_factory=lambda: int(os.getenv("DASHBOARD_CHART_REFRESH_SEC", "20"))
    )
    blackboard_health_latency_amber_ms: float = Field(
        default_factory=lambda: float(os.getenv("BLACKBOARD_HEALTH_LATENCY_AMBER_MS", "250.0"))
    )
    blackboard_health_latency_red_ms: float = Field(
        default_factory=lambda: float(os.getenv("BLACKBOARD_HEALTH_LATENCY_RED_MS", "1000.0"))
    )
    blackboard_health_min_confidence: float = Field(
        default_factory=lambda: float(os.getenv("BLACKBOARD_HEALTH_MIN_CONFIDENCE", "0.80"))
    )
    blackboard_health_trend_points: int = Field(
        default_factory=lambda: int(os.getenv("BLACKBOARD_HEALTH_TREND_POINTS", "30"))
    )
    status_print_interval_sec: float = Field(
        default_factory=lambda: float(os.getenv("STATUS_PRINT_INTERVAL_SEC", "5.0"))
    )
    event_threshold: float = Field(default_factory=lambda: float(os.getenv("EVENT_THRESHOLD", "0.003")))
    journal_dir: Path = Field(default_factory=lambda: Path(os.getenv("JOURNAL_DIR", "journal")))
    journal_pdf_dir: Path = Field(default_factory=lambda: Path(os.getenv("JOURNAL_PDF_DIR", "journal/pdf")))
    discord_webhook: str = Field(default_factory=lambda: os.getenv("DISCORD_WEBHOOK", ""))
    risk_profile: str = Field(default_factory=lambda: os.getenv("LUMINA_RISK_PROFILE", "Balanced").lower())
    participant_id: str = Field(
        default_factory=lambda: str(
            os.getenv("LUMINA_TRADER_NAME")
            or os.getenv("TRADERLEAGUE_PARTICIPANT_HANDLE")
            or _config_yaml_value("participant_id", "LUMINA_Steve")
            or "LUMINA_Steve"
        ).strip()
    )
    news_avoidance_minutes: int = Field(
        default_factory=lambda: int(_config_yaml_value("news_avoidance_minutes", 3) or 3)
    )
    timeframes: dict[str, int] = Field(
        default_factory=lambda: {
            "5min": 300,
            "15min": 900,
            "30min": 1800,
            "60min": 3600,
            "240min": 14400,
            "1440min": 86400,
        }
    )
    agent_styles: dict[str, str] = Field(
        default_factory=lambda: {
            "scalper": "Je bent een agressieve scalper die focust op tape-reading, volume spikes en 1-5 min momentum.",
            "swing": "Je bent een geduldige swing-trader die higher-highs/lower-lows, fibs en MTF structure gebruikt.",
            "risk": "Je bent een strenge risk-manager die alleen trades toestaat met 1:2+ RR, lage drawdown en hoge confluence.",
        }
    )
    news_impact_multipliers: dict[str, float] = Field(
        default_factory=lambda: {
            "high_bullish": float(
                _safe_dict(_config_yaml_value("news_impact_multipliers", {})).get("high_bullish", 1.3)
            ),
            "high_bearish": float(
                _safe_dict(_config_yaml_value("news_impact_multipliers", {})).get("high_bearish", 0.6)
            ),
            "high_neutral": float(
                _safe_dict(_config_yaml_value("news_impact_multipliers", {})).get("high_neutral", 0.9)
            ),
            "medium_bullish": float(
                _safe_dict(_config_yaml_value("news_impact_multipliers", {})).get("medium_bullish", 1.1)
            ),
            "medium_bearish": float(
                _safe_dict(_config_yaml_value("news_impact_multipliers", {})).get("medium_bearish", 0.9)
            ),
            "medium_neutral": float(
                _safe_dict(_config_yaml_value("news_impact_multipliers", {})).get("medium_neutral", 1.0)
            ),
        }
    )
    regime_risk_multipliers: dict[str, float] = Field(
        default_factory=lambda: {
            "TRENDING": 1.4,
            "BREAKOUT": 1.6,
            "VOLATILE": 0.7,
            "RANGING": 0.5,
            "NEUTRAL": 0.9,
        }
    )
    risk_controller: dict[str, Any] = Field(default_factory=lambda: _config_yaml_section("risk_controller"))
    regime: dict[str, Any] = Field(default_factory=lambda: _config_yaml_section("regime"))
    session: dict[str, Any] = Field(default_factory=lambda: _config_yaml_section("session"))
    portfolio_var: dict[str, Any] = Field(default_factory=lambda: _config_yaml_section("portfolio_var"))
    fine_tuning: dict[str, Any] = Field(default_factory=lambda: _config_yaml_section("fine_tuning"))

    @property
    def min_confluence(self) -> float:
        profile = self.risk_profile
        if profile == "conservative":
            return 0.82
        if profile == "aggressive":
            return 0.65
        return 0.75

    @property
    def dry_run(self) -> bool:
        return os.getenv("DRY_RUN", "True").lower() == "true"

    @property
    def simulate_trades(self) -> bool:
        simulated = os.getenv("SIMULATE_TRADES", "True").lower() == "true"
        return simulated if self.dry_run else False

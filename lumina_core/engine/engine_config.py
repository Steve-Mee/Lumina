from __future__ import annotations

import os
from pathlib import Path
import json

from pydantic import BaseModel, ConfigDict, Field


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

    state_file: Path = Field(default_factory=lambda: Path("lumina_sim_state.json"))
    thought_log: Path = Field(default_factory=lambda: Path("lumina_thought_log.jsonl"))
    bible_file: Path = Field(default_factory=lambda: Path("lumina_daytrading_bible.json"))
    live_jsonl: Path = Field(default_factory=lambda: Path("live_stream.jsonl"))

    instrument: str = Field(default_factory=lambda: os.getenv("INSTRUMENT", "MES JUN26"))
    swarm_symbols: list[str] = Field(default_factory=_parse_swarm_symbols)
    swarm_enabled: bool = Field(default_factory=lambda: os.getenv("SWARM_ENABLED", "True").lower() == "true")
    supported_swarm_roots: list[str] = Field(default_factory=lambda: ["MES", "MNQ", "MYM", "ES"])
    xai_key: str | None = Field(default_factory=lambda: os.getenv("XAI_API_KEY"))
    finnhub_api_key: str | None = Field(default_factory=lambda: os.getenv("FINNHUB_API_KEY"))
    crosstrade_token: str | None = Field(default_factory=lambda: os.getenv("CROSSTRADE_TOKEN"))
    crosstrade_account: str = Field(default_factory=lambda: os.getenv("CROSSTRADE_ACCOUNT", "DEMO5042070"))

    trade_mode: str = Field(default_factory=lambda: os.getenv("TRADE_MODE", "paper").lower())
    max_risk_percent: float = Field(default_factory=lambda: float(os.getenv("MAX_RISK_PERCENT", 1.0)))
    drawdown_kill_percent: float = Field(default_factory=lambda: float(os.getenv("DRAWDOWN_KILL_PERCENT", 8.0)))

    use_human_main_loop: bool = Field(default_factory=lambda: os.getenv("USE_HUMAN_MAIN_LOOP", "True").lower() == "true")
    start_pre_dream_backup: bool = Field(default_factory=lambda: os.getenv("START_PRE_DREAM_BACKUP", "False").lower() == "true")
    screen_share_enabled: bool = Field(default_factory=lambda: os.getenv("SCREEN_SHARE_ENABLED", "True").lower() == "true")
    dashboard_enabled: bool = Field(default_factory=lambda: os.getenv("DASHBOARD_ENABLED", "True").lower() == "true")
    voice_input_enabled: bool = Field(default_factory=lambda: os.getenv("VOICE_INPUT_ENABLED", "True").lower() == "true")
    vision_model: str = Field(default_factory=lambda: os.getenv("VISION_MODEL", "grok-4-vision-0309"))
    voice_wake_word: str = Field(default_factory=lambda: os.getenv("VOICE_WAKE_WORD", "lumina").strip().lower())
    dashboard_chart_refresh_sec: int = Field(default_factory=lambda: int(os.getenv("DASHBOARD_CHART_REFRESH_SEC", "20")))
    status_print_interval_sec: float = Field(default_factory=lambda: float(os.getenv("STATUS_PRINT_INTERVAL_SEC", "5.0")))
    event_threshold: float = Field(default_factory=lambda: float(os.getenv("EVENT_THRESHOLD", "0.003")))
    journal_dir: Path = Field(default_factory=lambda: Path(os.getenv("JOURNAL_DIR", "journal")))
    journal_pdf_dir: Path = Field(default_factory=lambda: Path(os.getenv("JOURNAL_PDF_DIR", "journal/pdf")))
    discord_webhook: str = Field(default_factory=lambda: os.getenv("DISCORD_WEBHOOK", ""))
    risk_profile: str = Field(default_factory=lambda: os.getenv("LUMINA_RISK_PROFILE", "Balanced").lower())
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
            "high_bullish": 1.3,
            "high_bearish": 0.6,
            "high_neutral": 0.9,
            "medium_bullish": 1.1,
            "medium_bearish": 0.9,
            "medium_neutral": 1.0,
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

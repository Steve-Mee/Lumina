from __future__ import annotations

import json
import logging
from pathlib import Path
from types import SimpleNamespace
from typing import Any, cast

import pandas as pd

from lumina_core.engine.performance_validator import PerformanceValidator


class _FakeBacktesterEngine:
    def __init__(self, app):
        self.app = app

    def run_snapshot_backtest(self, snapshot):
        _ = snapshot
        return {
            "trades": 120,
            "sharpe": 1.45,
            "winrate": 0.61,
            "maxdd": 4.8,
            "net_pnl": 150000.0,
            "monte_carlo": {"runs": 500, "mean_pnl": 149000.0},
            "walk_forward": {"windows": 10, "mean_sharpe": 1.31},
            "walk_forward_optimization": {"windows": 8, "mean_test_sharpe": 1.22},
        }


class _FakeAdvancedBacktester:
    def walk_forward_test(self, _df: pd.DataFrame) -> dict:
        return {
            "avg_test_sharpe": 1.33,
            "worst_test_maxdd": 5.9,
            "num_windows": 12,
        }

    def full_monte_carlo(self, _df: pd.DataFrame, runs: int = 500) -> dict:
        return {
            "num_runs": runs,
            "mean_sharpe": 1.42,
            "worst_maxdd": 6.8,
            "winrate_5pct": 0.56,
        }


class _FakePPOTrainer:
    def train_nightly_on_infinite_simulator(self, simulator_data, timesteps: int = 300_000) -> str:
        _ = simulator_data
        _ = timesteps
        return "lumina_agents/ppo/lumina_ppo_policy.zip"


class _FakeMarketDataService:
    def __init__(self, df: pd.DataFrame):
        self._df = df

    def load_historical_ohlc_for_symbol(self, instrument: str, days_back: int, limit: int) -> pd.DataFrame:
        _ = instrument
        _ = days_back
        _ = limit
        return self._df.copy()

    def load_historical_ohlc_extended(self, days_back: int, limit: int) -> list[dict]:
        _ = days_back
        _ = limit
        return self._df.to_dict("records")


class _AppLogger:
    def __init__(self):
        self._logger = logging.getLogger("performance-validator-test")

    def info(self, *args, **kwargs):
        self._logger.info(*args, **kwargs)

    def error(self, *args, **kwargs):
        self._logger.error(*args, **kwargs)

    def warning(self, *args, **kwargs):
        self._logger.warning(*args, **kwargs)

    def critical(self, *args, **kwargs):
        self._logger.critical(*args, **kwargs)


class _FakeApp:
    def __init__(self):
        self.logger = _AppLogger()
        self.SWARM_SYMBOLS = ["MES JUN26", "MNQ JUN26"]
        self.logged_thoughts: list[dict] = []
        self.feedback_events: list[dict] = []

    def log_thought(self, payload: dict):
        self.logged_thoughts.append(dict(payload))

    def process_user_feedback(self, text: str, trade_data: dict | None = None):
        self.feedback_events.append({"text": text, "trade_data": dict(trade_data or {})})


def _build_ohlc_df(n: int = 2400) -> pd.DataFrame:
    base = pd.date_range("2023-01-01", periods=n, freq="h")
    close = pd.Series([5000.0 + (i * 0.05) for i in range(n)])
    return pd.DataFrame(
        {
            "timestamp": base,
            "open": close - 0.1,
            "high": close + 0.2,
            "low": close - 0.3,
            "close": close,
            "volume": 1000,
        }
    )


def _write_real_audit(path: Path) -> None:
    rows = []
    running_pnl = 0.0
    for i in range(1, 51):
        pnl = 200.0 + i * 1.5
        running_pnl += pnl
        rows.append(
            {
                "event": "reconciled",
                "ts": f"2026-01-{(i % 28) + 1:02d}T12:00:00+00:00",
                "pnl": pnl,
                "cum": running_pnl,
            }
        )
    path.write_text("\n".join(json.dumps(x) for x in rows), encoding="utf-8")


def _build_validator(tmp_path: Path, monkeypatch) -> PerformanceValidator:
    app = _FakeApp()
    engine = SimpleNamespace(
        app=app,
        config=SimpleNamespace(instrument="MES JUN26"),
        equity_curve=[50000.0 + i * 220.0 for i in range(220)],
        account_equity=98500.0,
        account_balance=96000.0,
        open_pnl=500.0,
        realized_pnl_today=300.0,
        trade_log=[{"pnl": 120.0}] * 25,
        advanced_backtester=_FakeAdvancedBacktester(),
    )

    monkeypatch.setattr(
        "lumina_core.engine.performance_validator.BacktesterEngine",
        _FakeBacktesterEngine,
    )

    market = _FakeMarketDataService(_build_ohlc_df())
    trainer = _FakePPOTrainer()

    validator = PerformanceValidator(
        engine=cast(Any, engine),
        market_data_service=cast(Any, market),
        ppo_trainer=cast(Any, trainer),
        report_dir=tmp_path / "reports",
        real_audit_path=tmp_path / "trade_fill_audit.jsonl",
        monte_carlo_runs=50,
    )
    _write_real_audit(validator.real_audit_path)
    return validator


def test_run_3year_validation_generates_json_and_pdf(tmp_path: Path, monkeypatch) -> None:
    validator = _build_validator(tmp_path, monkeypatch)

    result = validator.run_3year_validation()

    assert result["status"] == "goal_met"
    assert result["goal_met"] is True
    assert result["mean_monthly_return"] >= 5.0
    assert result["mean_monthly_return"] <= 10.0
    assert result["worst_maxdd"] < 8.0
    assert result["num_symbols"] == 2

    json_path = Path(str(result["json_path"]))
    pdf_path = Path(str(result["monthly_pdf"]))
    assert json_path.exists()
    assert pdf_path.exists()


def test_run_validation_cycle_triggers_emergency_on_goal_miss(tmp_path: Path, monkeypatch) -> None:
    validator = _build_validator(tmp_path, monkeypatch)

    def _missed_summary() -> dict:
        return {
            "timestamp": "2026-04-06T00:00:00",
            "symbols": [],
            "aggregate": {
                "mean_monthly_return": 0.02,
                "worst_maxdd": 13.2,
                "mean_sharpe": 0.4,
                "mean_winrate": 0.43,
                "consistency_ratio": 0.0,
                "net_pnl": -5000.0,
                "trades": 5,
            },
            "side_by_side": {
                "correlation": 0.21,
                "paper_sharpe": 0.3,
                "real_sharpe": -0.2,
                "divergence_alert": True,
                "paper_curve": [50000.0, 49900.0],
                "real_curve": [50000.0, 50300.0],
                "paper_points": 2,
                "real_points": 2,
                "paper_equity_last": 49900.0,
                "real_equity_last": 50300.0,
            },
            "goals": validator._goal_targets(),
            "goal_met": False,
            "json_path": str(tmp_path / "stub.json"),
            "monthly_pdf": str(tmp_path / "stub.pdf"),
        }

    monkeypatch.setattr(
        PerformanceValidator,
        "run_full_swarm_validation_3y",
        lambda self: _missed_summary(),
    )
    monkeypatch.setattr(
        PerformanceValidator,
        "_generate_monthly_pdf",
        lambda self, _summary=None: str(tmp_path / "stub.pdf"),
    )

    result = validator.run_validation_cycle()

    emergency = dict(result.get("emergency_actions", {}))
    assert emergency.get("dna_rewrite") is True
    assert emergency.get("rl_retrain") is True
    assert str(emergency.get("rl_policy_path", "")).endswith(".zip")
    assert emergency.get("alert_sent") is False

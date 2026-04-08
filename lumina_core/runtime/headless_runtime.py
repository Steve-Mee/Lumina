# CANONICAL IMPLEMENTATION – Lumina v51
# HeadlessRuntime: deterministic, non-UI trade-loop runner for CI/CD and smoke validation.
# Outputs structured JSON summary to stdout + state/last_run_summary.json.
from __future__ import annotations

import json
import logging
import math
import os
import random
import statistics
import time
from datetime import datetime, timezone
from pathlib import Path
from types import SimpleNamespace
from typing import Any

import yaml

logger = logging.getLogger("lumina.headless")

_DEFAULT_SUMMARY_PATH = Path("state/last_run_summary.json")
_SUMMARY_PATH = _DEFAULT_SUMMARY_PATH
_SUMMARY_SCHEMA_VERSION = "1.0"
_DEFAULT_SIMULATION_SEED = 51


def _load_headless_config() -> dict[str, Any]:
    config_path = Path("config.yaml")
    if not config_path.exists():
        return {}
    try:
        payload = yaml.safe_load(config_path.read_text(encoding="utf-8"))
    except Exception:
        return {}
    if not isinstance(payload, dict):
        return {}
    section = payload.get("headless")
    return section if isinstance(section, dict) else {}


def _resolve_simulation_seed(cfg: dict[str, Any]) -> int:
    env_seed = os.getenv("LUMINA_HEADLESS_SEED")
    if env_seed is not None:
        try:
            return int(env_seed)
        except ValueError:
            logger.warning("Invalid LUMINA_HEADLESS_SEED=%r; using defaults", env_seed)

    raw = cfg.get("simulation_seed", _DEFAULT_SIMULATION_SEED)
    try:
        seed = int(raw)
    except (TypeError, ValueError):
        seed = _DEFAULT_SIMULATION_SEED

    # Enforce deterministic behavior by default.
    if seed == 0:
        return _DEFAULT_SIMULATION_SEED
    return seed


def _resolve_ticks_per_minute(cfg: dict[str, Any]) -> int:
    raw = cfg.get("ticks_per_minute", 200)
    try:
        value = int(raw)
    except (TypeError, ValueError):
        value = 200
    return max(1, value)


def _resolve_summary_path(cfg: dict[str, Any]) -> Path:
    env_path = os.getenv("LUMINA_HEADLESS_SUMMARY_PATH", "").strip()
    if env_path:
        return Path(env_path)

    if _SUMMARY_PATH != _DEFAULT_SUMMARY_PATH:
        return _SUMMARY_PATH

    cfg_path = str(cfg.get("summary_output_path", "")).strip()
    if cfg_path:
        return Path(cfg_path)
    return _SUMMARY_PATH

# ---------------------------------------------------------------------------
# Internal fast-path simulation kernel
# ---------------------------------------------------------------------------

def _generate_synthetic_ticks(n: int, seed: int, start_price: float = 5000.0) -> list[dict[str, Any]]:
    """Generate n synthetic price ticks for a rapid paper simulation."""
    rng = random.Random(seed)
    regimes = ["TRENDING_UP", "TRENDING_DOWN", "RANGING", "NEUTRAL"]
    ticks: list[dict[str, Any]] = []
    price = start_price
    regime_idx = 0
    regime_ticks = 0
    regime_dur = rng.randint(40, 120)

    for _ in range(n):
        regime_ticks += 1
        if regime_ticks >= regime_dur:
            regime_idx = (regime_idx + 1) % len(regimes)
            regime_dur = rng.randint(40, 120)
            regime_ticks = 0

        regime = regimes[regime_idx]
        drift = 0.12 if regime == "TRENDING_UP" else (-0.12 if regime == "TRENDING_DOWN" else 0.0)
        price += drift + rng.gauss(0, 0.4)
        price = max(100.0, price)

        ticks.append({
            "last": round(price, 2),
            "volume": rng.uniform(80, 1200),
            "regime": regime,
            "imbalance": rng.uniform(0.5, 2.0),
        })
    return ticks


def _run_simulation(
    ticks: list[dict[str, Any]],
    seed: int,
    symbol: str = "MES",
    point_value: float = 5.0,
    commission_per_side: float = 2.55,
) -> dict[str, Any]:
    """
    Core simulation loop.  Processes ticks and returns trade statistics.
    Deliberately fast (pure Python, sub-second for <=50 k ticks).
    """
    rng = random.Random(seed)
    pnl_values: list[float] = []
    running_pnl = 0.0
    peak_pnl = 0.0
    max_drawdown = 0.0
    risk_events = 0
    var_events = 0
    var_limit_usd = 1200.0
    daily_loss_cap = -1000.0

    position = 0
    qty = 1
    entry = 0.0
    stop = 0.0
    target = 0.0
    hold_ticks = 0

    for tick in ticks:
        price = float(tick["last"])
        regime = str(tick["regime"])
        imbalance = float(tick["imbalance"])

        if position == 0:
            entry_prob = 0.22 if "TREND" in regime else 0.14
            if rng.random() < entry_prob:
                side = 1 if (imbalance >= 1.0 and rng.random() < 0.55) else -1
                if "RANGING" in regime and rng.random() < 0.6:
                    side *= -1
                position = side
                qty = rng.randint(1, 3)
                entry = price
                sl_dist = 0.25 * rng.uniform(0.6, 1.4)
                tp_dist = 0.25 * rng.uniform(1.2, 3.0)
                stop = entry - sl_dist * position
                target = entry + tp_dist * position
                hold_ticks = 0
            continue

        hold_ticks += 1
        stop_hit = (position > 0 and price <= stop) or (position < 0 and price >= stop)
        target_hit = (position > 0 and price >= target) or (position < 0 and price <= target)
        timed_exit = hold_ticks >= 24

        if stop_hit or target_hit or timed_exit:
            gross = (price - entry) * position * qty * point_value
            net = gross - commission_per_side * 2.0 * qty
            pnl_values.append(net)
            running_pnl += net

            if running_pnl > peak_pnl:
                peak_pnl = running_pnl
            drawdown = peak_pnl - running_pnl
            if drawdown > max_drawdown:
                max_drawdown = drawdown

            # Risk event: trade loss exceeds 10% of daily cap in a single trade
            if net < abs(daily_loss_cap) * 0.10 * -1:
                risk_events += 1

            # VaR-proxy breach: potential per-trade risk > 80% of VaR limit
            open_risk = abs(entry - stop) * qty * point_value
            if open_risk > var_limit_usd * 0.80:
                var_events += 1

            position = 0
            qty = 1
            hold_ticks = 0

    total = len(pnl_values)
    net_pnl = float(sum(pnl_values)) if pnl_values else 0.0
    wins = sum(1 for p in pnl_values if p > 0)
    mean_pnl = float(statistics.mean(pnl_values)) if pnl_values else 0.0
    std_pnl = float(statistics.pstdev(pnl_values)) if len(pnl_values) > 1 else 0.0
    sharpe = (mean_pnl / std_pnl) * math.sqrt(252.0) if std_pnl > 1e-9 else 0.0

    return {
        "total_trades": total,
        "pnl_realized": round(net_pnl, 2),
        "max_drawdown": round(max_drawdown, 2),
        "risk_events": risk_events,
        "var_breach_count": var_events,
        "wins": wins,
        "win_rate": round(wins / total, 4) if total > 0 else 0.0,
        "mean_pnl_per_trade": round(mean_pnl, 2),
        "sharpe_annualized": round(sharpe, 4),
    }


# ---------------------------------------------------------------------------
# Broker validation helper
# ---------------------------------------------------------------------------

def _validate_broker(broker_mode: str) -> str:
    """
    Instantiate and connect the appropriate broker bridge.
    Returns a human-readable status string; never raises.
    """
    if broker_mode != "live":
        return "paper_ok"

    try:
        from lumina_core.engine.broker_bridge import broker_factory

        config = SimpleNamespace(
            broker_backend="live",
            broker_crosstrade_api_key=os.getenv("CROSSTRADE_TOKEN", "headless-validation-stub"),
            crosstrade_token=os.getenv("CROSSTRADE_TOKEN", "headless-validation-stub"),
            crosstrade_account=os.getenv("CROSSTRADE_ACCOUNT", "DEMO5042070"),
            broker_crosstrade_websocket_url=os.getenv(
                "CROSSTRADE_WS_URL", "wss://app.crosstrade.io/ws/stream"
            ),
            broker_crosstrade_base_url="https://app.crosstrade.io",
            crosstrade_fill_poll_url="",
        )
        broker = broker_factory(config=config)
        connected = broker.connect()
        return "live_connected" if connected else "live_connect_failed"
    except Exception as exc:
        logger.warning("Live broker validation error: %s", exc)
        return f"live_error:{type(exc).__name__}"


# ---------------------------------------------------------------------------
# Session guard helper
# ---------------------------------------------------------------------------

def _check_session_guard() -> int:
    """Return 1 if the current moment is outside the CME trading session, else 0."""
    try:
        from lumina_core.engine.session_guard import SessionGuard

        guard = SessionGuard()
        return 0 if guard.is_trading_session() else 1
    except Exception as exc:
        logger.debug("Session guard check skipped: %s", exc)
        return 0


# ---------------------------------------------------------------------------
# Evolution proposal counter
# ---------------------------------------------------------------------------

def _count_evolution_proposals(container: Any | None) -> int:
    if container is None:
        return 0
    try:
        log_path = Path("state/evolution_log.jsonl")
        if not log_path.exists():
            return 0
        count = 0
        for line in log_path.read_text(encoding="utf-8").splitlines():
            line = line.strip()
            if not line:
                continue
            try:
                obj = json.loads(line)
                if isinstance(obj, dict) and obj.get("status") in {"proposed", "pending"}:
                    count += 1
            except (json.JSONDecodeError, ValueError):
                pass
        return count
    except Exception:
        return 0


# ---------------------------------------------------------------------------
# Observability alert counter
# ---------------------------------------------------------------------------

def _count_observability_alerts(container: Any | None) -> int:
    if container is None:
        return 0
    try:
        obs = getattr(container, "observability_service", None)
        if obs is None:
            return 0
        collector = getattr(obs, "collector", None)
        if collector is None:
            return 0
        raw = collector.latest("lumina_alerts_sent_total")
        return int(raw) if raw is not None else 0
    except Exception:
        return 0


# ---------------------------------------------------------------------------
# Duration parser
# ---------------------------------------------------------------------------

def parse_duration_minutes(value: str) -> float:
    """
    Parse a duration string like "15m", "5m", "30s", "1h" into minutes.
    Raises ValueError for unrecognised formats.
    """
    value = value.strip().lower()
    if value.endswith("h"):
        return float(value[:-1]) * 60.0
    if value.endswith("m"):
        return float(value[:-1])
    if value.endswith("s"):
        return float(value[:-1]) / 60.0
    # Bare number treated as minutes
    return float(value)


# ---------------------------------------------------------------------------
# HeadlessRuntime
# ---------------------------------------------------------------------------

class HeadlessRuntime:
    """
    Deterministic headless trading runtime for smoke-test and CI/CD validation.

    Usage::

        runtime = HeadlessRuntime()
        summary = runtime.run(duration_minutes=15, mode="paper", broker_mode="paper")
        # summary is also printed to stdout as JSON and saved to
        # state/last_run_summary.json

    With an ApplicationContainer (optional; enables richer metrics)::

        container = create_application_container()
        runtime = HeadlessRuntime(container=container)
        summary = runtime.run(duration_minutes=5, mode="paper", broker_mode="live")
    """

    def __init__(self, container: Any | None = None) -> None:
        self._container = container
        self._logger = logging.getLogger("lumina.headless")

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def run(
        self,
        duration_minutes: int | float = 15,
        mode: str = "paper",
        broker_mode: str = "paper",
    ) -> dict[str, Any]:
        """
        Execute the headless trade loop for ``duration_minutes`` of simulated time.

        The simulation is deterministic and fast (sub-second for standard
        durations when no sleep is involved).  ``duration_minutes`` governs
        how many synthetic ticks are generated (proportional to typical CME
        session activity), not wall-clock wait time.

        Args:
            duration_minutes: Simulated session length in minutes (e.g. 15, 5).
            mode: Trading mode label – "paper" | "sim" | "real".
            broker_mode: Broker backend – "paper" | "live".

        Returns:
            Structured summary dict (also written to stdout and to disk).
        """
        cfg = _load_headless_config()

        started_at = datetime.now(timezone.utc).isoformat()
        seed = _resolve_simulation_seed(cfg)
        duration_minutes = float(duration_minutes)

        self._logger.info(
            "HeadlessRuntime.run started: mode=%s broker=%s duration=%.1fm",
            mode,
            broker_mode,
            duration_minutes,
        )

        ticks_per_minute = _resolve_ticks_per_minute(cfg)

        # Number of synthetic ticks proportional to duration.
        n_ticks = max(500, int(duration_minutes * ticks_per_minute))

        # --- Broker validation --------------------------------------------------
        broker_status = _validate_broker(broker_mode)

        # --- Session guard ------------------------------------------------------
        session_guard_blocks = _check_session_guard()

        # --- Core simulation ----------------------------------------------------
        ticks = _generate_synthetic_ticks(n=n_ticks, seed=seed)
        sim = _run_simulation(ticks, seed=seed)

        # --- Evolution proposals ------------------------------------------------
        evolution_proposals = _count_evolution_proposals(self._container)

        # --- Observability alerts -----------------------------------------------
        observability_alerts = _count_observability_alerts(self._container)

        # --- Compose summary ----------------------------------------------------
        finished_at = datetime.now(timezone.utc).isoformat()
        summary: dict[str, Any] = {
            "schema_version": _SUMMARY_SCHEMA_VERSION,
            "runtime": "headless",
            "mode": mode,
            "broker_mode": broker_mode,
            "broker_status": broker_status,
            "duration_minutes": duration_minutes,
            "started_at": started_at,
            "finished_at": finished_at,
            # Core trade metrics
            "total_trades": sim["total_trades"],
            "pnl_realized": sim["pnl_realized"],
            "max_drawdown": sim["max_drawdown"],
            # Risk metrics
            "risk_events": sim["risk_events"],
            "var_breach_count": sim["var_breach_count"],
            # Additional trade stats
            "wins": sim["wins"],
            "win_rate": sim["win_rate"],
            "mean_pnl_per_trade": sim["mean_pnl_per_trade"],
            "sharpe_annualized": sim["sharpe_annualized"],
            # System metrics
            "evolution_proposals": evolution_proposals,
            "session_guard_blocks": session_guard_blocks,
            "observability_alerts": observability_alerts,
        }

        summary_path = _resolve_summary_path(cfg)
        self._persist(summary, summary_path=summary_path)
        return summary

    # ------------------------------------------------------------------
    # Private helpers
    # ------------------------------------------------------------------

    def _persist(self, summary: dict[str, Any], *, summary_path: Path) -> None:
        """Write summary JSON to stdout and to state/last_run_summary.json."""
        summary_path.parent.mkdir(parents=True, exist_ok=True)
        payload = json.dumps(summary, indent=2)
        summary_path.write_text(payload, encoding="utf-8")
        # Always print to stdout so callers can capture it
        print(payload, flush=True)
        self._logger.info(
            "HeadlessRuntime summary written → %s  (trades=%d  pnl=%.2f)",
            summary_path,
            summary.get("total_trades", 0),
            summary.get("pnl_realized", 0.0),
        )

"""Core websocket telemetry readers (M5)."""
from __future__ import annotations

import json
import logging
import os
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

logger = logging.getLogger(__name__)

def _om():
    from lumina_os.backend import core_websocket as cw
    return cw

try:
    from api.monitoring import _safe_read_json, resolve_state_directory
except ImportError:  # pragma: no cover

    def resolve_state_directory() -> Path:
        raw = os.environ.get("LUMINA_STATE_DIR", "").strip()
        if raw:
            return Path(raw)
        return Path(__file__).resolve().parents[2] / "state"

    def _safe_read_json(path: Path) -> dict[str, Any]:
        if not path.is_file():
            return {}
        try:
            parsed = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            return {}
        return parsed if isinstance(parsed, dict) else {}

try:
    from backend.adaptive_intelligence_snapshot import (
        build_adaptive_intelligence_block,
        resolve_adaptive_history_path,
        resolve_adaptive_status_path,
    )
    from backend.live_trading_snapshot import build_live_trading_block
    from backend.monitoring_endpoints import _extract_regime_summary, _metric_value
    from backend.performance_snapshot import build_performance_block
    from backend.real_ops_snapshot import build_real_ops_block
    from backend.risk_fortress_snapshot import build_fortress_block
except ImportError:  # pragma: no cover
    from lumina_os.backend.adaptive_intelligence_snapshot import (
        build_adaptive_intelligence_block,
        resolve_adaptive_history_path,
        resolve_adaptive_status_path,
    )
    from lumina_os.backend.live_trading_snapshot import build_live_trading_block
    from lumina_os.backend.monitoring_endpoints import _extract_regime_summary, _metric_value
    from lumina_os.backend.performance_snapshot import build_performance_block
    from lumina_os.backend.real_ops_snapshot import build_real_ops_block
    from lumina_os.backend.risk_fortress_snapshot import build_fortress_block

def _utc_now_iso() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="milliseconds").replace("+00:00", "Z")

class _CachedFileReader:
    """Read JSON / JSONL files only when mtime changes."""

    def __init__(self) -> None:
        self._cache: dict[str, tuple[int, Any]] = {}

    def read_json(self, path: Path) -> dict[str, Any]:
        cached = self._get_cached(path)
        if cached is not None:
            return cached if isinstance(cached, dict) else {}
        data = _safe_read_json(path)
        self._store(path, data)
        return data

    def read_active_mutations(self, path: Path) -> list[dict[str, Any]]:
        cached = self._get_cached(path)
        if cached is not None:
            return cached if isinstance(cached, list) else []

        mutations: list[dict[str, Any]] = []
        if path.is_file():
            try:
                with path.open("r", encoding="utf-8") as fh:
                    for raw in fh:
                        line = raw.strip()
                        if not line:
                            continue
                        try:
                            entry = json.loads(line)
                        except json.JSONDecodeError:
                            continue
                        if not isinstance(entry, dict) or entry.get("status") != "proposed":
                            continue
                        challengers = entry.get("challengers")
                        challenger_count = len(challengers) if isinstance(challengers, list) else 0
                        mutations.append(
                            {
                                "hash": str(entry.get("hash", "")),
                                "timestamp": entry.get("timestamp"),
                                "challenger_count": challenger_count,
                            }
                        )
            except OSError:
                logger.debug("Unable to read evolution log at %s", path)

        self._store(path, mutations)
        return mutations

    def _get_cached(self, path: Path) -> Any | None:
        key = str(path)
        if not path.is_file():
            self._cache.pop(key, None)
            return None
        try:
            mtime_ns = path.stat().st_mtime_ns
        except OSError:
            return None
        hit = self._cache.get(key)
        if hit is not None and hit[0] == mtime_ns:
            return hit[1]
        return None

    def _store(self, path: Path, data: Any) -> None:
        try:
            mtime_ns = path.stat().st_mtime_ns
        except OSError:
            return
        self._cache[str(path)] = (mtime_ns, data)

class CoreLiveTelemetryReader:
    """Build aggregated telemetry snapshots from state files and observability."""

    def __init__(self, state_dir: Path | None = None) -> None:
        self._state_dir = state_dir or resolve_state_directory()
        self._files = _CachedFileReader()

    @property
    def state_dir(self) -> Path:
        return self._state_dir

    def build_snapshot(self, obs: Any | None = None) -> dict[str, Any]:
        runtime = self._files.read_json(self._state_dir / "monitoring_runtime_metrics.json")
        sim_state = self._files.read_json(self._state_dir / "lumina_sim_state.json")
        adaptive_path = resolve_adaptive_status_path(self._state_dir)
        adaptive = self._files.read_json(adaptive_path)
        history_path = resolve_adaptive_history_path(self._state_dir)
        mutations = self._files.read_active_mutations(
            Path(os.getenv("EVOLUTION_LOG_PATH", str(self._state_dir / "evolution_log.jsonl")))
        )

        obs_snapshot: dict[str, Any] = {}
        if obs is not None:
            try:
                raw = obs.snapshot()
                obs_snapshot = raw if isinstance(raw, dict) else {}
            except Exception:
                logger.debug("Observability snapshot unavailable", exc_info=True)

        regime_summary = _extract_regime_summary(obs_snapshot) if obs_snapshot else {}
        regime = str(regime_summary.get("current_regime") or "UNKNOWN")
        if regime == "UNKNOWN":
            agent = (sim_state.get("state_snapshot") or {}).get("agent") or {}
            if isinstance(agent, dict) and agent.get("regime"):
                regime = str(agent["regime"])

        mode = str(runtime.get("mode") or "").strip()
        if not mode:
            payload = adaptive.get("payload") if isinstance(adaptive.get("payload"), dict) else {}
            mode = str(payload.get("mode") or "unknown")

        if _om()._operator_mode_override:
            mode = _om()._operator_mode_override

        equity = _coerce_float(runtime.get("account_equity"))
        if equity is None:
            risk = (sim_state.get("state_snapshot") or {}).get("risk") or {}
            if isinstance(risk, dict):
                equity = _coerce_float(risk.get("account_equity"))

        consecutive_losses = _coerce_int(runtime.get("consecutive_losses"), default=0)
        has_data = bool(runtime) or bool(sim_state) or bool(adaptive)
        risk_level = _resolve_risk_level(
            obs_snapshot=obs_snapshot,
            regime_summary=regime_summary,
            consecutive_losses=consecutive_losses,
            has_data=has_data,
        )

        source_ts = runtime.get("timestamp")
        if not source_ts and isinstance(adaptive.get("timestamp"), str):
            source_ts = adaptive["timestamp"]

        adaptive_block = build_adaptive_intelligence_block(
            latest_record=adaptive if adaptive else None,
            history_path=history_path,
        )

        live_trading_block = build_live_trading_block(
            runtime=runtime,
            sim_state=sim_state,
            regime_summary=regime_summary,
            state_dir=self._state_dir,
        )

        fortress_block = build_fortress_block(
            runtime=runtime,
            sim_state=sim_state,
            obs_snapshot=obs_snapshot,
            kill_switch_metric_fn=_metric_value,
        )

        performance_block = build_performance_block(
            runtime=runtime,
            state_dir=self._state_dir,
        )

        real_ops_block = build_real_ops_block(
            runtime=runtime,
            state_dir=self._state_dir,
        )

        ninjatrader_block = _build_ninjatrader_telemetry_block()

        return {
            "mode": mode.lower() if mode else "unknown",
            "equity": equity,
            "regime": regime,
            "risk_level": risk_level,
            "active_mutations": mutations,
            "source_ts": source_ts,
            "adaptive_intelligence": adaptive_block,
            "live_trading": live_trading_block,
            "fortress": fortress_block,
            "performance": performance_block,
            "real_ops": real_ops_block,
            "ninjatrader": ninjatrader_block,
        }

def _build_ninjatrader_telemetry_block() -> dict[str, Any]:
    try:
        from lumina_core.broker.ninjatrader.bridge_service import get_ninjatrader_bridge_service

        state = get_ninjatrader_bridge_service().get_connection_state()
        return state.to_telemetry_dict()
    except Exception:
        return {
            "connected": False,
            "account": "",
            "last_bar_ts": None,
            "state": "disconnected",
            "safe_mode": "UNKNOWN",
            "fabric_target": "",
            "gateway": "",
            "session_id": "",
            "last_state_hash": "",
            "recent_alerts": 0,
            "metrics": {},
        }

def _coerce_float(value: Any) -> float | None:
    if value is None:
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        return None

def _coerce_int(value: Any, *, default: int = 0) -> int:
    try:
        return int(value)
    except (TypeError, ValueError):
        return default

def _resolve_risk_level(
    *,
    obs_snapshot: dict[str, Any],
    regime_summary: dict[str, Any],
    consecutive_losses: int,
    has_data: bool = False,
) -> str:
    if obs_snapshot:
        kill_switch = _metric_value(obs_snapshot, "lumina_risk_kill_switch_active", 0.0)
        if kill_switch >= 1.0:
            return "CRITICAL"

    risk_state = str(regime_summary.get("regime_risk_state") or "").strip().upper()
    if risk_state and risk_state != "UNKNOWN":
        return risk_state

    if consecutive_losses >= 3:
        return "ELEVATED"
    if has_data or consecutive_losses > 0 or obs_snapshot or regime_summary:
        return "NORMAL"
    return "UNKNOWN"

def _build_frame(*, seq: int, payload: dict[str, Any]) -> dict[str, Any]:
    return {
        "type": "telemetry",
        "seq": seq,
        "ts": _utc_now_iso(),
        "payload": payload,
    }

import logging
import os
import threading
import time
import json
from contextlib import contextmanager
from contextvars import ContextVar
from logging.handlers import RotatingFileHandler
from pathlib import Path
from typing import Any


EVENT_CODES: dict[str, str] = {
    "analysis.new_candle": "ANL-1001",
    "analysis.fast_path": "ANL-1002",
    "analysis.cache_hit": "ANL-1003",
    "analysis.llm_takeover": "ANL-1004",
    "ops.speak": "OPS-2001",
    "ops.account_balance": "OPS-2002",
    "ops.order_success": "OPS-2003",
    "ops.emergency_stop": "OPS-2004",
}


def runtime_trace_enabled() -> bool:
    """Verbose runtime tracing for test / verification (supervisor + analysis paths).

    Set ``LUMINA_RUNTIME_TRACE=1`` (or ``true`` / ``yes`` / ``on``). Logs lines prefixed with
    ``RUNTIME_TRACE`` so they are easy to grep in ``logs/lumina_full_log.csv``.
    """
    return os.getenv("LUMINA_RUNTIME_TRACE", "").strip().lower() in {"1", "true", "yes", "on"}


_TRACE_EMIT_LOCK = threading.Lock()
_TRACE_LAST_EMIT_MONO: dict[str, float] = {}
# Only throttle stages that fire every supervisor tick; other traces stay unthrottled.
_RUNTIME_TRACE_THROTTLE_STAGES = frozenset({"supervisor.policy_gateway"})
_CORRELATION_ID: ContextVar[str] = ContextVar("lumina_correlation_id", default="")
_MONITORING_IO_LOCK = threading.Lock()


def runtime_trace_interval_sec() -> float:
    """Minimum seconds between *noisy* trace lines when trace is enabled.

    ``LUMINA_RUNTIME_TRACE_INTERVAL_SEC`` — ``0`` or unset means no limit (log every line).
    Applies only to stages in ``_RUNTIME_TRACE_THROTTLE_STAGES`` (high-frequency supervisor).
    """
    raw = os.getenv("LUMINA_RUNTIME_TRACE_INTERVAL_SEC", "0").strip()
    try:
        return max(0.0, float(raw))
    except ValueError:
        return 0.0


def _fmt_trace_val(value: object) -> str:
    text = str(value).replace(",", ";")
    if len(text) > 240:
        return text[:237] + "..."
    return text


def log_runtime_trace(logger: logging.Logger, stage: str, **fields: object) -> None:
    """Emit one CSV-safe INFO line when :func:`runtime_trace_enabled` is true.

    Time contract: supervisor gates (hold, session) compare **Unix epoch seconds** (UTC
    instant). ``hold_until_ts`` and ``now_epoch_s`` (when present) are directly comparable.
    The host log ``asctime`` is local wall clock — use ``now_utc_iso`` for unambiguous correlation.
    """
    if not runtime_trace_enabled():
        return
    interval = runtime_trace_interval_sec()
    if interval > 0 and stage in _RUNTIME_TRACE_THROTTLE_STAGES:
        with _TRACE_EMIT_LOCK:
            now = time.monotonic()
            last = _TRACE_LAST_EMIT_MONO.get(stage, 0.0)
            if now - last < interval:
                return
            _TRACE_LAST_EMIT_MONO[stage] = now
    parts = ["RUNTIME_TRACE", f"stage={stage}"]
    for key in sorted(fields.keys()):
        parts.append(f"{key}={_fmt_trace_val(fields[key])}")
    logger.info(",".join(parts))


def log_event(logger: logging.Logger, event_name: str, level: int = logging.INFO, **fields: object) -> None:
    """Emit stable structured event logs with a canonical event code."""
    code = EVENT_CODES.get(event_name, "GEN-0000")
    payload_parts = [f"event={event_name}", f"code={code}"]
    for key, value in sorted(fields.items()):
        payload_parts.append(f"{key}={value}")
    message = ",".join(payload_parts)
    if hasattr(logger, "log"):
        logger.log(level, message)
        return

    if level >= logging.ERROR and hasattr(logger, "error"):
        logger.error(message)
        return
    if level >= logging.WARNING and hasattr(logger, "warning"):
        logger.warning(message)
        return
    if hasattr(logger, "info"):
        logger.info(message)


def get_logger(name: str) -> logging.Logger:
    """Return a hierarchical logger for Lumina components."""
    try:
        logger_name = str(name or "lumina").strip() or "lumina"
        return logging.getLogger(logger_name)
    except Exception:
        return logging.getLogger("lumina")


@contextmanager
def correlation_id(value: str):
    """Temporarily bind correlation context for structured events."""
    token = _CORRELATION_ID.set(str(value or ""))
    try:
        yield
    finally:
        _CORRELATION_ID.reset(token)


def _safe_log(logger: logging.Logger, level: int, event_name: str, **fields: Any) -> None:
    try:
        payload: dict[str, Any] = {"event": str(event_name)}
        cid = _CORRELATION_ID.get("")
        if cid:
            payload.setdefault("correlation_id", cid)
        payload.update(fields)
        logger.log(level, str(event_name), extra={"event_data": payload})
    except Exception:
        return


def log_evolution_event(logger: logging.Logger, event_type: str, dna_hash: str | None = None, **kwargs: Any) -> None:
    _safe_log(logger, logging.INFO, "evolution.event", event_type=event_type, dna_hash=dna_hash, **kwargs)


def log_twin_decision(
    logger: logging.Logger,
    dna_hash: str,
    score: float,
    recommendation: bool,
    risk_flags: list[str],
    explanation: str,
    **kwargs: Any,
) -> None:
    _safe_log(
        logger,
        logging.INFO,
        "twin.decision",
        dna_hash=dna_hash,
        score=float(score),
        recommendation=bool(recommendation),
        risk_flags=list(risk_flags),
        explanation=str(explanation),
        **kwargs,
    )


def log_shadow_verdict(logger: logging.Logger, dna_hash: str, verdict_dict: dict[str, Any], **kwargs: Any) -> None:
    _safe_log(logger, logging.INFO, "shadow.verdict", dna_hash=dna_hash, verdict=dict(verdict_dict), **kwargs)


def log_gate_rejection(
    logger: logging.Logger, gate_name: str, reason: str, current_value: Any, limit: Any, **kwargs: Any
) -> None:
    _safe_log(
        logger,
        logging.WARNING,
        "gate.rejection",
        gate_name=str(gate_name),
        reason=str(reason),
        current_value=current_value,
        limit=limit,
        **kwargs,
    )


def log_decision_flow(logger: logging.Logger, decision_context_id: str, step: str, **kwargs: Any) -> None:
    _safe_log(
        logger,
        logging.INFO,
        "decision.flow",
        decision_context_id=str(decision_context_id),
        step=str(step),
        **kwargs,
    )


def flush_logger_handlers(logger: logging.Logger | None) -> None:
    """Push log lines to attached file/stream handlers (helps diagnose startup stalls)."""
    if logger is None:
        return
    for h in getattr(logger, "handlers", []):
        try:
            h.flush()
        except Exception:
            logging.exception("flush_logger_handlers failed to flush a logger handler")


def build_logger(name: str, log_level: str = "INFO", file_path: str = "logs/lumina_full_log.csv") -> logging.Logger:
    """Create a non-propagating rotating logger used by runtime daemons."""
    logger = logging.getLogger(name)
    logger.setLevel(getattr(logging, log_level.upper(), logging.INFO))
    logger.handlers.clear()
    logger.propagate = False

    formatter = logging.Formatter("%(asctime)s,%(levelname)s,%(message)s")

    log_path = Path(file_path)
    log_path.parent.mkdir(parents=True, exist_ok=True)

    file_handler = RotatingFileHandler(log_path, maxBytes=5_000_000, backupCount=5, encoding="utf-8")
    file_handler.setLevel(getattr(logging, log_level.upper(), logging.INFO))
    file_handler.setFormatter(formatter)
    logger.addHandler(file_handler)

    console_handler = logging.StreamHandler()
    console_handler.setLevel(logging.WARNING)
    console_handler.setFormatter(formatter)
    logger.addHandler(console_handler)

    return logger


def setup_logging(
    *,
    log_level: str = "INFO",
    file_path: str = "logs/lumina_full_log.csv",
    logger_name: str = "lumina",
) -> logging.Logger:
    """Configure root + named canonical Lumina logger."""
    logger = build_logger(name=logger_name, log_level=log_level, file_path=file_path)
    root = logging.getLogger()
    root.setLevel(getattr(logging, log_level.upper(), logging.INFO))
    root.handlers.clear()
    for handler in logger.handlers:
        root.addHandler(handler)
    return logger


def resolve_monitoring_state_dir() -> Path:
    """Workspace ``state/`` directory (never rely on process cwd alone)."""
    override = os.getenv("LUMINA_WORKSPACE_ROOT", "").strip()
    if override:
        return (Path(override).expanduser().resolve() / "state")
    config_path = os.getenv("LUMINA_CONFIG", "").strip()
    if config_path:
        return Path(config_path).expanduser().resolve().parent / "state"
    cwd = Path.cwd()
    for candidate in (cwd, Path(__file__).resolve().parents[1]):
        if (candidate / "state").is_dir() and (candidate / "lumina_core").exists():
            return (candidate / "state").resolve()
    return (cwd / "state").resolve()


def _monitoring_state_path(name: str) -> Path:
    return resolve_monitoring_state_dir() / name


def _append_jsonl(path: Path, payload: dict[str, Any]) -> None:
    line = json.dumps(payload, ensure_ascii=True, sort_keys=True)
    path.parent.mkdir(parents=True, exist_ok=True)
    with _MONITORING_IO_LOCK:
        with path.open("a", encoding="utf-8") as fh:
            fh.write(line + "\n")


def _write_json(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with _MONITORING_IO_LOCK:
        path.write_text(json.dumps(payload, ensure_ascii=True, indent=2, sort_keys=True), encoding="utf-8")


def record_twin_decision_monitoring(
    *,
    dna_hash: str,
    score: float,
    recommendation: bool,
    risk_flags: list[str],
    explanation: str,
    source: str = "approval_twin",
) -> None:
    payload = {
        "timestamp": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        "source": str(source),
        "dna_hash": str(dna_hash),
        "score": float(score),
        "recommendation": bool(recommendation),
        "risk_flags": list(risk_flags),
        "explanation": str(explanation),
    }
    _append_jsonl(_monitoring_state_path("monitoring_twin_decisions.jsonl"), payload)


def record_twin_training_metrics_monitoring(*, avg_prediction_error: float, reward: float, training_steps: int) -> None:
    payload = {
        "timestamp": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        "avg_prediction_error": float(avg_prediction_error),
        "reward": float(reward),
        "training_steps": int(training_steps),
    }
    _append_jsonl(_monitoring_state_path("monitoring_twin_training.jsonl"), payload)


def record_gate_rejection_monitoring(
    *,
    gate_name: str,
    reason: str,
    mode: str = "",
    symbol: str = "",
    side: str = "",
    decision_context_id: str = "",
) -> None:
    payload = {
        "timestamp": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        "gate_name": str(gate_name),
        "reason": str(reason),
        "mode": str(mode),
        "symbol": str(symbol),
        "side": str(side),
        "decision_context_id": str(decision_context_id),
    }
    _append_jsonl(_monitoring_state_path("monitoring_gate_rejections.jsonl"), payload)


def record_model_load_time_monitoring(
    *,
    model_type: str,
    model_path: str,
    load_time_sec: float,
    status: str,
) -> None:
    payload = {
        "timestamp": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        "model_type": str(model_type),
        "model_path": str(model_path),
        "load_time_sec": float(load_time_sec),
        "status": str(status),
    }
    _append_jsonl(_monitoring_state_path("monitoring_model_load_times.jsonl"), payload)


def write_ppo_policy_metadata(
    *,
    policy_path: str,
    policy_version: str,
    total_training_steps: int,
    training_time_sec: float = 0.0,
    last_load_time_sec: float = 0.0,
    status: str = "ok",
) -> None:
    payload = {
        "updated_at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        "policy_path": str(policy_path),
        "policy_version": str(policy_version),
        "total_training_steps": int(total_training_steps),
        "training_time_sec": float(training_time_sec),
        "last_load_time_sec": float(last_load_time_sec),
        "status": str(status),
    }
    _write_json(_monitoring_state_path("ppo_policy_metadata.json"), payload)


def write_runtime_monitoring_snapshot(payload: dict[str, Any]) -> None:
    base = {"timestamp": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())}
    base.update(payload if isinstance(payload, dict) else {})
    _write_json(_monitoring_state_path("monitoring_runtime_metrics.json"), base)
    if "daily_pnl" in base:
        try:
            _append_jsonl(
                _monitoring_state_path("monitoring_daily_pnl.jsonl"),
                {"timestamp": str(base["timestamp"]), "daily_pnl": float(base["daily_pnl"])},
            )
        except (TypeError, ValueError):
            pass


def record_reasoning_latency_monitoring(
    *,
    source: str,
    elapsed_ms: float,
    sla_ms: float,
    breach_streak: int,
    fast_path_only: bool,
    daily_pnl: float | None = None,
) -> None:
    payload: dict[str, Any] = {
        "timestamp": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        "source": str(source),
        "elapsed_ms": float(elapsed_ms),
        "sla_ms": float(sla_ms),
        "breach_streak": int(breach_streak),
        "fast_path_only": bool(fast_path_only),
    }
    if daily_pnl is not None:
        payload["daily_pnl"] = float(daily_pnl)
    _append_jsonl(_monitoring_state_path("monitoring_reasoning_latency.jsonl"), payload)

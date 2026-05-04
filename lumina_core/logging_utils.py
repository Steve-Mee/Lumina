import logging
import os
import threading
import time
from logging.handlers import RotatingFileHandler
from pathlib import Path


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

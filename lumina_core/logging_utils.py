import logging
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

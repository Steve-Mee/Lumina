"""Launcher telemetry: structured events and optional JSONL hooks."""

from lumina_launcher.telemetry.events import log_event, timed_call, timed_event
from lumina_launcher.telemetry.hooks import allocate_run_id, emit_launcher_event

__all__ = [
    "allocate_run_id",
    "emit_launcher_event",
    "log_event",
    "timed_call",
    "timed_event",
]

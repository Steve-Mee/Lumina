"""Backward-compat re-exports. Prefer :mod:`lumina_launcher.telemetry`."""

from lumina_launcher.telemetry.events import log_event, timed_call, timed_event

__all__ = ["log_event", "timed_call", "timed_event"]

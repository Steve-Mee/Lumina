"""Minimal preflight report adapter for headless production bootstrap failures."""
from __future__ import annotations


class RuntimePreflightReportAdapter:
    """Minimal adapter for bootstrap exceptions."""

    @staticmethod
    def from_exception(exc: Exception):
        from lumina_core.runtime.runtime_preflight import RuntimePreflightReport

        return RuntimePreflightReport(
            ok=False,
            mode="unknown",
            checks={"bootstrap": "fail"},
            failure_reasons=(f"bootstrap:{type(exc).__name__}:{exc}",),
            message="Bootstrap failed",
        )

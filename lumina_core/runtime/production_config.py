"""Shared config helpers for headless smoke and production runtime."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from lumina_core.config_loader import ConfigLoader


def load_headless_section() -> dict[str, Any]:
    section = ConfigLoader.section("headless", default={}) or {}
    return section if isinstance(section, dict) else {}


def load_production_section(headless_cfg: dict[str, Any] | None = None) -> dict[str, Any]:
    cfg = headless_cfg if headless_cfg is not None else load_headless_section()
    prod = cfg.get("production")
    return prod if isinstance(prod, dict) else {}


def resolve_status_path() -> Path:
    return Path("state/headless_runtime_status.json")


def resolve_heartbeat_path() -> Path:
    return Path("state/lumina_heartbeat")


def resolve_preflight_report_path() -> Path:
    return Path("state/runtime_preflight_report.json")


def resolve_slo_live_path() -> Path:
    return Path("state/runtime_slo_live.json")


def resolve_reconciliation_report_path() -> Path:
    return Path("state/runtime_reconciliation_report.json")

"""Fabric connection diagnostics — preflight checks (Wave B2 PR-C1).

Token / fabric.json / config / TCP. Shared types + finalize live here.
"""

from __future__ import annotations

import json
import os
import socket
import time
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any, Literal

CheckStatus = Literal["pass", "fail", "warn", "skip"]
OverallStatus = Literal["green", "amber", "red"]

CRITICAL_CHECK_IDS = frozenset(
    {
        "token_present",
        "port_listen",
        "auth_ok",
        "place_order",
        "flatten",
        "safe_mode_enter",
    }
)


@dataclass
class DiagnosticCheck:
    id: str
    title: str
    status: CheckStatus
    message: str
    detail: str | None = None
    duration_ms: int = 0


@dataclass
class FabricConnectionReport:
    overall: OverallStatus
    started_at: str
    duration_ms: int
    target: str
    gateway_mode: str
    checks: list[DiagnosticCheck] = field(default_factory=list)
    summary: str = ""
    remediation: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return {
            "overall": self.overall,
            "started_at": self.started_at,
            "duration_ms": self.duration_ms,
            "target": self.target,
            "gateway_mode": self.gateway_mode,
            "checks": [asdict(c) for c in self.checks],
            "summary": self.summary,
            "remediation": self.remediation,
        }


def _fabric_json_path() -> Path:
    if os.name == "nt":
        base = os.environ.get("APPDATA") or str(Path.home() / "AppData" / "Roaming")
        return Path(base) / "LUMINA" / "fabric.json"
    xdg = os.environ.get("XDG_CONFIG_HOME")
    if xdg:
        return Path(xdg) / "LUMINA" / "fabric.json"
    return Path.home() / ".config" / "LUMINA" / "fabric.json"


def _audit_path() -> Path:
    if os.name == "nt":
        base = os.environ.get("APPDATA") or str(Path.home() / "AppData" / "Roaming")
        return Path(base) / "LUMINA" / "fabric-audit.jsonl"
    xdg = os.environ.get("XDG_CONFIG_HOME")
    if xdg:
        return Path(xdg) / "LUMINA" / "fabric-audit.jsonl"
    return Path.home() / ".config" / "LUMINA" / "fabric-audit.jsonl"


def _resolve_token() -> str:
    return str(
        os.getenv("LUMINA_FABRIC_TOKEN") or os.getenv("LUMINA_NT8_API_KEY") or ""
    ).strip()


def _load_fabric_json() -> dict[str, Any]:
    path = _fabric_json_path()
    if not path.is_file():
        return {}
    try:
        # PowerShell Set-Content often writes UTF-8 BOM — accept utf-8-sig.
        data = json.loads(path.read_text(encoding="utf-8-sig"))
        return data if isinstance(data, dict) else {}
    except (OSError, json.JSONDecodeError):
        return {}


def _load_broker_config() -> dict[str, Any]:
    """Load broker section from LUMINA_CONFIG / config.yaml (cwd-independent)."""
    try:
        import yaml
    except ImportError:
        return {}
    candidates = [
        Path(os.getenv("LUMINA_CONFIG", "") or ""),
        Path.cwd() / "config.yaml",
        Path.cwd().parent / "config.yaml",
    ]
    for path in candidates:
        if not path or not str(path).strip() or not path.is_file():
            continue
        try:
            raw = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
            if isinstance(raw, dict):
                broker = raw.get("broker")
                return broker if isinstance(broker, dict) else {}
        except Exception:
            continue
    return {}


def _tcp_check(host: str, port: int, timeout: float = 2.0) -> tuple[bool, str]:
    try:
        with socket.create_connection((host, port), timeout=timeout):
            return True, "TCP connect ok"
    except OSError as exc:
        return False, f"{type(exc).__name__}: {exc}"


def _is_localhost(host: str) -> bool:
    h = host.strip().lower()
    return h in {"127.0.0.1", "localhost", "::1"}


from lumina_launcher.services.fabric_diag_preflight_run import (  # noqa: E402,F401
    PreflightContext,
    finalize_report,
    run_preflight,
)

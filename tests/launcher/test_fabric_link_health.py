"""Fabric Link Health SSOT — live level never equals paper cert alone."""

from __future__ import annotations

import json
import time
from pathlib import Path

from lumina_launcher.services.fabric_link_certificate import write_certificate
from lumina_launcher.services.fabric_link_health import (
    RESTARTING_GRACE_SEC,
    build_fabric_link_health,
    compute_level,
)


def test_compute_level_matrix() -> None:
    assert compute_level(
        host_state="stopped",
        port_listening=False,
        active_sessions=0,
        safe_mode="NORMAL",
        auth_ok=False,
        host_code="clean",
        updated_age_sec=60.0,
    )[0] == "RED"

    assert compute_level(
        host_state="stopped",
        port_listening=False,
        active_sessions=0,
        safe_mode="NORMAL",
        auth_ok=False,
        host_code="clean",
        updated_age_sec=1.0,
    )[0] == "RESTARTING"

    assert compute_level(
        host_state="running",
        port_listening=True,
        active_sessions=0,
        safe_mode="NORMAL",
        auth_ok=False,
    )[0] == "AMBER"

    assert compute_level(
        host_state="running",
        port_listening=True,
        active_sessions=1,
        safe_mode="NORMAL",
        auth_ok=True,
    )[0] == "GREEN"

    assert compute_level(
        host_state="running",
        port_listening=True,
        active_sessions=0,
        safe_mode="SAFE",
        auth_ok=False,
    )[0] == "AMBER"

    assert compute_level(
        host_state="running",
        port_listening=False,
        active_sessions=1,
        safe_mode="NORMAL",
        auth_ok=True,
    )[0] == "RED"


def test_paper_cert_alone_not_live_green(tmp_path: Path) -> None:
    write_certificate(
        overall="green",
        target="127.0.0.1:50051",
        token="tok",
        workspace_root=tmp_path,
    )
    health = build_fabric_link_health(
        workspace_root=tmp_path,
        live={},
        host_snap={"state": "stopped", "code": "clean", "active_sessions": 0},
        port_listening=False,
        invalidate_on_host_down=False,
    )
    assert health["green"] is False
    assert health["level"] == "RED"
    assert health["gate_birth_ok"] is False
    assert health["host_ready"] is False


def test_host_up_with_cert_gate_birth_ok(tmp_path: Path) -> None:
    write_certificate(
        overall="green",
        target="127.0.0.1:50051",
        token="tok",
        workspace_root=tmp_path,
    )
    health = build_fabric_link_health(
        workspace_root=tmp_path,
        live={"auth_ok": False, "running": False},
        host_snap={
            "state": "running",
            "code": "ok",
            "host": "nt_addon",
            "bind_host": "127.0.0.1",
            "port": 50051,
            "safe_mode": "SAFE",
            "active_sessions": 0,
            "historical": "nt",
        },
        port_listening=True,
        invalidate_on_host_down=False,
    )
    assert health["level"] == "AMBER"
    assert health["green"] is False
    assert health["host_ready"] is True
    assert health["gate_birth_ok"] is True
    assert health["proof"]["certified"] is True


def test_supervisor_auth_makes_live_green(tmp_path: Path) -> None:
    health = build_fabric_link_health(
        workspace_root=tmp_path,
        live={
            "auth_ok": True,
            "connected": True,
            "session_id": "abc",
            "running": True,
        },
        host_snap={
            "state": "running",
            "code": "ok",
            "bind_host": "127.0.0.1",
            "port": 50051,
            "safe_mode": "NORMAL",
            "active_sessions": 1,
            "historical": "nt",
        },
        port_listening=True,
        invalidate_on_host_down=False,
    )
    assert health["level"] == "GREEN"
    assert health["green"] is True


def test_restarting_grace_not_hard_red() -> None:
    level, meaning = compute_level(
        host_state="stopped",
        port_listening=False,
        active_sessions=0,
        safe_mode="NORMAL",
        auth_ok=False,
        host_code="clean",
        updated_age_sec=RESTARTING_GRACE_SEC - 0.5,
    )
    assert level == "RESTARTING"
    assert "restart" in meaning.lower()


def test_stale_cert_blocks_birth_gate(tmp_path: Path) -> None:
    write_certificate(
        overall="green",
        target="127.0.0.1:50051",
        token="tok",
        workspace_root=tmp_path,
    )
    cert_path = tmp_path / "state" / "fabric_link_certificate.json"
    payload = json.loads(cert_path.read_text(encoding="utf-8"))
    payload["ts_unix"] = time.time() - 3 * 3600  # older than 2h birth window
    cert_path.write_text(json.dumps(payload), encoding="utf-8")

    health = build_fabric_link_health(
        workspace_root=tmp_path,
        live={"auth_ok": True, "session_id": "x", "connected": True},
        host_snap={
            "state": "running",
            "safe_mode": "NORMAL",
            "active_sessions": 1,
            "port": 50051,
            "bind_host": "127.0.0.1",
        },
        port_listening=True,
        invalidate_on_host_down=False,
    )
    assert health["green"] is True  # live still green
    assert health["gate_birth_ok"] is False
    assert health["gate_reason"] in {"FABRIC_LINK_STALE", "FABRIC_LINK_NOT_GREEN"}


def test_auth_failed_overrides_safe_heartbeat_meaning(tmp_path: Path) -> None:
    """Cold-start false not-GREEN: Brain AUTH_FAILED must not look like 'waiting for heartbeats'."""
    health = build_fabric_link_health(
        workspace_root=tmp_path,
        live={
            "auth_ok": False,
            "connected": False,
            "running": True,
            "last_error_code": "AUTH_FAILED",
            "last_error": "Invalid fabric token",
        },
        host_snap={
            "state": "running",
            "safe_mode": "SAFE",
            "active_sessions": 0,
            "port": 50051,
            "bind_host": "127.0.0.1",
        },
        port_listening=True,
        invalidate_on_host_down=False,
    )
    assert health["green"] is False
    assert health["level"] == "AMBER"
    assert health["host_ready"] is True
    assert "token" in str(health["meaning"]).lower()
    assert "heartbeats" not in str(health["meaning"]).lower()


def test_stale_running_status_with_closed_port_is_not_host_ready(tmp_path: Path) -> None:
    """ShutdownAsync hang left status=running while :50051 is dead — fail-closed RED."""
    health = build_fabric_link_health(
        workspace_root=tmp_path,
        live={"auth_ok": True, "connected": True, "session_id": "zombie", "running": True},
        host_snap={
            "state": "running",
            "code": "ok",
            "safe_mode": "NORMAL",
            "active_sessions": 1,
            "port": 50051,
            "bind_host": "127.0.0.1",
            "updated_utc": "2020-01-01T00:00:00+00:00",
        },
        port_listening=False,
        invalidate_on_host_down=False,
    )
    assert health["green"] is False
    assert health["host_ready"] is False
    assert health["level"] == "RED"
    assert health["host"]["state"] == "stopped"
    assert health["host"]["code"] == "stale_running_port_closed"

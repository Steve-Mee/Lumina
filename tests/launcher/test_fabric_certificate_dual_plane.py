"""Dual-plane certificate must not claim GREEN without historical_bars proof."""

from __future__ import annotations

from pathlib import Path

from lumina_launcher.services.fabric_link_certificate import read_certificate, write_certificate


def test_write_certificate_refuses_failed_historical_bars(tmp_path: Path) -> None:
    path = write_certificate(
        overall="green",
        target="127.0.0.1:50051",
        token="tok",
        workspace_root=tmp_path,
        extra={
            "historical_bars": "fail",
            "checks": [
                {"id": "place_order", "status": "pass"},
                {"id": "historical_bars", "status": "fail"},
            ],
        },
    )
    assert path is None
    assert read_certificate(tmp_path) is None


def test_write_certificate_refuses_checks_without_historical(tmp_path: Path) -> None:
    path = write_certificate(
        overall="green",
        target="127.0.0.1:50051",
        token="tok",
        workspace_root=tmp_path,
        extra={
            "checks": [
                {"id": "place_order", "status": "pass"},
                {"id": "flatten", "status": "pass"},
            ],
        },
    )
    assert path is None


def test_write_certificate_accepts_dual_plane_pass(tmp_path: Path) -> None:
    path = write_certificate(
        overall="green",
        target="127.0.0.1:50051",
        token="tok",
        workspace_root=tmp_path,
        extra={
            "historical_bars": "pass",
            "checks": [
                {"id": "place_order", "status": "pass"},
                {"id": "historical_bars", "status": "pass"},
            ],
        },
    )
    assert path is not None
    cert = read_certificate(tmp_path)
    assert cert is not None
    assert cert.get("dual_plane") is True
    assert cert.get("proof") == "fabric_nt_barsrequest"

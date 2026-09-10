"""Startup / diagnostic Fabric checks must never submit NT orders."""

from __future__ import annotations

from pathlib import Path

from lumina_core.broker.broker_bridge.schemas import Order
from lumina_core.broker.ninjatrader.fabric_client_ops import (
    is_forbidden_diagnostic_client_order_id,
)
from lumina_core.broker.ninjatrader.fabric_client import FabricConfig, FabricGrpcClient

ROOT = Path(__file__).resolve().parents[2]


def test_diag_live_source_never_places_or_flattens() -> None:
    text = (ROOT / "lumina_launcher/services/fabric_diag_live.py").read_text(encoding="utf-8")
    assert "place_order_sync" not in text
    assert "flatten_sync" not in text
    assert "diag-place-" not in text
    assert "diag-reauth-" not in text
    assert "diag-safe-" not in text


def test_heal_and_watch_never_enable_order_probe() -> None:
    heal = (ROOT / "lumina_launcher/services/fabric_heal.py").read_text(encoding="utf-8")
    watch = (ROOT / "lumina_launcher/services/ninjatrader_watch.py").read_text(encoding="utf-8")
    api = (ROOT / "lumina_os/backend/setup_endpoints_fabric.py").read_text(encoding="utf-8")
    assert "allow_live_order_probe=True" not in heal
    assert "allow_live_order_probe=True" not in watch
    assert "allow_live_order_probe=False" in heal
    assert "allow_live_order_probe=False" in watch
    assert "allow_live_order_probe=False" in api


def test_forbidden_diagnostic_order_ids() -> None:
    assert is_forbidden_diagnostic_client_order_id("diag-place-abc")
    assert is_forbidden_diagnostic_client_order_id("diag-reauth-1")
    assert is_forbidden_diagnostic_client_order_id("diag-safe-zz")
    assert is_forbidden_diagnostic_client_order_id("DIAG-PLACE-X")
    assert not is_forbidden_diagnostic_client_order_id("lumina-1")
    assert not is_forbidden_diagnostic_client_order_id("cid-place-1")


def test_place_order_sync_rejects_diag_ids_before_transport() -> None:
    client = FabricGrpcClient(FabricConfig(host="127.0.0.1", port=50051, auth_token="x"))
    out = client.place_order_sync(
        Order(symbol="MES", side="BUY", quantity=1, order_type="MARKET"),
        client_order_id="diag-place-deadbeef",
    )
    assert out["type"] == "error"
    assert out["code"] == "DIAGNOSTIC_PROBE_FORBIDDEN"

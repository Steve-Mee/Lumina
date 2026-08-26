"""ADR-0040 Fabric foundation bundle — fail-closed sidecar."""
from __future__ import annotations

import json
from pathlib import Path

from lumina_core.birth.fabric_foundation_bundle import (
    PRE_DECLARE_KEYS,
    evaluate_fabric_foundation_bundle,
)


def test_missing_bundle_fail_closed(tmp_path: Path) -> None:
    out = evaluate_fabric_foundation_bundle(tmp_path)
    assert out["ok"] is False
    assert out["reason"] == "bundle_missing"
    assert out["missing"] == list(PRE_DECLARE_KEYS)


def test_complete_bundle_ok(tmp_path: Path) -> None:
    path = tmp_path / "state" / "fabric_foundation_bundle.json"
    path.parent.mkdir(parents=True)
    payload = {key: True for key in PRE_DECLARE_KEYS}
    path.write_text(json.dumps(payload), encoding="utf-8")
    out = evaluate_fabric_foundation_bundle(tmp_path)
    assert out["ok"] is True
    assert out["missing"] == []


def test_incomplete_bundle_lists_missing(tmp_path: Path) -> None:
    path = tmp_path / "state" / "fabric_foundation_bundle.json"
    path.parent.mkdir(parents=True)
    path.write_text(json.dumps({"fabric_only_sim101": True}), encoding="utf-8")
    out = evaluate_fabric_foundation_bundle(tmp_path)
    assert out["ok"] is False
    assert "human_promotion_marker" in out["missing"]

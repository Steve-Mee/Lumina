from __future__ import annotations

import json
from pathlib import Path

from scripts.validation.bootstrap_sim_real_guard_rollout_b_workspaces import bootstrap_workspace


def test_bootstrap_workspace_creates_isolated_env_and_manifest(tmp_path: Path) -> None:
    source_root = tmp_path / "source"
    target_root = tmp_path / "candidate"
    (source_root / "lumina_core").mkdir(parents=True, exist_ok=True)
    (source_root / "lumina_core" / "sentinel.py").write_text("VALUE = 1\n", encoding="utf-8")
    (source_root / ".env").write_text("VOICE_ENABLED=true\n", encoding="utf-8")
    (source_root / ".venv").mkdir(parents=True, exist_ok=True)
    (source_root / "state").mkdir(parents=True, exist_ok=True)

    manifest = bootstrap_workspace(
        source_root=source_root,
        target_root=target_root,
        role="candidate",
        trade_mode="sim_real_guard",
        enable_sim_real_guard=True,
        broker="live",
        crosstrade_token="token-123",
        crosstrade_account="sim-456",
        shared_python_exe="C:/NinjaTraderAI_Bot/.venv/Scripts/python.exe",
    )

    assert (target_root / "lumina_core" / "sentinel.py").exists()
    assert not (target_root / ".venv").exists()
    assert not (target_root / "state" / "stale.txt").exists()

    env_payload = (target_root / ".env").read_text(encoding="utf-8")
    assert "TRADE_MODE=sim_real_guard" in env_payload
    assert "ENABLE_SIM_REAL_GUARD=true" in env_payload
    assert "ALLOW_SIM_REAL_GUARD_REAL_PROMOTION=false" in env_payload

    manifest_path = target_root / "state" / "validation" / "sim_real_guard_rollout_b" / "bootstrap_manifest.json"
    saved_manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    assert saved_manifest["role"] == "candidate"
    assert saved_manifest["uses_shared_python"] is True
    assert manifest["trade_mode"] == "sim_real_guard"

"""S1 production sources have no TODO/placeholder and no committed HMAC secret."""

from __future__ import annotations

from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]
S1_PATHS = (
    Path("lumina_core/risk/live_release.py"),
    Path("lumina_core/risk/sim_account_guard.py"),
    Path("lumina_core/order_gatekeeper/admission_s1_steps.py"),
    Path("lumina_core/broker/ninjatrader/guards.py"),
    Path("lumina_core/risk/admission_chain.py"),
    Path("integrations/ninjatrader8/Lumina.Execution.Fabric/Safety/SimAccountWhitelist.cs"),
    Path("integrations/ninjatrader8/Lumina.Execution.Fabric/Safety/LiveReleaseGuard.cs"),
    Path("docs/adr/0061-sim-whitelist-and-live-release.md"),
)
BANNED = ("TODO", "FIXME", "XXX", "NotImplemented", "pass  #", "placeholder")


@pytest.mark.unit
@pytest.mark.safety_gate
def test_s1_sources_have_no_todo_or_pass_placeholders() -> None:
    hits: list[str] = []
    for rel in S1_PATHS:
        text = (ROOT / rel).read_text(encoding="utf-8")
        for index, line in enumerate(text.splitlines(), start=1):
            stripped = line.strip()
            if stripped.startswith("#") or stripped.startswith("//"):
                continue
            for token in BANNED:
                if token in line:
                    hits.append(f"{rel}:{index}:{token}")
    assert hits == [], "placeholder in S1 source:\n" + "\n".join(hits)


@pytest.mark.unit
@pytest.mark.safety_gate
def test_live_release_secret_is_not_assigned_in_repo() -> None:
    needle = "LUMINA_LIVE_RELEASE_SECRET="
    hits: list[str] = []
    for rel in (
        Path("config.yaml"),
        Path(".env.example"),
        Path("lumina_core/engine/engine_config.py"),
        Path("lumina_launcher/services/nt_account_store.py"),
    ):
        text = (ROOT / rel).read_text(encoding="utf-8")
        for index, line in enumerate(text.splitlines(), start=1):
            stripped = line.strip()
            if needle not in stripped:
                continue
            if stripped.startswith("#"):
                continue
            value = stripped.split("=", 1)[1].strip().strip("\"'")
            if value:
                hits.append(f"{rel}:{index}")
    assert hits == [], "committed LIVE_RELEASE secret:\n" + "\n".join(hits)

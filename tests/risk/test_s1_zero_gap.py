"""S1 production sources have no TODO/placeholder and no committed HMAC secret."""

from __future__ import annotations

import re
import subprocess
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]
S1_PATHS = (
    Path("lumina_core/risk/live_release.py"),
    Path("lumina_core/risk/sim_account_guard.py"),
    Path("lumina_core/risk/s1_events.py"),
    Path("lumina_core/order_gatekeeper/admission_s1_steps.py"),
    Path("lumina_core/broker/ninjatrader/guards.py"),
    Path("lumina_core/broker/ninjatrader/promotion_gate.py"),
    Path("lumina_core/broker/ninjatrader/bridge_command_sync.py"),
    Path("lumina_core/risk/admission_chain.py"),
    Path("integrations/ninjatrader8/Lumina.Execution.Fabric/Safety/SimAccountWhitelist.cs"),
    Path("integrations/ninjatrader8/Lumina.Execution.Fabric/Safety/LiveReleaseGuard.cs"),
    Path("integrations/ninjatrader8/LuminaNt8AddOn/NtAccountOrderGateway.cs"),
)
BANNED = ("TODO", "FIXME", "XXX", "NotImplemented", "pass  #", "placeholder")
LATER_RE = re.compile(r"\blater\b", re.IGNORECASE)
SECRET_ASSIGN_RE = re.compile(r"LUMINA_LIVE_RELEASE_SECRET\s*=\s*(\S+)")


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
            if rel.suffix in {".py", ".cs"} and LATER_RE.search(line):
                hits.append(f"{rel}:{index}:later")
    assert hits == [], "placeholder in S1 source:\n" + "\n".join(hits)


@pytest.mark.unit
@pytest.mark.safety_gate
def test_live_release_secret_is_not_assigned_in_repo() -> None:
    listed = subprocess.check_output(["git", "ls-files"], cwd=ROOT, text=True).splitlines()
    hits: list[str] = []
    for rel in listed:
        if rel.startswith("tests/") or rel.startswith("archive/"):
            continue
        path = ROOT / rel
        if not path.is_file() or path.suffix.lower() in {".png", ".jpg", ".webp", ".dll", ".exe"}:
            continue
        try:
            text = path.read_text(encoding="utf-8")
        except UnicodeDecodeError:
            continue
        for index, line in enumerate(text.splitlines(), start=1):
            stripped = line.strip()
            if stripped.startswith("#") or stripped.startswith("//"):
                continue
            match = SECRET_ASSIGN_RE.search(stripped)
            if not match:
                continue
            value = match.group(1).strip().strip("\"'")
            if value:
                hits.append(f"{rel}:{index}")
    assert hits == [], "committed LIVE_RELEASE secret:\n" + "\n".join(hits)

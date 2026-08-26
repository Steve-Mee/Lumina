"""Architecture guard: no raw LUMINA_FABRIC_TOKEN getenv outside Fabric Secret Bus.

Elon law: if engineers can invent a new getenv path, dual-truth returns.
This test fails CI when production code bypasses fabric_secret.read/write.
"""

from __future__ import annotations

import re
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]

# Production trees only (not tests/docs/scripts install).
SCAN_ROOTS = (
    ROOT / "lumina_core",
    ROOT / "lumina_launcher",
    ROOT / "lumina_os",
)

# Files allowed to touch the env name directly (bus + thin wrappers + C# mirror is separate).
ALLOWLIST_PATH_PARTS = (
    # Single pipe
    "broker/ninjatrader/fabric_secret.py",
    "broker\\ninjatrader\\fabric_secret.py",
    # Thin compatibility wrappers that must re-export bus
    "setup_persist_fabric.py",
    "setup_persist_credentials.py",  # may pass token into write()
    "setup_persist_config.py",
    "setup_persist_tauri.py",
    "fabric_bootstrap.py",  # generates then write()
    # Credential UI payload keys (not runtime auth)
    "setup_onboarding_payload.py",
    "setup_endpoints_fabric.py",  # ConfigureCredentials field names / token_ssot payload
    # Install / audit mentions
    "cyber_sentinel.py",
    "config_loader.py",  # live required-env name list (not auth connect)
)

# Patterns that indicate an illegal *read* of the process secret.
ILLEGAL_READ = re.compile(
    r"""os\.getenv\(\s*[\"']LUMINA_FABRIC_TOKEN[\"']"""
    r"""|os\.environ\.get\(\s*[\"']LUMINA_FABRIC_TOKEN[\"']"""
    r"""|os\.environ\[\s*[\"']LUMINA_FABRIC_TOKEN[\"']\s*\]""",
)


def _is_allowlisted(path: Path) -> bool:
    s = str(path).replace("\\", "/")
    for part in ALLOWLIST_PATH_PARTS:
        if part.replace("\\", "/") in s.replace("\\", "/"):
            return True
    return False


@pytest.mark.unit
def test_no_raw_fabric_token_getenv_outside_secret_bus() -> None:
    offenders: list[str] = []
    for root in SCAN_ROOTS:
        if not root.is_dir():
            continue
        for path in root.rglob("*.py"):
            if "__pycache__" in path.parts:
                continue
            if _is_allowlisted(path):
                continue
            try:
                text = path.read_text(encoding="utf-8", errors="ignore")
            except OSError:
                continue
            # Skip comments-only hits roughly by scanning lines.
            for i, line in enumerate(text.splitlines(), 1):
                stripped = line.strip()
                if stripped.startswith("#"):
                    continue
                if ILLEGAL_READ.search(line):
                    offenders.append(f"{path.relative_to(ROOT)}:{i}: {stripped[:120]}")

    assert not offenders, (
        "Illegal raw LUMINA_FABRIC_TOKEN reads (use fabric_secret.read/write):\n"
        + "\n".join(offenders[:40])
    )

"""SIM-only birth prereq helper for genuine D4 multiday campaigns (ADR-0013)."""

from __future__ import annotations

from pathlib import Path

from lumina_core.birth.birth_certificate import validate_certificate_artifacts
from lumina_core.birth.config import load_birth_v2_config


def birth_policy_path(workspace_root: Path | str) -> Path:
    root = Path(workspace_root)
    return root / "lumina_agents" / "ppo" / "lumina_ppo_policy.zip"


def birth_certificate_path(workspace_root: Path | str) -> Path:
    root = Path(workspace_root)
    return root / "state" / "lumina_birth_certificate.json"


def ensure_birth_prereqs(
    *,
    workspace_root: Path | str,
    seed: bool = False,
    label: str = "d4-campaign",
) -> tuple[bool, str]:
    """Ensure birth v2 certificate + policy exist under workspace root.

    Flag seeding removed from product paths (ADR-0013). ``seed=True`` is ignored
    except in explicit test harnesses that patch this module.
    """
    _ = label
    policy = birth_policy_path(workspace_root)
    if not policy.exists():
        return False, f"missing birth policy: {policy}"

    thresholds = load_birth_v2_config(workspace_root).certificate_thresholds
    ok, reason, cert = validate_certificate_artifacts(workspace_root, thresholds=thresholds)
    if ok:
        return True, f"birth certificate valid: {birth_certificate_path(workspace_root)}"

    if seed:
        return False, (
            "birth certificate seeding disabled in product paths; "
            "run Birth Phase v2 to issue lumina_birth_certificate.json"
        )

    return False, f"invalid birth certificate ({reason}); cert_present={cert is not None}"

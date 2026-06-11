"""SIM-only birth prereq helper for genuine D4 multiday campaigns."""

from __future__ import annotations

from pathlib import Path


def birth_policy_path(workspace_root: Path | str) -> Path:
    root = Path(workspace_root)
    return root / "lumina_agents" / "ppo" / "lumina_ppo_policy.zip"


def birth_flag_path(workspace_root: Path | str) -> Path:
    root = Path(workspace_root)
    return root / "state" / "lumina_birth_completed.flag"


def ensure_birth_prereqs(
    *,
    workspace_root: Path | str,
    seed: bool,
    label: str = "d4-campaign",
) -> tuple[bool, str]:
    """Ensure birth policy + flag exist under workspace root (not isolated LUMINA_STATE_DIR).

    Seeding creates ``state/lumina_birth_completed.flag`` for SIM campaign runs only.
    """
    policy = birth_policy_path(workspace_root)
    flag = birth_flag_path(workspace_root)
    if not policy.exists():
        return False, f"missing birth policy: {policy}"
    if flag.exists():
        return True, f"birth flag present: {flag}"
    if not seed:
        return False, f"missing birth flag: {flag} (pass --seed-birth-flag for SIM campaigns)"
    flag.parent.mkdir(parents=True, exist_ok=True)
    flag.write_text(f"seeded:{label}\n", encoding="utf-8")
    return True, f"seeded birth flag: {flag}"

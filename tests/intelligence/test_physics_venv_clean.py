from __future__ import annotations

from pathlib import Path

import pytest

from lumina_core.intelligence.physics_venv import NEVER_INSTALL_WITH_LUNGS, assert_physics_venv_clean

pytestmark = pytest.mark.unit

ROOT = Path(__file__).resolve().parents[2]


def test_physics_requirements_contain_no_vllm() -> None:
    # gegeven
    path = ROOT / "requirements-birth-physics.txt"

    # wanneer
    text = path.read_text(encoding="utf-8")
    install_lines = [
        line.strip()
        for line in text.splitlines()
        if line.strip() and not line.strip().startswith("#")
    ]

    # dan
    joined = "\n".join(install_lines).lower()
    assert "vllm" not in joined
    for banned in NEVER_INSTALL_WITH_LUNGS:
        assert banned not in joined
    assert_physics_venv_clean(ROOT)


def test_installer_source_mentions_vllm_only_in_refuse_or_detect_paths() -> None:
    # gegeven
    paths = [
        ROOT / "scripts" / "install_birth_physics_stack.py",
        ROOT / "lumina_core" / "birth" / "physics_stack_install.py",
    ]

    # wanneer / dan
    for path in paths:
        text = path.read_text(encoding="utf-8")
        lowered = text.lower()
        assert "vllm" in lowered
        assert "pip install vllm" not in lowered
        assert "pip install ray[serve]" not in lowered
        for raw in text.splitlines():
            stripped = raw.strip().lower()
            if stripped.startswith("#"):
                continue
            if "pip" in stripped and "install" in stripped and "vllm" in stripped:
                raise AssertionError(f"{path.name} pip-installs vllm: {raw}")

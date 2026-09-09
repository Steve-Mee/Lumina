"""Physics-venv cleanliness: Lungs never install Voice serving packages."""

from __future__ import annotations

from pathlib import Path

NEVER_INSTALL_WITH_LUNGS: frozenset[str] = frozenset(
    {
        "vllm",
        "ray[serve]",
        "compressed-tensors",
    }
)

_PHYSICS_REQUIREMENT_FILES: tuple[str, ...] = (
    "requirements-birth-physics.txt",
    "requirements-birth-ml.txt",
)

_INSTALLER_RELATIVE: tuple[str, ...] = (
    "scripts/install_birth_physics_stack.py",
    "lumina_core/birth/physics_stack_install.py",
)

_REPO_ROOT = Path(__file__).resolve().parents[2]

_PIP_INSTALL_BANNED: tuple[str, ...] = (
    "pip install vllm",
    "pip install ray[serve]",
    "pip install compressed-tensors",
)


def _requirement_install_tokens(text: str) -> list[str]:
    tokens: list[str] = []
    for raw in text.splitlines():
        line = raw.strip()
        if not line or line.startswith("#") or line.startswith("-"):
            continue
        pkg = line.split("==")[0].split(">=")[0].split("[")[0].strip().lower()
        if pkg:
            tokens.append(pkg)
        lowered = line.lower()
        if "ray[serve]" in lowered:
            tokens.append("ray[serve]")
        if "compressed-tensors" in lowered:
            tokens.append("compressed-tensors")
    return tokens


def assert_physics_venv_clean(env: Path | str | None = None) -> None:
    """Fail if physics requirements or installer declare Voice serving packages.

    ``env`` is a workspace root. ``vllm`` may appear in installer source only
    as refuse/detect wording, never as a pip install target.
    """
    root = Path(env).resolve() if env is not None else _REPO_ROOT
    for name in _PHYSICS_REQUIREMENT_FILES:
        path = root / name
        if not path.is_file():
            continue
        declared = set(_requirement_install_tokens(path.read_text(encoding="utf-8")))
        hits = sorted(pkg for pkg in NEVER_INSTALL_WITH_LUNGS if pkg in declared or pkg.split("[", 1)[0] in declared)
        if "vllm" in declared or "compressed-tensors" in declared:
            hits = sorted(set(hits) | ({"vllm"} if "vllm" in declared else set()) | (
                {"compressed-tensors"} if "compressed-tensors" in declared else set()
            ))
        if hits:
            raise AssertionError(f"physics requirements {name} must not declare Voice packages: {hits}")
    for rel in _INSTALLER_RELATIVE:
        path = root / rel
        if not path.is_file():
            continue
        lowered = path.read_text(encoding="utf-8").lower()
        for needle in _PIP_INSTALL_BANNED:
            if needle in lowered:
                raise AssertionError(f"{rel} must not {needle}")

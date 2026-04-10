from __future__ import annotations

from pathlib import Path
import sys


ROOT = Path(__file__).resolve().parents[2]
README = ROOT / "README.md"

# Keep this list aligned with the "Mappenstructuur" section in README.
REQUIRED_PATHS = [
    "deploy",
    "docs",
    "journal",
    "lumina_core",
    "lumina_bible",
    "lumina_agents",
    "lumina_vector_db",
    "scripts",
    "tests",
]


def check_required_paths() -> list[str]:
    missing: list[str] = []
    for rel in REQUIRED_PATHS:
        if not (ROOT / rel).exists():
            missing.append(rel)
    return missing


def main() -> int:
    if not README.exists():
        print("ERROR: README.md not found")
        return 2

    missing = check_required_paths()
    if missing:
        print("ERROR: README path drift detected. Missing paths:")
        for rel in missing:
            print(f"- {rel}")
        return 1

    print("OK: README path check passed")
    return 0


if __name__ == "__main__":
    sys.exit(main())

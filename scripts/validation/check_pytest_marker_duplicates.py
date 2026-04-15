from __future__ import annotations

from configparser import ConfigParser
from pathlib import Path


def _extract_markers(pytest_ini: Path) -> list[str]:
    parser = ConfigParser()
    parser.read(pytest_ini, encoding="utf-8")
    raw = parser.get("pytest", "markers", fallback="")

    markers: list[str] = []
    for line in raw.splitlines():
        token = line.strip()
        if not token:
            continue
        name = token.split(":", 1)[0].strip()
        if name:
            markers.append(name)
    return markers


def main() -> int:
    pytest_ini = Path("pytest.ini")
    if not pytest_ini.exists():
        print("pytest.ini not found")
        return 2

    markers = _extract_markers(pytest_ini)
    seen: set[str] = set()
    duplicates: list[str] = []
    for marker in markers:
        if marker in seen and marker not in duplicates:
            duplicates.append(marker)
        seen.add(marker)

    if duplicates:
        print("Duplicate pytest markers detected: " + ", ".join(sorted(duplicates)))
        return 1

    print(f"pytest marker lint passed ({len(markers)} markers, no duplicates)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

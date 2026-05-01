#!/usr/bin/env python3
"""Draft release notes from ADR titles and print a short release reminder.

Reads current version from pyproject.toml, prompts for the next version,
writes CHANGELOG_DRAFT.md with the latest five canonical ADRs (000x, excluding template).
"""

from __future__ import annotations

import argparse
import re
import sys
import tomllib
from pathlib import Path


def _repo_root() -> Path:
    return Path(__file__).resolve().parent.parent


def _read_project_version(pyproject: Path) -> str:
    data = tomllib.loads(pyproject.read_text(encoding="utf-8"))
    return str(data["project"]["version"])


def _adr_sort_key(path: Path) -> int:
    m = re.match(r"^(\d+)-", path.name)
    return int(m.group(1)) if m else -1


def _latest_canonical_adrs(adr_dir: Path, *, limit: int = 5) -> list[Path]:
    candidates = []
    for p in adr_dir.glob("*.md"):
        if p.name == "0000-template.md":
            continue
        if re.match(r"^\d{4}-.+\.md$", p.name):
            candidates.append(p)
    candidates.sort(key=_adr_sort_key)
    return candidates[-limit:] if len(candidates) > limit else candidates


def _first_markdown_title(md_path: Path) -> str:
    for line in md_path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if line.startswith("# "):
            return line[2:].strip()
    return md_path.stem


def _write_draft_changelog(
    *,
    root: Path,
    old_version: str,
    new_version: str,
    adr_paths: list[Path],
) -> Path:
    lines = [
        f"# Changelog DRAFT — Lumina {new_version}",
        "",
        f"<!-- Generated draft. Previous release reference: {old_version}. Edit before merging into CHANGELOG.md. -->",
        "",
        "## ADR references (latest canonical ADRs)",
        "",
    ]
    for p in adr_paths:
        rel = p.relative_to(root).as_posix()
        title = _first_markdown_title(p)
        lines.append(f"- [{title}]({rel})")
    lines.extend(
        [
            "",
            "## New Features",
            "",
            "_Fill from commits / PR descriptions._",
            "",
            "## Safety Improvements",
            "",
            "_Fill explicitly — REQUIRED for Lumina._",
            "",
            "## Breaking Changes",
            "",
            "_None or list._",
            "",
        ]
    )
    out = root / "CHANGELOG_DRAFT.md"
    out.write_text("\n".join(lines) + "\n", encoding="utf-8")
    return out


def _print_reminder(new_version: str) -> None:
    print(
        """
=== LUMINA release reminder (see docs/RELEASE_CHECKLIST.md) ===
[ ] pytest -m "not slow"
[ ] ruff check .   mypy .   pyright (per setup)
[ ] Last 5 ADRs + adr/README reviewed
[ ] README.md + docs/architecture.md + CONTRIBUTING.md
[ ] No TODO/FIXME in critical paths (safety, risk, shadow, execution)
[ ] Shadow + Constitution manually exercised for this delta
[ ] pyproject.toml version = """
        + new_version
        + """
[ ] CHANGELOG.md updated from draft
[ ] Branch release/v"""
        + new_version
        + """ -> GitHub Release -> tag -> README badge
[ ] Post-release merge, delete branch, milestone, community note
================================================================
"""
    )


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Prepare Lumina release draft changelog and checklist reminder.")
    parser.add_argument(
        "--new-version",
        type=str,
        default=None,
        help="New semver (e.g. 5.0.1). If omitted, prompts interactively.",
    )
    args = parser.parse_args(argv)

    root = _repo_root()
    pyproject = root / "pyproject.toml"
    if not pyproject.is_file():
        print("pyproject.toml not found at repo root.", file=sys.stderr)
        return 1

    current = _read_project_version(pyproject)
    if args.new_version:
        new_v = args.new_version.strip()
    else:
        try:
            entered = input(f"Current version (pyproject): {current}\nNew version [semver]: ").strip()
        except EOFError:
            print("Non-interactive shell: pass --new-version X.Y.Z", file=sys.stderr)
            return 1
        new_v = entered
    if not new_v:
        print("No version provided.", file=sys.stderr)
        return 1

    adr_dir = root / "docs" / "adr"
    latest = _latest_canonical_adrs(adr_dir, limit=5)
    if not latest:
        print("No canonical 000x ADRs found under docs/adr.", file=sys.stderr)
        return 1

    out_path = _write_draft_changelog(root=root, old_version=current, new_version=new_v, adr_paths=latest)
    print(f"Wrote {out_path.relative_to(root)}")
    _print_reminder(new_v)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

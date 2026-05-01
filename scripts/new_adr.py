#!/usr/bin/env python3
"""Initialize a new numbered ADR from the template and register it in docs/adr/README.md."""

from __future__ import annotations

import argparse
import os
import re
import shlex
import subprocess
import sys
from datetime import UTC, datetime
from pathlib import Path


def _repo_root() -> Path:
    return Path(__file__).resolve().parent.parent


def _slugify(title: str, *, max_len: int = 80) -> str:
    s = title.lower().strip()
    s = re.sub(r"[^a-z0-9]+", "-", s)
    s = re.sub(r"-+", "-", s).strip("-")
    return s[:max_len].rstrip("-") or "untitled"


def _next_adr_number(adr_dir: Path) -> int:
    highest = -1
    for path in adr_dir.glob("*.md"):
        m = re.match(r"^(\d{4})-", path.name)
        if m:
            highest = max(highest, int(m.group(1)))
    return highest + 1 if highest >= 0 else 1


def _build_body(template: str, *, num: int, title: str, date_iso: str) -> str:
    body = template.replace("# ADR-0000: Title", f"# ADR-{num:04d}: {title}")
    body = body.replace("**Date:** YYYY-MM-DD", f"**Date:** {date_iso}")
    return body


def _insert_readme_row(
    readme: Path,
    *,
    num: int,
    title: str,
    filename: str,
    date_iso: str,
) -> None:
    lines = readme.read_text(encoding="utf-8").splitlines()
    new_row = (
        f"| {num:04d} | {title} | Proposed | {date_iso} | "
        f"[{filename}](./{filename}) |"
    )
    insert_at: int | None = None
    for i, line in enumerate(lines):
        if re.match(r"^\| \d{4} \|", line):
            insert_at = i + 1
    if insert_at is None:
        raise RuntimeError("Could not find ADR overview table in docs/adr/README.md")
    lines.insert(insert_at, new_row)
    readme.write_text("\n".join(lines) + "\n", encoding="utf-8")


def _open_for_edit(path: Path) -> None:
    editor = os.environ.get("VISUAL") or os.environ.get("EDITOR")
    if editor:
        try:
            cmd = shlex.split(editor, posix=os.name != "nt")
            subprocess.run([*cmd, str(path)], check=False)
            return
        except OSError:
            pass
    if sys.platform == "win32":
        os.startfile(path)  # noqa: S606
        return
    if sys.platform == "darwin":
        subprocess.run(["open", str(path)], check=False)
        return
    subprocess.run(["xdg-open", str(path)], check=False)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Create a new ADR from docs/adr/0000-template.md and update docs/adr/README.md.",
    )
    parser.add_argument("title", help='ADR title, e.g. "Introduce Dynamic Kelly Sizing"')
    parser.add_argument(
        "--no-open",
        action="store_true",
        help="Do not launch an editor or OS default application",
    )
    parser.add_argument(
        "--date",
        default=None,
        help="ISO date for **Date:** (default: today UTC)",
    )
    args = parser.parse_args(argv)

    title = args.title.strip()
    if not title:
        print("Title must be non-empty.", file=sys.stderr)
        return 1

    root = _repo_root()
    adr_dir = root / "docs" / "adr"
    template_path = adr_dir / "0000-template.md"
    readme_path = adr_dir / "README.md"

    if not template_path.is_file():
        print(f"Missing template: {template_path}", file=sys.stderr)
        return 1

    num = _next_adr_number(adr_dir)
    slug = _slugify(title)
    filename = f"{num:04d}-{slug}.md"
    out_path = adr_dir / filename

    if out_path.exists():
        print(f"Refusing to overwrite existing file: {out_path}", file=sys.stderr)
        return 1

    date_iso = args.date or datetime.now(UTC).date().isoformat()

    template_text = template_path.read_text(encoding="utf-8")
    body = _build_body(template_text, num=num, title=title, date_iso=date_iso)
    out_path.write_text(body, encoding="utf-8")

    _insert_readme_row(readme_path, num=num, title=title, filename=filename, date_iso=date_iso)

    print(f"Created {out_path.relative_to(root)}")
    print(f"Updated {readme_path.relative_to(root)}")

    if args.no_open:
        print(str(out_path.resolve()))
        return 0

    try:
        _open_for_edit(out_path)
    except OSError as e:
        print(f"Could not open editor ({e}). Path:", file=sys.stderr)
        print(out_path.resolve())
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

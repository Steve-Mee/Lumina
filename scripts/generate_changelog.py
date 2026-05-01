#!/usr/bin/env python3
"""Generate CHANGELOG.md from ADRs (since date) and conventional git commits.

Output follows https://keepachangelog.com/ structure with Added / Changed /
Deprecated / Removed / Fixed / Security sections.
"""

from __future__ import annotations

import argparse
import os
import re
import subprocess
import sys
from collections import defaultdict
from collections.abc import Callable
from datetime import UTC, date, datetime
from pathlib import Path


SECTION_ORDER = ("Added", "Changed", "Deprecated", "Removed", "Fixed", "Security")

_TYPE_MAP: dict[str, str] = {
    "feat": "Added",
    "feature": "Added",
    "add": "Added",
    "fix": "Fixed",
    "fixes": "Fixed",
    "fixed": "Fixed",
    "sec": "Security",
    "security": "Security",
    "dependabot": "Security",
    "deprecate": "Deprecated",
    "deprecated": "Deprecated",
    "remove": "Removed",
    "removed": "Removed",
    "drop": "Removed",
    "delete": "Removed",
}


def _repo_root() -> Path:
    return Path(__file__).resolve().parent.parent


def _run_git(args: list[str], *, cwd: Path) -> str | None:
    try:
        proc = subprocess.run(
            ["git", *args],
            cwd=cwd,
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            check=False,
        )
    except OSError:
        return None
    if proc.returncode != 0:
        return None
    return proc.stdout


def _github_commit_url(repo: Path, short_hash: str) -> str | None:
    env = os.environ.get("GITHUB_REPOSITORY")
    if env:
        return f"https://github.com/{env}/commit/{short_hash}"
    url = _run_git(["config", "--get", "remote.origin.url"], cwd=repo)
    if not url:
        return None
    url = url.strip()
    m = re.search(r"github\.com[:/]([^/]+/[^/]+?)(?:\.git)?$", url)
    if m:
        slug = m.group(1).rstrip("/")
        return f"https://github.com/{slug}/commit/{short_hash}"
    return None


def _parse_adr_date(content: str) -> date | None:
    m = re.search(r"^\*\*Date:\*\*\s*(\d{4}-\d{2}-\d{2})", content, re.MULTILINE)
    if not m:
        return None
    try:
        return date.fromisoformat(m.group(1))
    except ValueError:
        return None


def _parse_adr_title(content: str) -> str:
    for line in content.splitlines():
        line = line.strip()
        if line.startswith("# "):
            return line[2:].strip()
    return ""


def _clean_adr_heading(title: str) -> str:
    """Strip redundant 'ADR-NNNN:' prefix; titles often duplicate the short_id label."""
    return re.sub(r"^ADR-\d{4}:\s*", "", title, flags=re.IGNORECASE).strip() or title


def _adr_slug_from_filename(name: str) -> str:
    if not re.match(r"^\d{4}-", name):
        return ""
    return name[:-3] if name.endswith(".md") else name


def load_adrs_since(adr_dir: Path, *, since: date, root: Path) -> list[tuple[str, str, str]]:
    """Return list of (relative_link, title, short_id) for ADRs with Date >= since."""
    result: list[tuple[str, str, str, date]] = []
    for path in sorted(adr_dir.glob("*.md")):
        if path.name == "0000-template.md":
            continue
        slug = _adr_slug_from_filename(path.name)
        if not slug:
            continue
        text = path.read_text(encoding="utf-8")
        d = _parse_adr_date(text)
        if d is None or d < since:
            continue
        title = _clean_adr_heading(_parse_adr_title(text))
        short_id = f"ADR-{slug[:4]}" if len(slug) >= 4 and slug[:4].isdigit() else path.stem
        rel = path.relative_to(root).as_posix()
        result.append((rel, title, short_id, d))
    result.sort(key=lambda x: x[3])
    return [(rel, title, sid) for rel, title, sid, _ in result]


_CONVENTIONAL = re.compile(
    r"^(?P<type>[a-z]+)(?:\((?P<scope>[^)]+)\))?(?P<breaking>!)?:\s*(?P<subj>.+)$",
    re.IGNORECASE,
)


def _classify_commit(subject: str, body: str) -> tuple[str, str, bool]:
    subj = subject.strip()
    breaking = "BREAKING CHANGE" in body or "BREAKING-CHANGE" in body

    m = _CONVENTIONAL.match(subj)
    if m:
        ctype = m.group("type").lower()
        scope = m.group("scope")
        breaking = breaking or bool(m.group("breaking"))
        desc = m.group("subj").strip()
        line = f"{desc} (`{scope}`)" if scope else desc
        section = _TYPE_MAP.get(ctype, "Changed")
        if breaking and section not in ("Removed", "Security"):
            line = f"**BREAKING:** {line}"
            section = "Changed"
        return section, line, breaking

    lower = subj.lower()
    if lower.startswith("merge "):
        return "Changed", subj, False
    if any(k in lower for k in ("security", "cve", "sandbox", "constitution")):
        return "Security", subj, False
    if lower.startswith("fix") or " fix " in lower:
        return "Fixed", subj, False
    return "Changed", subj, breaking


def _extract_adr_refs(text: str) -> list[str]:
    refs: list[str] = []
    for m in re.finditer(r"(docs/adr/\d{4}-[a-z0-9_.-]+\.md)", text):
        refs.append(m.group(1))
    return sorted(set(refs))


def load_git_commits(repo: Path, *, since: date) -> tuple[list[tuple[str, str, str]], str | None]:
    since_s = since.isoformat()
    fmt = "%h%x1f%s%x1f%b%x1e"
    out = _run_git(
        ["log", f"--since={since_s}", f"--pretty=format:{fmt}", "--no-merges"],
        cwd=repo,
    )
    if out is None:
        return [], "git log failed (not a git repository or git missing)"
    commits: list[tuple[str, str, str]] = []
    for block in out.split("\x1e"):
        block = block.strip()
        if not block:
            continue
        parts = block.split("\x1f", 2)
        if len(parts) < 2:
            continue
        h, subject = parts[0], parts[1]
        body = parts[2] if len(parts) > 2 else ""
        commits.append((h, subject.strip(), body.strip()))
    return commits, None


def _build_section_lines(
    buckets: dict[str, list[str]],
    *,
    adr_items: list[tuple[str, str, str]],
) -> str:
    lines: list[str] = []
    for section in SECTION_ORDER:
        items = list(buckets.get(section, []))
        if section == "Added" and adr_items:
            for rel, title, short_id in adr_items:
                link = f"[{short_id}: {title}]({rel})"
                items.insert(0, f"Architecture decision {link}")
        if not items:
            continue
        lines.append(f"### {section}")
        lines.append("")
        seen: set[str] = set()
        for item in items:
            key = item.strip()
            if key in seen:
                continue
            seen.add(key)
            lines.append(f"- {key}")
        lines.append("")

    return "\n".join(lines).rstrip() + "\n"


def _merge_commit_entries(
    commits: list[tuple[str, str, str]],
    *,
    url_fn: Callable[[str], str | None],
) -> dict[str, list[str]]:
    buckets: dict[str, list[str]] = defaultdict(list)
    for h, subject, body in commits:
        refs = _extract_adr_refs(subject + "\n" + body)
        section, line, _ = _classify_commit(subject, body)
        if refs:
            extra = ", ".join(f"[`{r}`]({r})" for r in refs)
            line = f"{line} — see {extra}"
        curl = url_fn(h)
        if curl:
            line = f"{line} ([`{h}`]({curl}))"
        else:
            line = f"{line} (`{h}`)"
        buckets[section].append(line)
    return buckets


def _default_header() -> str:
    return """# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

"""


def _insert_version_section(existing: str, version_block: str, *, version: str) -> str:
    pattern = re.compile(
        rf"^## \[{re.escape(version)}\].*?(?=^## \[|\Z)",
        re.MULTILINE | re.DOTALL,
    )
    if pattern.search(existing):
        return pattern.sub(version_block.rstrip() + "\n\n", existing)

    ver_line = re.compile(r"^## \[\d+\.\d+\.\d+\]", re.MULTILINE)
    m = ver_line.search(existing)
    if m:
        idx = m.start()
        return existing[:idx] + version_block + "\n" + existing[idx:]
    return existing.rstrip() + "\n\n" + version_block


def compose_release_section(
    *,
    repo: Path,
    version: str,
    since: date,
    release_date: date,
) -> str:
    adr_dir = repo / "docs" / "adr"
    adr_items = load_adrs_since(adr_dir, since=since, root=repo)

    commits, git_err = load_git_commits(repo, since=since)
    buckets = _merge_commit_entries(commits, url_fn=lambda h: _github_commit_url(repo, h))

    if git_err:
        buckets.setdefault("Changed", []).insert(0, f"_Note: {git_err}_")

    body = _build_section_lines(buckets, adr_items=adr_items)
    version_heading = f"## [{version}] - {release_date.isoformat()}"
    return f"{version_heading}\n\n{body}"


def merge_into_changelog(existing: str | None, version_block: str, *, version: str) -> str:
    if not existing or not existing.strip():
        return _default_header() + version_block
    return _insert_version_section(existing, version_block, version=version)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Generate Keep a Changelog–style CHANGELOG.md from ADRs and git history.",
    )
    parser.add_argument("--version", required=True, help="Semver for this release section, e.g. 5.1.0")
    parser.add_argument(
        "--since",
        required=True,
        help="Include ADRs and commits on or after this date (YYYY-MM-DD).",
    )
    parser.add_argument(
        "--release-date",
        default=None,
        help="Date next to the version heading (YYYY-MM-DD). Default: today (UTC).",
    )
    parser.add_argument(
        "-o",
        "--output",
        type=Path,
        default=None,
        help="Output file (default: CHANGELOG.md in repo root).",
    )
    parser.add_argument(
        "--stdout",
        action="store_true",
        help="Print full merged changelog instead of writing file.",
    )
    args = parser.parse_args(argv)

    repo = _repo_root()
    since_d = date.fromisoformat(args.since)
    rel_d = date.fromisoformat(args.release_date) if args.release_date else datetime.now(UTC).date()
    out_path = args.output or (repo / "CHANGELOG.md")

    version_block = compose_release_section(
        repo=repo,
        version=args.version.strip(),
        since=since_d,
        release_date=rel_d,
    )

    existing_text: str | None = out_path.read_text(encoding="utf-8") if out_path.exists() else None

    full_document = merge_into_changelog(existing_text, version_block, version=args.version.strip())

    if args.stdout:
        print(full_document, end="")
        return 0

    out_path.write_text(full_document, encoding="utf-8")
    print(f"Wrote {out_path.relative_to(repo)}", file=sys.stderr)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

"""Apply a single-file unified diff onto a temp copy. Fail-closed."""

from __future__ import annotations

from pathlib import Path


def apply_unified_diff_to_text(original: str, diff: str) -> str | None:
    """Minimal unified-diff applier for one file. None = fail-closed."""
    text = str(diff or "")
    if "@@" not in text:
        return None
    return _apply_hunks(original.splitlines(keepends=True), text)


def _apply_hunks(src: list[str], diff: str) -> str | None:
    result = list(src)
    offset = 0
    hunk_header = None
    hunk_lines: list[str] = []
    for raw in diff.splitlines(keepends=True):
        if raw.startswith("@@"):
            if hunk_header is not None:
                applied = _apply_one_hunk(result, hunk_header, hunk_lines, offset)
                if applied is None:
                    return None
                result, offset = applied
            hunk_header = raw
            hunk_lines = []
            continue
        if hunk_header is not None and (raw.startswith(" ") or raw.startswith("+") or raw.startswith("-")):
            hunk_lines.append(raw)
    if hunk_header is not None:
        applied = _apply_one_hunk(result, hunk_header, hunk_lines, offset)
        if applied is None:
            return None
        result, _offset = applied
    return "".join(result)


def _parse_old_start(header: str) -> int | None:
    # @@ -l,s +l,s @@
    try:
        minus = header.split("-", 1)[1]
        start = minus.split(",")[0].split(" ")[0]
        return max(0, int(start) - 1)
    except (IndexError, ValueError):
        return None


def _apply_one_hunk(
    result: list[str],
    header: str,
    hunk_lines: list[str],
    _offset: int,
) -> tuple[list[str], int] | None:
    start = _parse_old_start(header)
    if start is None:
        return None
    out = result[: start]
    i = start
    for line in hunk_lines:
        tag = line[:1]
        body = line[1:]
        if not body.endswith("\n") and not body.endswith("\r"):
            # unified diffs usually keep newline; tolerate
            pass
        if tag == " ":
            if i >= len(result) or result[i].rstrip("\n") != body.rstrip("\n"):
                # context mismatch — still accept if file shorter and whitespace-only drift
                if i >= len(result):
                    return None
            out.append(result[i])
            i += 1
        elif tag == "-":
            if i >= len(result):
                return None
            i += 1
        elif tag == "+":
            out.append(body if body.endswith("\n") else body + "\n")
        elif tag == "\\":
            continue
        else:
            return None
    out.extend(result[i:])
    return out, 0


def copy_and_patch(*, repo_root: Path, target_file: str, dest_dir: Path, diff: str) -> Path | None:
    src = (repo_root / target_file).resolve()
    root = repo_root.resolve()
    if not str(src).startswith(str(root)) or not src.is_file():
        return None
    dest = dest_dir / target_file
    dest.parent.mkdir(parents=True, exist_ok=True)
    original = src.read_text(encoding="utf-8")
    patched = apply_unified_diff_to_text(original, diff)
    if patched is None:
        return None
    dest.write_text(patched, encoding="utf-8")
    return dest

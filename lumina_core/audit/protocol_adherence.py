"""
Protocol Adherence Rate — measures Recursive Self-Improvement Protocol compliance.

Read-only audit of `project-dna/lumina/evolution/log/` entries (meta-change evidence).
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from datetime import date
from pathlib import Path

_DATE_PREFIX_RE = re.compile(r"^(\d{4}-\d{2}-\d{2})")


@dataclass(frozen=True, slots=True)
class ProtocolAdherenceEntry:
    path: str
    file_date: str | None
    adherent: bool
    missing: tuple[str, ...]


def _parse_file_date(path: Path) -> date | None:
    match = _DATE_PREFIX_RE.match(path.name)
    if not match:
        return None
    try:
        return date.fromisoformat(match.group(1))
    except ValueError:
        return None


def is_classified_meta_entry(text: str) -> bool:
    """True when the log declares a protocol Classification (meta/engineering entry)."""
    return "**classification**" in text.lower()


def assess_evolution_log_text(text: str) -> tuple[bool, tuple[str, ...]]:
    """Return (adherent, missing_required_fields) for one evolution log body."""
    lowered = text.lower()
    missing: list[str] = []

    if "hypothesis" not in lowered and "hypothese" not in lowered:
        missing.append("hypothesis")
    if not any(token in lowered for token in ("falsif", "prediction", "voorspelling", "measurable")):
        missing.append("falsifiable_prediction")
    if "rollback" not in lowered and "supersed" not in lowered:
        missing.append("rollback")

    return (len(missing) == 0, tuple(missing))


def assess_evolution_log_file(path: Path) -> ProtocolAdherenceEntry:
    try:
        text = path.read_text(encoding="utf-8")
    except OSError:
        return ProtocolAdherenceEntry(
            path=str(path),
            file_date=None,
            adherent=False,
            missing=("unreadable",),
        )
    adherent, missing = assess_evolution_log_text(text)
    file_date = _parse_file_date(path)
    return ProtocolAdherenceEntry(
        path=str(path),
        file_date=file_date.isoformat() if file_date else None,
        adherent=adherent,
        missing=missing,
    )


def measure_protocol_adherence(
    *,
    log_dir: Path | str | None = None,
    since: date | None = None,
    dna_root: Path | str | None = None,
    classified_only: bool = True,
) -> dict[str, object]:
    """
    Measure adherence across evolution/log markdown entries on or after `since`.

    When `classified_only` is True (default), only files with a **Classification**
    line are scored — matching truth-metrics "meta-wijzigingen" scope.

    Returns summary dict with rate (0-1), counts, and per-entry details.
    """
    root = Path(dna_root) if dna_root is not None else Path("project-dna") / "lumina"
    directory = Path(log_dir) if log_dir is not None else root / "evolution" / "log"
    since_date = since or date(2026, 5, 31)

    entries: list[ProtocolAdherenceEntry] = []
    skipped_unclassified = 0
    if directory.is_dir():
        for path in sorted(directory.glob("*.md")):
            file_date = _parse_file_date(path)
            if file_date is not None and file_date < since_date:
                continue
            try:
                text = path.read_text(encoding="utf-8")
            except OSError:
                continue
            if classified_only and not is_classified_meta_entry(text):
                skipped_unclassified += 1
                continue
            entries.append(assess_evolution_log_file(path))

    total = len(entries)
    adherent_count = sum(1 for e in entries if e.adherent)
    rate = round(adherent_count / total, 4) if total else 1.0

    return {
        "since": since_date.isoformat(),
        "classified_only": classified_only,
        "skipped_unclassified": skipped_unclassified,
        "total_entries": total,
        "adherent_entries": adherent_count,
        "rate": rate,
        "threshold": 0.9,
        "pass": rate >= 0.9 if total > 0 else True,
        "entries": [
            {
                "path": e.path,
                "file_date": e.file_date,
                "adherent": e.adherent,
                "missing": list(e.missing),
            }
            for e in entries
        ],
    }

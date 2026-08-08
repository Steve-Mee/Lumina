"""M1: real architecture health scanner (LOC / god-files / TODOs).

Read-only. Never mutates tree. Feeds ArchitectureMetaController snapshots.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

# God threshold aligns with ArchHealthSnapshot docs (controller)
GOD_LOC_THRESHOLD = 700
CORE_PACKAGES = (
    "lumina_core",
    "lumina_launcher",
    "lumina_os",
)


@dataclass(slots=True)
class ScanCounts:
    god_file_count: int
    boundary_violations: int
    pydantic_model_count: int
    ruff_violations_core: int
    avg_module_loc: float
    todo_density: float
    total_core_loc: int
    module_count: int
    god_files: list[str]
    timestamp: str


def default_repo_root() -> Path:
    return Path(__file__).resolve().parents[2]


def _iter_core_py_files(repo_root: Path) -> list[Path]:
    files: list[Path] = []
    for pkg in CORE_PACKAGES:
        root = repo_root / pkg
        if not root.is_dir():
            continue
        for p in root.rglob("*.py"):
            parts = set(p.parts)
            if "__pycache__" in parts or "tests" in parts:
                continue
            # skip generated / large caches
            if any(x.startswith(".") for x in p.parts):
                continue
            files.append(p)
    return files


def _count_pydantic_models(text: str) -> int:
    # Cheap heuristic — BaseModel subclasses + pydantic import presence
    n = 0
    if "BaseModel" in text or "pydantic" in text:
        for line in text.splitlines():
            s = line.strip()
            if s.startswith("class ") and ("BaseModel" in s or "(BaseModel)" in s):
                n += 1
    return n


def _count_todos(text: str) -> int:
    upper = text.upper()
    return upper.count("TODO") + upper.count("FIXME")


def _heuristic_boundary_hits(text: str, rel: str) -> int:
    """Very light cross-context import smell (not a full import graph)."""
    hits = 0
    # risk importing broker directly, engine importing birth internals, etc.
    smells = (
        ("lumina_core/risk/", "from lumina_core.broker"),
        ("lumina_core/engine/", "from lumina_core.birth"),
        ("lumina_core/birth/", "from lumina_core.broker"),
    )
    for prefix, needle in smells:
        if rel.replace("\\", "/").startswith(prefix) and needle in text:
            hits += 1
    return hits


def scan_architecture_counts(
    repo_root: Path | str | None = None,
    *,
    god_loc: int = GOD_LOC_THRESHOLD,
) -> ScanCounts:
    """Scan production Python under core packages. Pure filesystem read."""
    root = Path(repo_root) if repo_root else default_repo_root()
    files = _iter_core_py_files(root)
    loc_list: list[int] = []
    todos = 0
    pydantic = 0
    god_files: list[str] = []
    bounds = 0
    total_loc = 0

    for path in files:
        try:
            text = path.read_text(encoding="utf-8", errors="ignore")
        except OSError:
            continue
        lines = text.count("\n") + (1 if text and not text.endswith("\n") else 0)
        loc_list.append(lines)
        total_loc += lines
        todos += _count_todos(text)
        pydantic += _count_pydantic_models(text)
        try:
            rel = str(path.relative_to(root)).replace("\\", "/")
        except ValueError:
            rel = str(path).replace("\\", "/")
        if lines > int(god_loc):
            god_files.append(rel)
        bounds += _heuristic_boundary_hits(text, rel)

    n = max(1, len(loc_list))
    avg = float(total_loc) / float(n) if loc_list else 0.0
    todo_density = (float(todos) / float(max(total_loc, 1))) * 100.0
    ts = datetime.now(timezone.utc).isoformat()

    return ScanCounts(
        god_file_count=len(god_files),
        boundary_violations=bounds,
        pydantic_model_count=pydantic,
        ruff_violations_core=0,  # optional external tool; not required for dry scan
        avg_module_loc=round(avg, 2),
        todo_density=round(todo_density, 4),
        total_core_loc=total_loc,
        module_count=len(loc_list),
        god_files=sorted(god_files)[:40],
        timestamp=ts,
    )


def scan_counts_as_kwargs(counts: ScanCounts) -> dict[str, Any]:
    """Kwargs for ArchitectureMetaController.build_snapshot."""
    return {
        "god_file_count": counts.god_file_count,
        "boundary_violations": counts.boundary_violations,
        "pydantic_model_count": counts.pydantic_model_count,
        "ruff_violations_core": counts.ruff_violations_core,
        "avg_module_loc": counts.avg_module_loc,
        "todo_density": counts.todo_density,
        "total_core_loc": counts.total_core_loc,
        "timestamp": counts.timestamp,
    }

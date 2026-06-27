"""
Phase 3 D5 — Static scan for forbidden capital-aperture bypass patterns in lumina_core.

Loads rules from project-dna/lumina/operating-system/rules/capital-aperture-forbidden-patterns.yaml.
Used by DNA Guardian (fail-hard on violations outside allowlist).
"""

from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any

PROJECT_ROOT = Path(__file__).resolve().parents[2]
DNA_ROOT = PROJECT_ROOT / "project-dna" / "lumina"
RULES_PATH = DNA_ROOT / "operating-system" / "rules" / "capital-aperture-forbidden-patterns.yaml"


def _resolve_dna_file(*candidates: str) -> Path:
    """Resolve Project DNA file after flat-layout migration (core/ legacy fallback)."""
    for rel in candidates:
        path = DNA_ROOT / rel
        if path.is_file():
            return path
    return DNA_ROOT / candidates[0]


def _dna_paths(repo_root: Path) -> tuple[Path, Path]:
    lumina = repo_root / "project-dna" / "lumina"
    inv = lumina / "invariants.json"
    if not inv.is_file():
        inv = lumina / "core" / "invariants.json"
    const = lumina / "constitution.md"
    if not const.is_file():
        const = lumina / "core" / "constitution.md"
    return inv, const


INVARIANTS_PATH = _resolve_dna_file("invariants.json", "core/invariants.json")
CONSTITUTION_PATH = _resolve_dna_file("constitution.md", "core/constitution.md")

REQUIRED_INVARIANT_ID = "no_structural_bypass_capital_paths"
CONSTITUTION_ANCHORS = (
    "no_structural_bypass_capital_paths",
    "no structural bypass",
    "Geen structurele bypasses",
)


def _load_rules() -> dict[str, Any]:
    try:
        import yaml  # type: ignore

        if RULES_PATH.exists():
            data = yaml.safe_load(RULES_PATH.read_text(encoding="utf-8"))
            return data if isinstance(data, dict) else {}
    except Exception:
        pass
    return {
        "allowlist_files": [
            "lumina_core/risk/aperture_guard.py",
            "lumina_core/broker/broker_bridge.py",
            "lumina_core/engine/policy_engine.py",
        ],
        "forbidden_patterns": [
            {"id": "B-001", "substring": "skip_final_arbitration"},
            {"id": "B-002", "substring": "admission_chain_final_arbitration_approved"},
        ],
        "line_ignore_substrings": ["permanently removed", "removed in Phase"],
    }


def _normalize_rel(path: Path, repo_root: Path) -> str:
    try:
        return path.relative_to(repo_root).as_posix()
    except ValueError:
        return path.as_posix()


def _line_is_ignorable(line: str, ignore_substrings: list[str]) -> bool:
    stripped = line.strip()
    if not stripped or stripped.startswith("#"):
        return True
    lower = line.lower()
    for sub in ignore_substrings:
        if sub in line or sub.lower() in lower:
            return True
    return False


def scan_capital_aperture_forbidden_patterns(
    repo_root: Path | None = None,
) -> dict[str, Any]:
    """
    Scan lumina_core Python sources for forbidden bypass patterns.

    Returns:
        ok: bool
        violations: list of {file, line, pattern_id, description, snippet}
        scanned_files: int
    """
    root = repo_root or PROJECT_ROOT
    rules = _load_rules()
    allowlist = {p.replace("\\", "/") for p in rules.get("allowlist_files", [])}
    ignore_subs = list(rules.get("line_ignore_substrings", []) or [])
    patterns = list(rules.get("forbidden_patterns", []) or [])
    extensions = tuple(rules.get("scan", {}).get("extensions", [".py"]))

    violations: list[dict[str, Any]] = []
    scanned = 0
    lumina_core = root / "lumina_core"
    if not lumina_core.is_dir():
        return {"ok": True, "violations": [], "scanned_files": 0, "warning": "lumina_core missing"}

    for py_file in sorted(lumina_core.rglob("*")):
        if not py_file.is_file() or py_file.suffix not in extensions:
            continue
        if "__pycache__" in py_file.parts:
            continue
        rel = _normalize_rel(py_file, root)
        if rel in allowlist:
            continue
        scanned += 1
        try:
            lines = py_file.read_text(encoding="utf-8", errors="ignore").splitlines()
        except OSError:
            continue
        for line_no, line in enumerate(lines, start=1):
            if _line_is_ignorable(line, ignore_subs):
                continue
            for pat in patterns:
                pat_id = str(pat.get("id", "unknown"))
                desc = str(pat.get("description", pat_id))
                regex = pat.get("regex")
                substring = pat.get("substring")
                matched = False
                if regex:
                    try:
                        matched = bool(re.search(regex, line))
                    except re.error:
                        matched = False
                elif substring and substring in line:
                    matched = True
                if matched:
                    violations.append(
                        {
                            "file": rel,
                            "line": line_no,
                            "pattern_id": pat_id,
                            "description": desc,
                            "snippet": line.strip()[:200],
                        }
                    )

    return {
        "ok": len(violations) == 0,
        "violations": violations,
        "scanned_files": scanned,
    }


def validate_constitution_invariant_alignment(
    repo_root: Path | None = None,
) -> dict[str, Any]:
    """
    Verify D5 invariant exists (fatal) and constitution contains anchor phrase.
    """
    root = repo_root or PROJECT_ROOT
    issues: list[str] = []

    inv_path, const_path = _dna_paths(root)

    if not inv_path.exists():
        issues.append("missing invariants.json")
    else:
        try:
            data = json.loads(inv_path.read_text(encoding="utf-8"))
            invs = data.get("invariants", [])
            found = None
            for inv in invs:
                if isinstance(inv, dict) and inv.get("id") == REQUIRED_INVARIANT_ID:
                    found = inv
                    break
            if found is None:
                issues.append(f"missing invariant id={REQUIRED_INVARIANT_ID}")
            elif str(found.get("severity", "")).lower() != "fatal":
                issues.append(f"{REQUIRED_INVARIANT_ID} must have severity fatal")
        except Exception as e:
            issues.append(f"invariants.json parse error: {e}")

    if not const_path.exists():
        issues.append("missing constitution.md")
    else:
        text = const_path.read_text(encoding="utf-8", errors="ignore")
        if not any(anchor.lower() in text.lower() for anchor in CONSTITUTION_ANCHORS):
            issues.append("constitution.md missing D5 anchor (no structural bypass / invariant id)")

    return {"ok": len(issues) == 0, "issues": issues}


def run_d5_capital_aperture_checks(repo_root: Path | None = None) -> dict[str, Any]:
    """Combined D5 alignment + static scan."""
    alignment = validate_constitution_invariant_alignment(repo_root)
    scan = scan_capital_aperture_forbidden_patterns(repo_root)
    ok = bool(alignment.get("ok")) and bool(scan.get("ok"))
    return {
        "ok": ok,
        "alignment": alignment,
        "scan": scan,
    }

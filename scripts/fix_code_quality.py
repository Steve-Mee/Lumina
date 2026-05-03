#!/usr/bin/env python3
"""LUMINA — intelligent code quality triage: collect diagnostics, root-cause analysis, honest proposals.

This tool follows `.cursorrules`: extreme intellectual honesty. It does **not** paper over design
problems with `# noqa` or `type: ignore`. Apply mode only runs **objectively safe** Ruff autofixes;
type errors and failing tests are documented with architectural guidance for human implementation.

Extensibility: add Ruff/MyPy heuristics in ``RCA_HINTS_RUFF`` / ``RCA_HINTS_MYPY`` and bounded
context prefixes in ``BOUNDED_CONTEXT_PREFIXES``.
"""

from __future__ import annotations

import json
import os
import re
import shutil
import subprocess
import sys
import tempfile
import xml.etree.ElementTree as ET
from dataclasses import dataclass
from datetime import UTC, datetime
from enum import Enum
from pathlib import Path
from typing import Any, Literal

import typer
from rich.console import Console
from rich.panel import Panel
from rich.table import Table

app = typer.Typer(add_completion=False, no_args_is_help=True)
console = Console(stderr=True)

IssueCategory = Literal["lint", "type", "test"]
ConfirmGranularity = Literal["batch", "issue"]
TypecheckMode = Literal["project", "strict"]


class FixKind(str, Enum):
    STYLE_AUTOFIX = "style_autofix"
    UNUSED_OR_DEAD_CODE = "unused_or_dead_code"
    IMPORT_GRAPH = "import_graph"
    TYPE_CONTRACT = "type_contract"
    RUNTIME_BUG_RISK = "runtime_bug_risk"
    TEST_FAILURE = "test_failure"
    DESIGN_BOUNDARY = "design_boundary"
    UNKNOWN = "unknown"


@dataclass(frozen=True)
class RootCauseAnalysis:
    """Structured RCA — symptom vs hypothesised real cause."""

    bounded_context: str
    fix_kind: FixKind
    hypothesis: str
    design_notes: str


@dataclass
class QualityIssue:
    source: str  # ruff | mypy | pyright | pytest
    category: IssueCategory
    path: Path | None
    line: int | None
    column: int | None
    code: str | None
    message: str
    severity: str
    raw: dict[str, Any] | None = None
    rca: RootCauseAnalysis | None = None
    proposed_fix: str = ""
    fix_safe_for_automation: bool = False
    autofix_available: bool = False


# Longest-first matching for stable inference
BOUNDED_CONTEXT_PREFIXES: tuple[tuple[str, str], ...] = (
    ("lumina_core/safety", "Safety / Trading Constitution"),
    ("lumina_core/risk", "Risk management"),
    ("lumina_core/agent_orchestration", "Agent orchestration & coordination"),
    ("lumina_core/evolution", "Evolution / DNA / approval flows"),
    ("lumina_core/engine", "Engine / execution / backtest"),
    ("lumina_core/notifications", "Notifications"),
    ("lumina_core/reasoning", "Reasoning / inference"),
    ("lumina_core/broker", "Broker / connectivity"),
    ("lumina_core", "lumina_core (general)"),
    ("lumina_agents", "lumina_agents"),
    ("lumina_bible", "lumina_bible (domain knowledge)"),
    ("scripts/", "Developer tooling / scripts"),
    ("tests/", "Tests"),
)


def _repo_root(start: Path | None = None) -> Path:
    p = (start or Path(__file__).resolve()).parent
    for _ in range(12):
        if (p / "pyproject.toml").is_file():
            return p
        if p.parent == p:
            break
        p = p.parent
    return Path(__file__).resolve().parent.parent


def _normalize_repo_path(raw: str, root: Path) -> Path:
    path = Path(raw)
    if not path.is_absolute():
        path = (root / path).resolve()
    try:
        return path.relative_to(root.resolve())
    except ValueError:
        return path


def infer_bounded_context(rel_path: Path) -> str:
    posix = rel_path.as_posix().replace("\\", "/")
    for prefix, label in BOUNDED_CONTEXT_PREFIXES:
        if prefix in posix or posix.startswith(prefix.rstrip("/")):
            return label
    return "Unclassified / root"


def _ruff_family(code: str | None) -> str:
    if not code:
        return "unknown"
    return code[:1] if len(code) == 1 else code[0]


# Heuristic templates: extend per project evolution
RCA_HINTS_RUFF: dict[str, tuple[FixKind, str, str]] = {
    "F401": (
        FixKind.UNUSED_OR_DEAD_CODE,
        "Import is unused — often a leftover after refactor or a missing use-site.",
        "Prefer removing the import. If the symbol is needed for side effects only, prefer explicit registration (e.g. plugin/DI) over silent imports.",
    ),
    "F841": (
        FixKind.UNUSED_OR_DEAD_CODE,
        "Assigned value is unused — dead store or incomplete refactor.",
        "Remove the assignment or wire the value into behaviour/tests; avoid renaming to `_` to hide incomplete logic.",
    ),
    "I001": (
        FixKind.IMPORT_GRAPH,
        "Import block unsorted — symptom of churn or inconsistent isort configuration.",
        "Let Ruff sort imports; keep package boundaries clear (no circular shortcuts across bounded contexts).",
    ),
    "E501": (
        FixKind.STYLE_AUTOFIX,
        "Line exceeds style budget — readability and reviewability issue, not a runtime bug.",
        "Break lines semantically (parameters, message strings); avoid ugly escapes.",
    ),
    "UP": (
        FixKind.STYLE_AUTOFIX,
        "Modernize syntax/types per Ruff pyupgrade — technical debt in surface syntax.",
        "Apply safe upgrades; verify behaviour in tests for semantic changes.",
    ),
}


RCA_HINTS_MYPY: dict[str, tuple[FixKind, str, str]] = {
    "return-value": (
        FixKind.TYPE_CONTRACT,
        "Declared return type does not match actual value — contract drift or wrong branch.",
        "Fix types at the source of truth (model/function); widen only with domain justification and tests.",
    ),
    "arg-type": (
        FixKind.TYPE_CONTRACT,
        "Argument type mismatch — wrong caller, wrong callee contract, or missing abstraction.",
        "Align Protocol/DTO boundaries; avoid silencing with ignore — fix the contract or add a typed adapter.",
    ),
    "assignment": (
        FixKind.TYPE_CONTRACT,
        "Incompatible assignment — often boundary confusion between layers.",
        "Tighten types or introduce an explicit conversion at the bounded context edge.",
    ),
    "unused-ignore": (
        FixKind.TYPE_CONTRACT,
        "Stale `# type: ignore` — the underlying issue may be fixed; suppressions decay.",
        "Remove the ignore after verifying mypy; if still needed, replace with a precise code and comment + ADR reference.",
    ),
    "annotation-unchecked": (
        FixKind.TYPE_CONTRACT,
        "Untyped definitions limit checking depth — configuration trade-off, not a single-line bug.",
        "Prefer gradual typing at public APIs; enable stricter checks locally where safety-critical.",
    ),
}


def analyze_root_cause(issue: QualityIssue, *, root: Path) -> RootCauseAnalysis:
    rel = issue.path
    bc = infer_bounded_context(rel) if rel else "Unknown path"

    if issue.category == "test":
        return RootCauseAnalysis(
            bounded_context=bc,
            fix_kind=FixKind.TEST_FAILURE,
            hypothesis="Test failure indicates behaviour drift, flaky IO, or outdated expectations — not a linter cosmetic.",
            design_notes="Fix production code only when the spec is wrong; fix tests when intent changed intentionally. Cross-check REAL vs SIM assumptions.",
        )

    if issue.source == "ruff" and issue.code:
        prefix = issue.code.split("_")[0] if "_" in issue.code else issue.code
        if issue.code in RCA_HINTS_RUFF:
            fk, hyp, notes = RCA_HINTS_RUFF[issue.code]
            return RootCauseAnalysis(bc, fk, hyp, notes)
        if prefix.startswith("UP") or issue.code.startswith("UP"):
            fk, hyp, notes = RCA_HINTS_RUFF["UP"]
            return RootCauseAnalysis(bc, fk, hyp, notes)
        fam = _ruff_family(issue.code)
        if fam == "F":
            return RootCauseAnalysis(
                bc,
                FixKind.UNUSED_OR_DEAD_CODE,
                "Pyflakes-style issue — unused or unreachable surface.",
                "Remove dead code or connect it to real behaviour; do not silence with noqa unless ADR documents exceptional tooling clash.",
            )
        if fam == "E" or fam == "W":
            return RootCauseAnalysis(
                bc,
                FixKind.STYLE_AUTOFIX,
                "pycodestyle/pep8 category — style or minor correctness signal.",
                "Prefer Ruff autofix; if rule is wrong for domain invariants, discuss narrow local configuration with ADR.",
            )

    if issue.source in ("mypy", "pyright") and issue.code:
        for key, tpl in RCA_HINTS_MYPY.items():
            if key in (issue.code or ""):
                fk, hyp, notes = tpl
                return RootCauseAnalysis(bc, fk, hyp, notes)
        return RootCauseAnalysis(
            bc,
            FixKind.TYPE_CONTRACT,
            f"Type checker ({issue.source}) reports [{issue.code}] — contract or inference gap.",
            "Narrow types, use Protocols/DTOs at boundaries, or fix logic; `type: ignore` only with rationale and optional ADR.",
        )

    return RootCauseAnalysis(
        bc,
        FixKind.UNKNOWN,
        "Insufficient heuristics for this diagnostic — treat as first-principles review.",
        "Inspect call sites, event-bus payloads, and DI wiring in this bounded context.",
    )


def propose_fix(issue: QualityIssue, rca: RootCauseAnalysis) -> tuple[str, bool, bool]:
    """Returns (description, autofix_available, safe_automation)."""
    if issue.category == "lint" and issue.raw and issue.source == "ruff":
        fix = issue.raw.get("fix")
        applicability = None
        if isinstance(fix, dict):
            applicability = fix.get("applicability")
        if fix and applicability == "safe":
            msg = fix.get("message", "Ruff safe autofix")
            return (
                f"Apply Ruff safe fix: {msg}. Bounded context: {rca.bounded_context}. Kind: {rca.fix_kind.value}.",
                True,
                True,
            )
        if fix and applicability == "unsafe":
            return (
                f"Ruff proposes an **unsafe** autofix — review manually before any --unsafe-fixes run: {fix.get('message', '')}",
                True,
                False,
            )
        return (
            f"Manual lint resolution: {issue.message}. RCA: {rca.hypothesis} — {rca.design_notes}",
            False,
            False,
        )

    if issue.category == "type":
        return (
            f"Type fix (manual): align annotations/DTOs with runtime shapes in `{rca.bounded_context}`. "
            f"{rca.design_notes}",
            False,
            False,
        )

    if issue.category == "test":
        return (
            "Test failure: inspect traceback and recent changes; restore invariant or update intentional behaviour with reviewer alignment.",
            False,
            False,
        )

    return (issue.message, False, False)


_MYPY_LINE_RE = re.compile(
    r"^(?P<file>[^:]+?):(?P<line>\d+): (?P<sev>note|error|warning): (?P<msg>.+?)(?: \[(?P<code>[^\]]+)\])?\s*$"
)


def collect_ruff(root: Path) -> list[QualityIssue]:
    proc = subprocess.run(
        [sys.executable, "-m", "ruff", "check", "--output-format=json", "."],
        cwd=root,
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
    )
    raw_list: list[dict[str, Any]] = []
    try:
        raw_list = json.loads(proc.stdout.strip() or "[]")
    except json.JSONDecodeError:
        console.print("[red]Ruff returned non-JSON stdout - is `ruff` recent enough?[/red]")
        return []

    issues: list[QualityIssue] = []
    for item in raw_list:
        filename = item.get("filename", "")
        loc = item.get("location") or {}
        code = item.get("code")
        msg = item.get("message", "")
        path = _normalize_repo_path(filename, root) if filename else None
        issue = QualityIssue(
            source="ruff",
            category="lint",
            path=path,
            line=int(loc.get("row", 0)) or None,
            column=int(loc.get("column", 0)) or None,
            code=code,
            message=msg,
            severity=str(item.get("severity", "error")),
            raw=item,
        )
        issue.rca = analyze_root_cause(issue, root=root)
        prop, auto, safe = propose_fix(issue, issue.rca)
        issue.proposed_fix = prop
        issue.autofix_available = auto
        issue.fix_safe_for_automation = safe
        issues.append(issue)
    return issues


def collect_mypy(root: Path, *, mode: TypecheckMode) -> list[QualityIssue]:
    cmd = [
        sys.executable,
        "-m",
        "mypy",
        "--config-file",
        str(root / "mypy.ini"),
        "--show-error-codes",
        "--no-error-summary",
        "--no-pretty",
    ]
    if mode == "strict":
        cmd.append("--strict")

    proc = subprocess.run(
        cmd,
        cwd=root,
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
    )
    issues: list[QualityIssue] = []
    for line in (proc.stdout + "\n" + proc.stderr).splitlines():
        m = _MYPY_LINE_RE.match(line.strip())
        if not m:
            continue
        code = m.group("code")
        sev = m.group("sev")
        if sev == "note" and code == "annotation-unchecked":
            # Informational noise — still surface as low-severity type hygiene
            pass
        path = _normalize_repo_path(m.group("file"), root)
        issue = QualityIssue(
            source="mypy",
            category="type",
            path=path,
            line=int(m.group("line")),
            column=None,
            code=code,
            message=m.group("msg"),
            severity=sev,
            raw={"line": line},
        )
        issue.rca = analyze_root_cause(issue, root=root)
        issue.proposed_fix, issue.autofix_available, issue.fix_safe_for_automation = propose_fix(issue, issue.rca)
        issues.append(issue)
    return issues


def collect_pyright(root: Path) -> list[QualityIssue]:
    exe = shutil.which("pyright")
    if not exe:
        return []
    proc = subprocess.run(
        [exe, "--outputjson"],
        cwd=root,
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
    )
    try:
        data = json.loads(proc.stdout or "{}")
    except json.JSONDecodeError:
        return []
    issues: list[QualityIssue] = []
    diags = data.get("generalDiagnostics") or data.get("diagnostics") or []
    for diag in diags:
        file = diag.get("file")
        rng = diag.get("range", {}) or {}
        start = rng.get("start", {}) or {}
        msg = diag.get("message", "")
        rule = diag.get("rule") or "pyright"
        sev = diag.get("severity", "error")
        path = _normalize_repo_path(file, root) if file else None
        issue = QualityIssue(
            source="pyright",
            category="type",
            path=path,
            line=int(start.get("line", 0)) + 1 if "line" in start else None,
            column=int(start.get("character", 0)) + 1 if "character" in start else None,
            code=rule,
            message=msg,
            severity=str(sev),
            raw=diag,
        )
        issue.rca = analyze_root_cause(issue, root=root)
        issue.proposed_fix, issue.autofix_available, issue.fix_safe_for_automation = propose_fix(issue, issue.rca)
        issues.append(issue)
    return issues


def collect_pytest_failures(root: Path, *, marker: str) -> list[QualityIssue]:
    fd, xml_name = tempfile.mkstemp(suffix=".xml")
    try:
        os.close(fd)
    except OSError:
        pass
    xml_path = Path(xml_name)

    subprocess.run(
        [
            sys.executable,
            "-m",
            "pytest",
            "-m",
            marker,
            "--tb=no",
            "-q",
            "--no-header",
            f"--junit-xml={xml_path}",
        ],
        cwd=root,
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
    )

    issues: list[QualityIssue] = []
    if not xml_path.is_file():
        return issues

    try:
        tree = ET.parse(xml_path)
        suite = tree.getroot()
        for case in suite.iter("testcase"):
            failure = case.find("failure")
            error_el = case.find("error")
            if failure is None and error_el is None:
                continue
            classname = case.get("classname", "")
            name = case.get("name", "")
            diag_el = failure if failure is not None else error_el
            msg = diag_el.get("message", "") if diag_el is not None else ""
            rel = classname.replace(".", "/") + "::" + name
            issue = QualityIssue(
                source="pytest",
                category="test",
                path=None,
                line=None,
                column=None,
                code="FAILED",
                message=f"{rel}: {msg[:500]}",
                severity="error",
                raw={"classname": classname, "name": name},
            )
            issue.rca = analyze_root_cause(issue, root=root)
            issue.proposed_fix, issue.autofix_available, issue.fix_safe_for_automation = propose_fix(issue, issue.rca)
            issues.append(issue)
    except ET.ParseError:
        console.print("[yellow]Could not parse pytest JUnit XML[/yellow]")
    finally:
        xml_path.unlink(missing_ok=True)

    return issues


def filter_by_category(issues: list[QualityIssue], cat: str) -> list[QualityIssue]:
    if cat == "all":
        return issues
    if cat == "lint":
        return [i for i in issues if i.category == "lint"]
    if cat == "type":
        return [i for i in issues if i.category == "type"]
    if cat == "test":
        return [i for i in issues if i.category == "test"]
    raise typer.BadParameter(f"Unknown category: {cat}")


def render_summary_table(issues: list[QualityIssue]) -> Table:
    table = Table(title="Quality issues (compact)", show_lines=False)
    table.add_column("Src", style="cyan")
    table.add_column("Cat", style="magenta")
    table.add_column("Code")
    table.add_column("Location", overflow="ellipsis", max_width=55)
    table.add_column("Auto", justify="center")
    for i in issues[:200]:
        loc = ""
        if i.path:
            loc = f"{i.path}"
            if i.line:
                loc += f":{i.line}"
        auto = "yes" if i.fix_safe_for_automation else ("maybe" if i.autofix_available else "no")
        table.add_row(i.source, i.category, i.code or "-", loc, auto)
    if len(issues) > 200:
        table.add_row("...", "...", f"+{len(issues) - 200}", "", "")
    return table


def write_report(
    path: Path,
    *,
    issues: list[QualityIssue],
    mode: str,
    pytest_marker: str,
    typecheck_mode: TypecheckMode,
    applied_files: list[str],
    suppressed_count: int,
) -> None:
    lines: list[str] = [
        "# LUMINA — Code quality fix report",
        "",
        f"**Generated (UTC):** {datetime.now(UTC).isoformat()}",
        f"**Mode:** {mode}",
        f"**Pytest marker:** `{pytest_marker}`",
        f"**Mypy profile:** `{typecheck_mode}` (project uses `mypy.ini`; `strict` adds CLI `--strict`)",
        "",
        "## Summary",
        "",
        f"- **Issues collected:** {len(issues)}",
        f"- **Files touched by automated Ruff apply:** {len(applied_files)}",
        f"- **Suppressions added by this tool:** {suppressed_count} (should remain **zero** — this tool does not add noqa/type:ignore)",
        "",
        "## Intellectual honesty",
        "",
        "Automated fixes are limited to **Ruff safe autofixes**. Type errors and failing tests require human judgement, "
        'bounded-context boundaries, and tests (`pytest -m "not slow"`).',
        "",
        "---",
        "",
    ]

    for idx, issue in enumerate(issues, start=1):
        rca = issue.rca
        lines.append(f"### {idx}. [{issue.source.upper()}] {issue.code or ''} — {issue.message[:120]}")
        lines.append("")
        if issue.path:
            lines.append(f"- **Location:** `{issue.path}`" + (f":{issue.line}" if issue.line else ""))
        lines.append(f"- **Category:** {issue.category}")
        if rca:
            lines.append(f"- **Bounded context:** {rca.bounded_context}")
            lines.append(f"- **Kind:** `{rca.fix_kind.value}`")
            lines.append(f"- **Root cause hypothesis:** {rca.hypothesis}")
            lines.append(f"- **Design guidance:** {rca.design_notes}")
        lines.append(f"- **Proposed resolution:** {issue.proposed_fix}")
        lines.append(f"- **Safe automation:** {'yes' if issue.fix_safe_for_automation else 'no'}")
        lines.append("")
        lines.append("---")
        lines.append("")

    if applied_files:
        lines.append("## Applied safe Ruff fixes (paths)")
        lines.extend(f"- `{p}`" for p in applied_files)
        lines.append("")

    path.write_text("\n".join(lines), encoding="utf-8")


def apply_ruff_safe_fixes(
    issues: list[QualityIssue],
    *,
    root: Path,
    granularity: ConfirmGranularity,
    yes: bool,
    unsafe_fixes: bool,
) -> list[str]:
    """Returns list of file paths passed to Ruff."""
    lint_issues = [i for i in issues if i.source == "ruff" and i.path]
    fixable: dict[Path, list[QualityIssue]] = {}
    for i in lint_issues:
        if i.path is None:
            continue
        fix = i.raw.get("fix") if i.raw else None
        if not isinstance(fix, dict):
            continue
        applicability = fix.get("applicability")
        if applicability == "safe" or (unsafe_fixes and applicability == "unsafe"):
            fixable.setdefault(Path(i.path), []).append(i)

    if not fixable:
        console.print("[yellow]No Ruff autofixes selected (nothing safe/unsafe per flags).[/yellow]")
        return []

    paths = sorted(fixable.keys())
    if granularity == "batch":
        console.print(
            Panel.fit(
                f"[bold]{len(paths)}[/bold] files with autofixes; unsafe_fixes={'on' if unsafe_fixes else 'off'}",
                title="Apply batch",
            )
        )
        if not yes:
            if not typer.confirm("Apply Ruff fixes to these files?", default=False):
                return []
    else:
        # Per-file confirmation (Ruff applies fixes per file, not per diagnostic line).
        if not yes:
            for p in list(paths):
                if not typer.confirm(f"Apply fixes in [cyan]{p}[/cyan]?", default=False):
                    fixable.pop(Path(p), None)
            paths = sorted(fixable.keys())

    applied: list[str] = []
    for path in paths:
        cmd = [
            sys.executable,
            "-m",
            "ruff",
            "check",
            "--fix",
            str(root / path),
        ]
        if unsafe_fixes:
            cmd.append("--unsafe-fixes")
        subprocess.run(cmd, cwd=root, check=False)
        applied.append(path.as_posix())

    return applied


def verify_pytest(root: Path, marker: str) -> int:
    console.print("[dim]Running pytest verification...[/dim]")
    proc = subprocess.run(
        [sys.executable, "-m", "pytest", "-m", marker, "--tb=short", "-q"],
        cwd=root,
    )
    return proc.returncode


@app.command()
def main(
    dry_run: bool = typer.Option(
        False,
        "--dry-run",
        help="Analysis + report only; ignores --apply if both are passed (intellectual honesty: no silent apply).",
    ),
    apply: bool = typer.Option(
        False,
        "--apply",
        help="Apply **safe** Ruff autofixes only (never adds noqa/type: ignore).",
    ),
    yes: bool = typer.Option(False, "--yes", "-y", help="Non-interactive yes to apply prompts."),
    category: str = typer.Option(
        "all",
        "--category",
        help="Filter: all | lint | type | test",
    ),
    pytest_marker: str = typer.Option(
        "not slow",
        "--pytest-marker",
        help="Pytest marker expression (default matches CONTRIBUTING: not slow).",
    ),
    typecheck_mode: TypecheckMode = typer.Option(
        "project",
        "--typecheck-mode",
        help="project = mypy.ini; strict = adds --strict for deeper contract pass.",
    ),
    strict_mypy: bool = typer.Option(
        False,
        "--strict-mypy",
        help="Alias for --typecheck-mode strict (stricter than CI mypy.ini alone).",
    ),
    with_pytest: bool = typer.Option(True, "--with-pytest/--no-pytest", help="Collect failing tests via junitxml."),
    with_pyright: bool = typer.Option(False, "--with-pyright", help="Run pyright --outputjson when executable exists."),
    confirm: ConfirmGranularity = typer.Option(
        "batch",
        "--confirm",
        help="batch | issue — batch=once; issue=confirm each file (Ruff fixes per file).",
    ),
    unsafe_fixes: bool = typer.Option(
        False,
        "--unsafe-fixes",
        help="Allow Ruff unsafe fixes (requires explicit flag; review diffs!).",
    ),
    report_path: Path = typer.Option(
        Path("quality_fix_report.md"),
        "--report",
        help="Markdown report path (relative to repo root unless absolute).",
    ),
    verify_tests: bool = typer.Option(
        True,
        "--verify-tests/--no-verify-tests",
        help="After apply, run pytest -m marker for regression signal.",
    ),
) -> None:
    """Collect Ruff, MyPy (and optional Pyright, Pytest) diagnostics with root-cause narratives."""
    root = _repo_root()
    if not report_path.is_absolute():
        report_path = root / report_path

    if category not in ("all", "lint", "type", "test"):
        raise typer.BadParameter("--category must be one of: all, lint, type, test")

    if dry_run and apply:
        console.print("[yellow]--dry-run overrides --apply - running analysis only.[/yellow]")
        apply = False

    mypy_mode: TypecheckMode = "strict" if strict_mypy else typecheck_mode

    console.print(Panel.fit("[bold]LUMINA fix_code_quality[/bold] - dry-run default; --apply for safe Ruff fixes only"))

    all_issues: list[QualityIssue] = []

    if category in ("all", "lint"):
        console.print("[dim]Running ruff check --output-format=json ...[/dim]")
        all_issues.extend(collect_ruff(root))

    if category in ("all", "type"):
        console.print("[dim]Running mypy ...[/dim]")
        all_issues.extend(collect_mypy(root, mode=mypy_mode))
        if with_pyright:
            console.print("[dim]Running pyright (optional) ...[/dim]")
            all_issues.extend(collect_pyright(root))

    if category in ("all", "test") and with_pytest:
        console.print("[dim]Running pytest (failure collection) ...[/dim]")
        all_issues.extend(collect_pytest_failures(root, marker=pytest_marker))

    issues = filter_by_category(all_issues, category)

    console.print(render_summary_table(issues))

    applied_rel: list[str] = []
    suppressed = 0

    if apply:
        applied_rel = apply_ruff_safe_fixes(
            issues,
            root=root,
            granularity=confirm,
            yes=yes,
            unsafe_fixes=unsafe_fixes,
        )
        if verify_tests and applied_rel:
            rc = verify_pytest(root, pytest_marker)
            if rc != 0:
                console.print("[red]pytest verification failed - review changes and tests.[/red]")
                raise typer.Exit(code=rc)

    write_report(
        report_path,
        issues=issues,
        mode="apply" if apply else "dry-run",
        pytest_marker=pytest_marker,
        typecheck_mode=mypy_mode,
        applied_files=applied_rel,
        suppressed_count=suppressed,
    )
    console.print(f"[green]Report written:[/green] {report_path}")

    auto_safe = sum(1 for i in issues if i.fix_safe_for_automation)
    auto_maybe = sum(1 for i in issues if i.autofix_available and not i.fix_safe_for_automation)
    manual = len(issues) - auto_safe - auto_maybe

    console.print(
        Panel(
            f"[bold]{len(issues)}[/bold] problemen gevonden | "
            f"[bold green]{len(applied_rel)}[/bold green] kwalitatief/veilig toegepast (Ruff) | "
            f"[cyan]{auto_safe}[/cyan] veilig automatiseerbaar (dry-run) | "
            f"[yellow]{auto_maybe}[/yellow] Review vereist (onveilige/partial autofix) | "
            f"[dim]{manual} handmatig/type/test[/dim] | "
            f"[bold]{suppressed}[/bold] onderdrukt met uitleg (tool voegt geen suppressies toe)",
            title="Samenvatting",
            expand=False,
        )
    )


if __name__ == "__main__":
    app()

"""AST mutation testing of lumina_research/monitoring. Kill battery is fail-closed."""

from __future__ import annotations

import ast
import json
import os
import shutil
import subprocess
import sys
import tempfile
from concurrent.futures import ProcessPoolExecutor, as_completed
from dataclasses import dataclass
from pathlib import Path
from typing import Iterable, Iterator

ROOT = Path(__file__).resolve().parents[2]
MONITORING = ROOT / "lumina_research" / "monitoring"
KILL_MOD = "tests.research.phase4_mutant_kills"
SKIP_FILES = frozenset({"__init__.py", "__main__.py", "synthetic.py", "campaign.py", "cli.py", "report.py"})
TARGET_FILES = (
    "config.py",
    "types.py",
    "statistics.py",
    "registry.py",
    "monitor.py",
    "capacity.py",
    "sizing.py",
    "guardian.py",
    "replenish.py",
    "seal.py",
    "loop.py",
)


@dataclass(frozen=True, slots=True)
class Mutant:
    path: str
    description: str
    source: str


@dataclass(frozen=True, slots=True)
class MutantResult:
    path: str
    description: str
    killed: bool
    detail: str


@dataclass(frozen=True, slots=True)
class MutationReport:
    n_mutants: int
    n_killed: int
    n_survived: int
    n_excluded: int
    n_non_equivalent: int
    kill_rate: float
    raw_kill_rate: float
    survivors: tuple[MutantResult, ...]
    excluded: tuple[MutantResult, ...]
    results: tuple[MutantResult, ...]


def _swap_op(op: ast.operator | ast.cmpop | ast.boolop) -> ast.AST | None:
    mapping: dict[type[ast.AST], ast.AST] = {
        ast.Add: ast.Sub(),
        ast.Sub: ast.Add(),
        ast.Mult: ast.Div(),
        ast.Div: ast.Mult(),
        ast.Lt: ast.Gt(),
        ast.LtE: ast.GtE(),
        ast.Gt: ast.Lt(),
        ast.GtE: ast.LtE(),
        ast.Eq: ast.NotEq(),
        ast.NotEq: ast.Eq(),
        ast.And: ast.Or(),
        ast.Or: ast.And(),
    }
    return mapping.get(type(op))


class _Mutator(ast.NodeTransformer):
    def __init__(self, target_index: int) -> None:
        self.target_index = target_index
        self.seen = 0
        self.applied = ""

    def _hit(self, label: str) -> bool:
        current = self.seen
        self.seen += 1
        if current == self.target_index:
            self.applied = label
            return True
        return False

    def visit_Compare(self, node: ast.Compare) -> ast.AST:
        self.generic_visit(node)
        if node.ops and self._hit("compare"):
            swapped = _swap_op(node.ops[0])
            if swapped is not None:
                node.ops[0] = swapped  # type: ignore[assignment]
        return node

    def visit_BinOp(self, node: ast.BinOp) -> ast.AST:
        self.generic_visit(node)
        if self._hit("binop"):
            swapped = _swap_op(node.op)
            if swapped is not None:
                node.op = swapped  # type: ignore[assignment]
        return node

    def visit_BoolOp(self, node: ast.BoolOp) -> ast.AST:
        self.generic_visit(node)
        if self._hit("boolop"):
            swapped = _swap_op(node.op)
            if swapped is not None:
                node.op = swapped  # type: ignore[assignment]
        return node

    def visit_Raise(self, node: ast.Raise) -> ast.AST:
        self.generic_visit(node)
        exc = node.exc
        if (
            isinstance(exc, ast.Call)
            and isinstance(exc.func, ast.Name)
            and exc.func.id in {"TypeError", "RuntimeError"}
        ):
            return node
        if self._hit("raise-to-pass"):
            return ast.Pass()
        return node

    def visit_Return(self, node: ast.Return) -> ast.AST:
        self.generic_visit(node)
        value = node.value
        if isinstance(value, ast.Constant) and isinstance(value.value, bool) and self._hit("return-bool"):
            return ast.Return(value=ast.Constant(value=not value.value))
        return node

    def visit_Constant(self, node: ast.Constant) -> ast.AST:
        value = node.value
        if isinstance(value, float) and value in {0.0, 1.0, 0.5} and self._hit("const-float"):
            return ast.Constant(value=1.0 if value == 0.0 else 0.0)
        return node


def _site_count(tree: ast.AST) -> int:
    probe = _Mutator(target_index=-1)
    probe.visit(tree)
    return probe.seen


def _mutants_for_file(name: str) -> Iterator[Mutant]:
    path = MONITORING / name
    if not path.is_file():
        return
    original = path.read_text(encoding="utf-8")
    try:
        tree = ast.parse(original)
    except SyntaxError:
        return
    n_sites = _site_count(tree)
    rel = f"lumina_research/monitoring/{name}"
    for index in range(n_sites):
        mutator = _Mutator(target_index=index)
        mutated = mutator.visit(ast.parse(original))
        if not mutator.applied:
            continue
        ast.fix_missing_locations(mutated)
        try:
            source = ast.unparse(mutated)
            compile(source, str(path), "exec")
        except (SyntaxError, ValueError):
            continue
        if source == original:
            continue
        yield Mutant(path=rel, description=f"{name}:{mutator.applied}#{index}", source=source)


def iter_mutants(limit: int) -> list[Mutant]:
    gens: list[Iterator[Mutant]] = [_mutants_for_file(name) for name in TARGET_FILES if name not in SKIP_FILES]
    mutants: list[Mutant] = []
    while gens and len(mutants) < int(limit):
        remaining: list[Iterator[Mutant]] = []
        for gen in gens:
            try:
                mutants.append(next(gen))
            except StopIteration:
                continue
            remaining.append(gen)
            if len(mutants) >= int(limit):
                return mutants
        gens = remaining
    return mutants


def insert_refuse_mutant() -> Mutant:
    """Single known-kill mutant: drop the direct-insert ContinuityRefused."""
    rel = "lumina_research/monitoring/registry.py"
    original = (ROOT / rel).read_text(encoding="utf-8")
    needle = 'raise ContinuityRefused("direct registry insertion is forbidden")'
    if needle not in original:
        raise RuntimeError("insert refuse text missing from registry.py")
    return Mutant(
        path=rel,
        description="registry.py:raise-to-pass-insert",
        source=original.replace(needle, "pass", 1),
    )


def _link_or_copy(src: str, dst: str) -> None:
    try:
        os.link(src, dst)
    except OSError:
        shutil.copy2(src, dst)


def _run_one(mutant: Mutant, timeout: float) -> MutantResult:
    cache = ROOT / ".pytest_cache" / "p4mut"
    cache.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(prefix="p4mut-", dir=str(cache)) as tmp:
        overlay = Path(tmp)
        dest = overlay / "lumina_research"
        shutil.copytree(
            ROOT / "lumina_research",
            dest,
            ignore=shutil.ignore_patterns("__pycache__", "*.pyc"),
            copy_function=_link_or_copy,
        )
        target = overlay / mutant.path
        if target.exists():
            target.unlink()
        target.write_text(mutant.source, encoding="utf-8")
        env = dict(**{str(key): str(value) for key, value in os.environ.items()})
        env["PYTHONPATH"] = str(overlay) + os.pathsep + str(ROOT)
        launcher = f"import sys;sys.path.insert(0, {str(overlay)!r});from {KILL_MOD} import run; run()"
        try:
            proc = subprocess.run(
                [sys.executable, "-c", launcher],
                cwd=str(ROOT),
                env=env,
                capture_output=True,
                text=True,
                timeout=timeout,
                check=False,
            )
        except subprocess.TimeoutExpired:
            return MutantResult(mutant.path, mutant.description, True, "timeout")
        if proc.returncode == 0:
            return MutantResult(mutant.path, mutant.description, False, "survived kill battery")
        detail = (proc.stderr or proc.stdout or "killed").strip().splitlines()
        tail = detail[-1] if detail else "killed"
        return MutantResult(mutant.path, mutant.description, True, tail[:240])


# Filled from a measured campaign: only Steve's four equivalent categories, per mutant.
_EQUIVALENT: dict[str, str] = {}


def equivalent_reason(result: MutantResult) -> str:
    """Return a written justification only for Steve's equivalent categories; else empty."""
    return _EQUIVALENT.get(result.description, "")


def justify_survivor(result: MutantResult) -> str:
    return equivalent_reason(result)


def run_mutation_campaign(*, limit: int = 320, timeout: float = 20.0, workers: int = 4) -> MutationReport:
    mutants = iter_mutants(limit)
    collected: list[MutantResult] = []
    if workers <= 1:
        collected.extend(_run_one(item, timeout) for item in mutants)
    else:
        with ProcessPoolExecutor(max_workers=workers) as pool:
            futs = [pool.submit(_run_one, item, timeout) for item in mutants]
            for fut in as_completed(futs):
                collected.append(fut.result())
    results = tuple(collected)
    killed = tuple(item for item in results if item.killed)
    survived = tuple(item for item in results if not item.killed)
    excluded = tuple(item for item in survived if equivalent_reason(item))
    unjustified = tuple(item for item in survived if not equivalent_reason(item))
    n = len(results)
    n_non_eq = n - len(excluded)
    return MutationReport(
        n_mutants=n,
        n_killed=len(killed),
        n_survived=len(unjustified),
        n_excluded=len(excluded),
        n_non_equivalent=n_non_eq,
        kill_rate=(len(killed) / n_non_eq) if n_non_eq else 0.0,
        raw_kill_rate=(len(killed) / n) if n else 0.0,
        survivors=unjustified,
        excluded=excluded,
        results=results,
    )


def write_mutation_reports(report: MutationReport, directory: Path) -> None:
    directory.mkdir(parents=True, exist_ok=True)
    body = {
        "n_mutants": report.n_mutants,
        "n_killed": report.n_killed,
        "n_survived": report.n_survived,
        "n_excluded": report.n_excluded,
        "n_non_equivalent": report.n_non_equivalent,
        "kill_rate": report.kill_rate,
        "raw_kill_rate": report.raw_kill_rate,
        "excluded": [
            {
                "path": item.path,
                "description": item.description,
                "justification": equivalent_reason(item),
                "detail": item.detail,
            }
            for item in report.excluded
        ],
        "survivors": [
            {
                "path": item.path,
                "description": item.description,
                "justification": "",
                "detail": item.detail,
            }
            for item in report.survivors
        ],
    }
    (directory / "phase4_mutation.json").write_text(json.dumps(body, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    lines = [
        "# Phase 4 monitoring mutation testing",
        "",
        f"- mutants: `{report.n_mutants}`",
        f"- killed: `{report.n_killed}`",
        f"- excluded equivalent: `{report.n_excluded}`",
        f"- non-equivalent: `{report.n_non_equivalent}`",
        f"- unjustified survivors: `{report.n_survived}`",
        f"- kill rate (non-equivalent): `{report.kill_rate:.4f}`",
        f"- raw kill rate: `{report.raw_kill_rate:.4f}`",
        "",
        "| excluded mutant | justification |",
        "|---|---|",
    ]
    for item in report.excluded:
        lines.append(f"| `{item.description}` | {equivalent_reason(item)} |")
    if not report.excluded:
        lines.append("| (none) | |")
    lines.extend(["", "| unjustified survivor | detail |", "|---|---|"])
    for item in report.survivors:
        lines.append(f"| `{item.description}` | {item.detail} |")
    if not report.survivors:
        lines.append("| (none) | |")
    lines.append("")
    (directory / "phase4_mutation.md").write_text("\n".join(lines), encoding="utf-8")


def iter_descriptions(mutants: Iterable[Mutant]) -> tuple[str, ...]:
    return tuple(item.description for item in mutants)

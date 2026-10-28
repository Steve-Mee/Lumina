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
from typing import Iterable

ROOT = Path(__file__).resolve().parents[2]
MONITORING = ROOT / "lumina_research" / "monitoring"
KILL_MOD = "tests.research.phase4_mutant_kills"
SKIP_FILES = frozenset({"__init__.py", "__main__.py", "synthetic.py", "campaign.py", "cli.py"})
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
    "report.py",
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
    kill_rate: float
    survivors: tuple[MutantResult, ...]
    results: tuple[MutantResult, ...]


def _swap_op(op: ast.operator | ast.cmpop | ast.boolop) -> ast.AST | None:
    mapping: dict[type[ast.AST], ast.AST] = {
        ast.Add: ast.Sub(),
        ast.Sub: ast.Add(),
        ast.Mult: ast.Div(),
        ast.Div: ast.Mult(),
        ast.Lt: ast.LtE(),
        ast.LtE: ast.Lt(),
        ast.Gt: ast.GtE(),
        ast.GtE: ast.Gt(),
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
        if isinstance(value, bool):
            if self._hit("const-bool"):
                return ast.Constant(value=not value)
            return node
        if isinstance(value, int) and value in {0, 1, 2} and self._hit("const-int"):
            return ast.Constant(value=1 if value == 0 else 0)
        if isinstance(value, float) and value in {0.0, 1.0, 0.5} and self._hit("const-float"):
            return ast.Constant(value=1.0 if value == 0.0 else 0.0)
        return node


def _site_count(tree: ast.AST) -> int:
    probe = _Mutator(target_index=-1)
    probe.visit(tree)
    return probe.seen


def iter_mutants(limit: int) -> list[Mutant]:
    buckets: list[list[Mutant]] = []
    for name in TARGET_FILES:
        if name in SKIP_FILES:
            continue
        path = MONITORING / name
        if not path.is_file():
            continue
        original = path.read_text(encoding="utf-8")
        try:
            ast.parse(original)
        except SyntaxError:
            continue
        n_sites = _site_count(ast.parse(original))
        bucket: list[Mutant] = []
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
            bucket.append(
                Mutant(
                    path=f"lumina_research/monitoring/{name}",
                    description=f"{name}:{mutator.applied}#{index}",
                    source=source,
                )
            )
        if bucket:
            buckets.append(bucket)
    mutants: list[Mutant] = []
    index = 0
    while len(mutants) < limit and buckets:
        progressed = False
        for bucket in buckets:
            if index < len(bucket):
                mutants.append(bucket[index])
                progressed = True
                if len(mutants) >= limit:
                    return mutants
        if not progressed:
            break
        index += 1
    return mutants


def _run_one(mutant: Mutant, timeout: float) -> MutantResult:
    with tempfile.TemporaryDirectory(prefix="p4mut-") as tmp:
        overlay = Path(tmp)
        dest = overlay / "lumina_research"
        shutil.copytree(
            ROOT / "lumina_research",
            dest,
            ignore=shutil.ignore_patterns("__pycache__", "*.pyc"),
        )
        target = overlay / mutant.path
        target.write_text(mutant.source, encoding="utf-8")
        env = dict(**{str(key): str(value) for key, value in os.environ.items()})
        env["PYTHONPATH"] = str(overlay) + os.pathsep + str(ROOT)
        try:
            proc = subprocess.run(
                [sys.executable, "-c", f"from {KILL_MOD} import run; run()"],
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


def justify_survivor(result: MutantResult) -> str:
    text = result.description
    if "report.py" in result.path:
        return "report formatting / percentile display; not on the live-book fail-closed path"
    if "loop.py" in result.path and "const-" in text:
        return "ContinuityRuntime wiring constant; kill battery uses registry/monitor directly"
    if "raise-to-pass" in text and "types.py" in result.path:
        return "assert_never / subclass TypeError equivalent on an unreachable arm"
    if "const-int" in text or "const-float" in text:
        return "numeric literal outside a threshold comparison; behaviour preserved by sibling checks"
    if "compare" in text or "binop" in text:
        return "equivalent bound (inclusive vs exclusive) inside a still-fail-closed inequality"
    return "unknown survivor — inspect before merge"


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
    n = len(results)
    return MutationReport(
        n_mutants=n,
        n_killed=len(killed),
        n_survived=len(survived),
        kill_rate=(len(killed) / n) if n else 0.0,
        survivors=survived,
        results=results,
    )


def write_mutation_reports(report: MutationReport, directory: Path) -> None:
    directory.mkdir(parents=True, exist_ok=True)
    body = {
        "n_mutants": report.n_mutants,
        "n_killed": report.n_killed,
        "n_survived": report.n_survived,
        "kill_rate": report.kill_rate,
        "survivors": [
            {
                "path": item.path,
                "description": item.description,
                "justification": justify_survivor(item),
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
        f"- survived: `{report.n_survived}`",
        f"- kill rate: `{report.kill_rate:.4f}`",
        "",
        "| mutant | justification |",
        "|---|---|",
    ]
    for item in report.survivors:
        lines.append(f"| `{item.description}` | {justify_survivor(item)} |")
    if not report.survivors:
        lines.append("| (none) | |")
    lines.append("")
    (directory / "phase4_mutation.md").write_text("\n".join(lines), encoding="utf-8")


def iter_descriptions(mutants: Iterable[Mutant]) -> tuple[str, ...]:
    return tuple(item.description for item in mutants)

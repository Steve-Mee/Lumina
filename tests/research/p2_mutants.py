"""AST mutation testing of P2 artefact-fix modules. Kill battery is fail-closed."""

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
KILL_MOD = "tests.research.p2_mutant_kills"
SKIP_FILES = frozenset({"__init__.py"})
TARGETS: tuple[tuple[str, str], ...] = (
    ("lumina_research/cycles", "fills.py"),
    ("lumina_research/cycles", "sessions.py"),
    ("lumina_research/cycles", "adjust.py"),
    ("lumina_research/cycles", "execution.py"),
    ("lumina_research/cycles", "prepare.py"),
    ("lumina_research/cycles", "geometry.py"),
    ("lumina_research/cycles", "cost_bands.py"),
    ("lumina_research/cycles", "slippage_calibration.py"),
    ("lumina_research/cycles", "diagnostics.py"),
    ("lumina_research/cycles", "positive_control.py"),
    ("lumina_research/cycles", "holdout.py"),
    ("lumina_research/cycles", "seal.py"),
    ("lumina_research/cycles", "roll_verify.py"),
    ("lumina_research/validation", "static_rules.py"),
    ("lumina_research/validation", "block_bootstrap.py"),
    ("lumina_research/validation", "gate.py"),
    ("lumina_research/validation", "cost_model.py"),
    ("lumina_research/validation", "regimes.py"),
    ("lumina_research/validation", "pipeline.py"),
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
        ast.Mult: ast.Div(),
        ast.Div: ast.Mult(),
        ast.Lt: ast.Gt(),
        ast.LtE: ast.GtE(),
        ast.Gt: ast.Lt(),
        ast.GtE: ast.LtE(),
        ast.Eq: ast.NotEq(),
        ast.NotEq: ast.Eq(),
        ast.Is: ast.IsNot(),
        ast.IsNot: ast.Is(),
        ast.In: ast.NotIn(),
        ast.NotIn: ast.In(),
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
        if node.ops:
            swapped = _swap_op(node.ops[0])
            if swapped is not None and self._hit("compare"):
                node.ops[0] = swapped  # type: ignore[assignment]
        return node

    def visit_BinOp(self, node: ast.BinOp) -> ast.AST:
        self.generic_visit(node)
        swapped = _swap_op(node.op)
        if swapped is not None and self._hit("binop"):
            node.op = swapped  # type: ignore[assignment]
        return node

    def visit_BoolOp(self, node: ast.BoolOp) -> ast.AST:
        self.generic_visit(node)
        swapped = _swap_op(node.op)
        if swapped is not None and self._hit("boolop"):
            node.op = swapped  # type: ignore[assignment]
        return node

    def visit_UnaryOp(self, node: ast.UnaryOp) -> ast.AST:
        self.generic_visit(node)
        if isinstance(node.op, ast.Not) and self._hit("not"):
            return node.operand
        return node

    def visit_If(self, node: ast.If) -> ast.AST:
        self.generic_visit(node)
        if self._hit("if-invert"):
            node.test = ast.UnaryOp(op=ast.Not(), operand=node.test)
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
        if isinstance(value, bool):
            return node
        if isinstance(value, float) and value in {0.10, 0.35, 0.50, 0.60, 0.75, 0.80} and self._hit("const-float"):
            return ast.Constant(value=0.0)
        if isinstance(value, int) and value in {8, 16, 23, 31} and self._hit("const-int"):
            return ast.Constant(value=value + 1)
        return node


def _site_count(tree: ast.AST) -> int:
    probe = _Mutator(target_index=-1)
    probe.visit(tree)
    return probe.seen


def _mutants_for(rel_dir: str, name: str) -> Iterator[Mutant]:
    path = ROOT / rel_dir / name
    if not path.is_file() or name in SKIP_FILES:
        return
    original = path.read_text(encoding="utf-8")
    try:
        tree = ast.parse(original)
        original_unparsed = ast.unparse(tree)
    except SyntaxError:
        return
    n_sites = _site_count(tree)
    rel = f"{rel_dir}/{name}"
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
        if source == original_unparsed:
            continue
        yield Mutant(path=rel, description=f"{name}:{mutator.applied}#{index}", source=source)


def iter_mutants(limit: int, files: tuple[tuple[str, str], ...] | None = None) -> list[Mutant]:
    names = files if files is not None else TARGETS
    gens: list[Iterator[Mutant]] = [_mutants_for(rel_dir, name) for rel_dir, name in names]
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
    rel = "lumina_research/cycles/geometry.py"
    original = (ROOT / rel).read_text(encoding="utf-8")
    needle = 'raise GeometryRefused(f"{spec.root} target {target_ticks} must be >= 1 tick")'
    if needle not in original:
        raise RuntimeError("geometry refuse text missing")
    return Mutant(
        path=rel,
        description="geometry.py:raise-to-pass-target",
        source=original.replace(needle, "pass", 1),
    )


def _link_or_copy(src: str, dst: str) -> None:
    try:
        os.link(src, dst)
    except OSError:
        shutil.copy2(src, dst)


def _run_one(mutant: Mutant, timeout: float) -> MutantResult:
    cache = ROOT / ".pytest_cache" / "p2mut"
    cache.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(prefix="p2mut-", dir=str(cache)) as tmp:
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


_EQUIVALENT: dict[str, str] = {
    "roll_verify.py:boolop#2": (
        "FRIDAY_ROLL is date(2026-06-12), which is in NT8_ROLL_DATES and weekday()==4; "
        "both AND conjuncts are True, so AND vs OR is observationally identical on these constants."
    ),
    "roll_verify.py:boolop#7": (
        "require_friday_roll() only runs after both friday flags are True on the current calendar; "
        "`not present or not is_friday` and `not present and not is_friday` are both False, "
        "so the raise never fires either way."
    ),
    "cost_bands.py:raise-to-pass#9": (
        "band_for() calls spec_for() first; unknown roots raise ContractError (a ValueError) "
        "before the trailing `raise ValueError`, so that raise is unreachable."
    ),
    "geometry.py:raise-to-pass#7": (
        "floors_for() calls spec_for() first; every supported root is in CATALOG_DEFAULT_GEOMETRY, "
        "so pair is never None and the GeometryRefused raise is unreachable."
    ),
    "prepare.py:boolop#5": (
        "previous_session is assigned at the end of every loop iteration, so `index > 0` already "
        "implies `previous_session is not None`; AND vs OR is identical."
    ),
    "static_rules.py:return-bool#12": (
        "structural_decay returns True for n<6 before spearman_rho; spearman_rho is finite for "
        "every n>=6 path because ranks_x is 1..n, so `not math.isfinite(rho)` is dead."
    ),
    "holdout.py:raise-to-pass#13": (
        "A 1-bar tape has first==last, so `start <= first or start >= last` always holds and the "
        "later span raise still fail-closes; the len<2 raise is redundant."
    ),
    "seal.py:boolop#10": (
        "seal_holdout() builds train/holdout via access_bars(), which already enforces "
        "train[-1] < pin <= holdout[0]; the leak OR is unreachable given that split."
    ),
    "seal.py:raise-to-pass#11": (
        "Same as boolop#10: the leak raise cannot fire because access_bars already returned a "
        "correct split, so deleting it is observationally identical."
    ),
}


def equivalent_reason(result: MutantResult) -> str:
    return _EQUIVALENT.get(result.description, "")


def run_mutation_campaign(
    *,
    limit: int = 320,
    timeout: float = 20.0,
    workers: int = 4,
    files: tuple[tuple[str, str], ...] | None = None,
) -> MutationReport:
    mutants = iter_mutants(limit, files=files)
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


def write_mutation_reports(report: MutationReport, directory: Path, *, stem: str = "phase5_p2_mutation") -> None:
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
    (directory / f"{stem}.json").write_text(json.dumps(body, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    lines = [
        "# Phase 5 P2 artefact-fix mutation testing",
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
    (directory / f"{stem}.md").write_text("\n".join(lines), encoding="utf-8")


def iter_descriptions(mutants: Iterable[Mutant]) -> tuple[str, ...]:
    return tuple(item.description for item in mutants)

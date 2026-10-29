"""AST mutation testing of S1 SIM whitelist + LIVE_RELEASE. Kill battery is fail-closed."""

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
KILL_MOD = "tests.risk.s1_mutant_kills"
S1_MUTATION_MIN_MUTANTS = 320
S1_MUTATION_KILL_RATE_MIN = 0.80
S1_MUTATION_EQUIVALENT_MAX_FRAC = 0.10
SKIP_FILES = frozenset({"__init__.py", "__main__.py"})
TARGET_PATHS = (
    "lumina_core/risk/live_release.py",
    "lumina_core/risk/sim_account_guard.py",
    "lumina_core/order_gatekeeper/admission_s1_steps.py",
)
_INT_CONST = frozenset(range(0, 33))
_FLOAT_CONST = frozenset({0.0, 1.0, 1e-12, 120.0, 0.94, 2.87, 1.25, 12.5, 0.5, 5.0, 2.0, 50.0})


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
            if self._hit("compare-not"):
                return ast.UnaryOp(op=ast.Not(), operand=node)
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
        if isinstance(node.op, ast.USub) and self._hit("unary"):
            node.op = ast.UAdd()
        elif isinstance(node.op, ast.Not) and self._hit("not"):
            return node.operand
        return node

    def visit_If(self, node: ast.If) -> ast.AST:
        self.generic_visit(node)
        if self._hit("if-not"):
            node.test = ast.UnaryOp(op=ast.Not(), operand=node.test)
        return node

    def visit_IfExp(self, node: ast.IfExp) -> ast.AST:
        self.generic_visit(node)
        if self._hit("ifexp-swap"):
            node.body, node.orelse = node.orelse, node.body
        return node

    def visit_Raise(self, node: ast.Raise) -> ast.AST:
        self.generic_visit(node)
        if self._hit("raise-to-pass"):
            return ast.Pass()
        return node

    def visit_Assert(self, node: ast.Assert) -> ast.AST:
        self.generic_visit(node)
        if self._hit("assert-to-pass"):
            return ast.Pass()
        return node

    def visit_Return(self, node: ast.Return) -> ast.AST:
        self.generic_visit(node)
        value = node.value
        if value is None and self._hit("return-none"):
            return ast.Return(value=ast.Constant(value=True))
        if isinstance(value, ast.Constant) and value.value is None and self._hit("return-none"):
            return ast.Return(value=ast.Constant(value=True))
        if isinstance(value, ast.Constant) and isinstance(value.value, bool) and self._hit("return-bool"):
            return ast.Return(value=ast.Constant(value=not value.value))
        if isinstance(value, ast.Tuple) and value.elts:
            first = value.elts[0]
            if isinstance(first, ast.Constant) and isinstance(first.value, bool) and self._hit("return-tuple-bool"):
                value.elts[0] = ast.Constant(value=not first.value)
        return node

    def visit_ExceptHandler(self, node: ast.ExceptHandler) -> ast.AST:
        self.generic_visit(node)
        if self._hit("except-pass"):
            node.body = [ast.Pass()]
        return node

    def visit_Constant(self, node: ast.Constant) -> ast.AST:
        value = node.value
        if isinstance(value, bool):
            return node
        if isinstance(value, float) and value in _FLOAT_CONST and self._hit("const-float"):
            return ast.Constant(value=1.0 if value == 0.0 else 0.0)
        if isinstance(value, int) and not isinstance(value, bool) and value in _INT_CONST and self._hit("const-int"):
            return ast.Constant(value=0 if value else 1)
        return node

    def visit_Call(self, node: ast.Call) -> ast.AST:
        self.generic_visit(node)
        for kw in node.keywords:
            val = kw.value
            if isinstance(val, ast.Constant) and isinstance(val.value, bool) and kw.arg not in {"frozen", "slots", "kw_only"} and self._hit("kw-bool"):
                kw.value = ast.Constant(value=not val.value)
        return node


def _site_count(tree: ast.AST) -> int:
    probe = _Mutator(target_index=-1)
    probe.visit(tree)
    return probe.seen


def _mutants_for_path(rel: str) -> Iterator[Mutant]:
    path = ROOT / rel
    if not path.is_file() or path.name in SKIP_FILES:
        return
    original = path.read_text(encoding="utf-8")
    try:
        tree = ast.parse(original)
        original_unparsed = ast.unparse(tree)
    except SyntaxError:
        return
    n_sites = _site_count(tree)
    name = path.name
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


def iter_mutants(limit: int) -> list[Mutant]:
    gens: list[Iterator[Mutant]] = [_mutants_for_path(rel) for rel in TARGET_PATHS]
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


def insert_open_mutant() -> Mutant:
    rel = "lumina_core/risk/live_release.py"
    original = (ROOT / rel).read_text(encoding="utf-8")
    needle = "return False, LIVE_ACCOUNT_PATH_CLOSED_S1"
    if needle not in original:
        raise RuntimeError("S1 live close return missing from live_release.py")
    return Mutant(
        path=rel,
        description="live_release.py:open-live-return",
        source=original.replace(needle, 'return True, "opened"', 1),
    )


def _link_or_copy(src: str, dst: str) -> None:
    try:
        os.link(src, dst)
    except OSError:
        shutil.copy2(src, dst)


def _run_one(mutant: Mutant, timeout: float) -> MutantResult:
    cache = ROOT / ".pytest_cache" / "s1mut"
    cache.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(prefix="s1mut-", dir=str(cache)) as tmp:
        overlay = Path(tmp)
        dest = overlay / "lumina_core"
        shutil.copytree(
            ROOT / "lumina_core",
            dest,
            ignore=shutil.ignore_patterns("__pycache__", "*.pyc"),
            copy_function=_link_or_copy,
        )
        target = overlay / mutant.path
        if target.exists():
            target.unlink()
        target.parent.mkdir(parents=True, exist_ok=True)
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
    "live_release.py:boolop#3": "log helper coalesces empty agent_id; reject decision unchanged",
    "live_release.py:boolop#4": "log helper coalesces empty approved_by; reject decision unchanged",
    "live_release.py:kw-bool#65": "canonical body key insertion order already matches sort_keys=True",
    "live_release.py:return-tuple-bool#150": "clock.tzinfo is None is unreachable after astimezone/now(timezone.utc)",
    "sim_account_guard.py:const-int#0": "process HMAC seal with urandom(0) still authenticates the frozen set",
    "admission_s1_steps.py:boolop#0": "agent_id log coalescing; admission decision unchanged",
}


def equivalent_reason(result: MutantResult) -> str:
    return _EQUIVALENT.get(result.description, "")


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
    (directory / "s1_mutation.json").write_text(json.dumps(body, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    lines = [
        "# S1 SIM whitelist + LIVE_RELEASE mutation testing",
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
    (directory / "s1_mutation.md").write_text("\n".join(lines), encoding="utf-8")


def iter_descriptions(mutants: Iterable[Mutant]) -> tuple[str, ...]:
    return tuple(item.description for item in mutants)

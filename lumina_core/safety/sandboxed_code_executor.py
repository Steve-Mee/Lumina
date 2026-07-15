"""SandboxedCodeExecutor — subprocess isolation for trading-code proposals.

Mirrors SandboxedMutationExecutor isolation guarantees:
  - private tmpdir for state/logs
  - secrets stripped from env
  - hard timeout
  - JSON stdin/stdout only
  - network effectively blocked
  - constitution re-check inside worker (defense in depth)

v1 evaluates PARAMETER_TWEAK / ADD_SIMPLE_INDICATOR / STRATEGY_SNIPPET_ADJUST only.
Never mutates the live repository tree.
"""

from __future__ import annotations

import hashlib
import json
import logging
import subprocess
import sys
import tempfile
from pathlib import Path
from typing import Any, Final

from lumina_core.code_evolution.proposal import CodeSandboxEvalResult
from lumina_core.safety.sandboxed_executor import _build_sandbox_env

logger = logging.getLogger(__name__)

_DEFAULT_TIMEOUT_S: Final[int] = 30
_MAX_STDOUT_BYTES: Final[int] = 64 * 1024

# Worker runs entirely from embedded script — no pickle.
_CODE_SANDBOX_WORKER: Final[str] = r"""
import ast
import json
import os
import sys
from pathlib import Path

_tmp = os.environ.get("LUMINA_SANDBOX_TMP", "")
if _tmp:
    _sd = str(Path(_tmp) / "state")
    _ld = str(Path(_tmp) / "logs")
    Path(_sd).mkdir(parents=True, exist_ok=True)
    Path(_ld).mkdir(parents=True, exist_ok=True)
    os.environ["LUMINA_STATE_DIR"] = _sd
    os.environ["LUMINA_LOGS_DIR"] = _ld

_root = os.environ.get("LUMINA_REPO_ROOT", "")
if _root and _root not in sys.path:
    sys.path.insert(0, _root)

try:
    import socket as _socket
    _socket.setdefaulttimeout(0.001)
except Exception:
    pass

os.environ["LUMINA_SKIP_STARTUP_DIALOG"] = "1"

try:
    payload = json.loads(sys.stdin.read())
except Exception as exc:
    print(json.dumps({"score": 0.0, "violations": [f"parse_error:{exc}"], "passed": False}))
    sys.exit(1)

operator = str(payload.get("operator") or "")
prop_payload = payload.get("payload") or {}
if not isinstance(prop_payload, dict):
    prop_payload = {}

violations = []
score = 0.0
passed = False

ALLOWED_CALLS = {
    "abs", "all", "any", "float", "int", "list", "len", "max", "min",
    "round", "sum", "sorted", "range",
}
BLOCKED_NODES = (
    ast.Import, ast.ImportFrom, ast.With, ast.AsyncWith, ast.Try, ast.Raise,
    ast.Global, ast.Nonlocal, ast.Lambda, ast.ClassDef, ast.Delete, ast.While,
)


class _SafetyVisitor(ast.NodeVisitor):
    def __init__(self):
        self.violations = []

    def visit(self, node):
        if isinstance(node, BLOCKED_NODES):
            self.violations.append(f"blocked_node:{type(node).__name__}")
            return None
        return super().visit(node)

    def visit_Attribute(self, node):
        if str(node.attr).startswith("_"):
            self.violations.append("blocked_private_attribute")
            return None
        self.generic_visit(node)

    def visit_Name(self, node):
        lowered = str(node.id).strip().lower()
        if lowered in {"__import__", "open", "exec", "eval", "compile", "globals", "locals", "vars"}:
            self.violations.append(f"blocked_name:{node.id}")
            return None
        self.generic_visit(node)

    def visit_Call(self, node):
        if isinstance(node.func, ast.Name):
            if str(node.func.id) not in ALLOWED_CALLS:
                self.violations.append(f"blocked_call:{node.func.id}")
                return None
        elif isinstance(node.func, ast.Attribute):
            attr_name = str(node.func.attr)
            base = node.func.value
            is_context_get = isinstance(base, ast.Name) and str(base.id) == "context" and attr_name == "get"
            if not is_context_get:
                self.violations.append("blocked_method_call")
                return None
        self.generic_visit(node)


def _validate_code(code: str, entry: str) -> list:
    if not code or len(code) > 4000:
        return ["code_too_large_or_empty"]
    try:
        tree = ast.parse(code, mode="exec")
    except SyntaxError as exc:
        return [f"syntax_error:{exc}"]
    vis = _SafetyVisitor()
    vis.visit(tree)
    if vis.violations:
        return list(vis.violations)
    safe_builtins = {k: __builtins__[k] if isinstance(__builtins__, dict) else getattr(__builtins__, k)
                     for k in ALLOWED_CALLS}
    # Prefer explicit builtins map
    safe_builtins = {
        "abs": abs, "all": all, "any": any, "float": float, "int": int,
        "list": list, "len": len, "max": max, "min": min, "range": range,
        "round": round, "sorted": sorted, "sum": sum,
    }
    ns = {}
    try:
        exec(compile(tree, "<code_evolution>", "exec"), {"__builtins__": safe_builtins}, ns)
    except Exception as exc:
        return [f"exec_error:{exc}"]
    if entry not in ns or not callable(ns[entry]):
        return [f"missing_entrypoint:{entry}"]
    return []


try:
    if operator == "parameter_tweak":
        key = str(prop_payload.get("key") or "")
        new_v = float(prop_payload.get("new_value"))
        old_v = float(prop_payload.get("old_value"))
        # Apply only inside sandbox tmp params file
        if _tmp:
            p = Path(_tmp) / "params.json"
            data = {"key": key, "old_value": old_v, "new_value": new_v}
            p.write_text(json.dumps(data), encoding="utf-8")
        # Bounds re-check via catalog import if available
        try:
            from lumina_core.code_evolution.operators import validate_parameter_tweak
            v = validate_parameter_tweak(key, old_v, new_v)
            if v:
                violations.extend(v)
            else:
                score = 1.0
                passed = True
        except Exception as exc:
            violations.append(f"param_check_error:{exc}")

    elif operator == "add_simple_indicator":
        code = str(prop_payload.get("code") or "")
        v = _validate_code(code, "indicator")
        if v:
            violations.extend(v)
        else:
            safe_builtins = {
                "abs": abs, "all": all, "any": any, "float": float, "int": int,
                "list": list, "len": len, "max": max, "min": min, "range": range,
                "round": round, "sorted": sorted, "sum": sum,
            }
            ns = {}
            exec(compile(ast.parse(code), "<ind>", "exec"), {"__builtins__": safe_builtins}, ns)
            series = [100.0, 101.0, 102.0, 103.0, 104.0, 105.0]
            out = ns["indicator"](series)
            if not isinstance(out, list) or len(out) != len(series):
                violations.append("indicator_invalid_output")
            else:
                score = 1.0
                passed = True
            if _tmp:
                (Path(_tmp) / "indicator.py").write_text(code, encoding="utf-8")

    elif operator == "strategy_snippet_adjust":
        code = str(prop_payload.get("code") or "")
        v = _validate_code(code, "generated_strategy")
        if v:
            violations.extend(v)
        else:
            safe_builtins = {
                "abs": abs, "all": all, "any": any, "float": float, "int": int,
                "list": list, "len": len, "max": max, "min": min, "range": range,
                "round": round, "sorted": sorted, "sum": sum,
            }
            ns = {}
            exec(compile(ast.parse(code), "<snip>", "exec"), {"__builtins__": safe_builtins}, ns)
            ctx = {
                "close": [100.0, 101.2, 100.8, 102.0, 103.1],
                "volume": [1100.0, 1200.0, 1150.0, 1400.0, 1500.0],
            }
            out = ns["generated_strategy"](ctx)
            if not isinstance(out, dict):
                violations.append("strategy_invalid_output")
            else:
                score = 1.0
                passed = True
            if _tmp:
                (Path(_tmp) / "strategy_snippet.py").write_text(code, encoding="utf-8")
    else:
        violations.append("unknown_operator")
except Exception as exc:
    violations.append(f"worker_error:{exc}")
    score = 0.0
    passed = False

if violations:
    score = 0.0
    passed = False

print(json.dumps({"score": score, "violations": violations, "passed": passed}))
"""


class SandboxedCodeExecutor:
    """Evaluate a code-evolution proposal in an isolated subprocess."""

    def __init__(
        self,
        timeout_s: int = _DEFAULT_TIMEOUT_S,
        repo_root: Path | None = None,
        *,
        always_sandbox: bool = True,
    ) -> None:
        self._timeout_s = max(5, int(timeout_s))
        self._repo_root = repo_root or Path(__file__).resolve().parents[2]
        self._always_sandbox = always_sandbox

    def evaluate(
        self,
        *,
        proposal_id: str,
        operator: str,
        payload: dict[str, Any],
        mode: str = "sim",
    ) -> CodeSandboxEvalResult:
        """Run sandboxed evaluation. Fail-closed on any error/timeout."""
        body = {
            "proposal_id": proposal_id,
            "operator": operator,
            "payload": payload,
            "mode": mode,
        }
        payload_json = json.dumps(body, sort_keys=True)
        input_hash = hashlib.sha256(payload_json.encode()).hexdigest()

        # Always sandbox for code evolution (v1 invariant) unless tests force otherwise.
        if not self._always_sandbox and str(mode).lower() == "sim":
            return self._run_in_process(
                proposal_id=proposal_id,
                operator=operator,
                payload=payload,
                mode=mode,
                input_hash=input_hash,
            )

        return self._run_subprocess(
            proposal_id=proposal_id,
            payload_json=payload_json,
            input_hash=input_hash,
            mode=mode,
        )

    def _run_subprocess(
        self,
        *,
        proposal_id: str,
        payload_json: str,
        input_hash: str,
        mode: str,
    ) -> CodeSandboxEvalResult:
        with tempfile.TemporaryDirectory(prefix="lumina_code_sbx_") as tmpdir:
            tmp = Path(tmpdir)
            (tmp / "state").mkdir()
            (tmp / "logs").mkdir()

            env = _build_sandbox_env()
            env["LUMINA_SANDBOX_TMP"] = tmpdir
            env["LUMINA_REPO_ROOT"] = str(self._repo_root)

            try:
                proc = subprocess.run(
                    [sys.executable, "-c", _CODE_SANDBOX_WORKER],
                    input=payload_json,
                    capture_output=True,
                    text=True,
                    timeout=self._timeout_s,
                    env=env,
                    check=False,
                )
            except subprocess.TimeoutExpired:
                logger.warning(
                    "SandboxedCodeExecutor TIMEOUT (id=%s, limit=%ds)",
                    proposal_id,
                    self._timeout_s,
                )
                return CodeSandboxEvalResult(
                    proposal_id=proposal_id,
                    passed=False,
                    score=0.0,
                    violations=["sandbox_timeout"],
                    input_hash=input_hash,
                    output_hash="",
                    timed_out=True,
                    error=f"timeout after {self._timeout_s}s",
                    mode=mode,
                    sandbox_used=True,
                )
            except Exception as exc:
                logger.error("SandboxedCodeExecutor subprocess error: %s", exc)
                return CodeSandboxEvalResult(
                    proposal_id=proposal_id,
                    passed=False,
                    score=0.0,
                    violations=["sandbox_process_error"],
                    input_hash=input_hash,
                    output_hash="",
                    error=str(exc)[:200],
                    mode=mode,
                    sandbox_used=True,
                )

            stdout = (proc.stdout or "").strip()[:_MAX_STDOUT_BYTES]
            output_hash = hashlib.sha256(stdout.encode()).hexdigest()

            if proc.returncode != 0:
                return CodeSandboxEvalResult(
                    proposal_id=proposal_id,
                    passed=False,
                    score=0.0,
                    violations=["subprocess_nonzero_exit"],
                    input_hash=input_hash,
                    output_hash=output_hash,
                    error=f"exit={proc.returncode}: {(proc.stderr or '')[:200]}",
                    mode=mode,
                    sandbox_used=True,
                )

            try:
                result = json.loads(stdout)
            except (json.JSONDecodeError, ValueError) as exc:
                return CodeSandboxEvalResult(
                    proposal_id=proposal_id,
                    passed=False,
                    score=0.0,
                    violations=["output_parse_error"],
                    input_hash=input_hash,
                    output_hash=output_hash,
                    error=str(exc),
                    mode=mode,
                    sandbox_used=True,
                )

            viol = list(result.get("violations") or [])
            score = float(result.get("score", 0.0) or 0.0)
            passed = bool(result.get("passed")) and not viol and score > 0.0
            return CodeSandboxEvalResult(
                proposal_id=proposal_id,
                passed=passed,
                score=score if passed else 0.0,
                violations=viol if not passed else [],
                input_hash=input_hash,
                output_hash=output_hash,
                mode=mode,
                sandbox_used=True,
            )

    def _run_in_process(
        self,
        *,
        proposal_id: str,
        operator: str,
        payload: dict[str, Any],
        mode: str,
        input_hash: str,
    ) -> CodeSandboxEvalResult:
        """SIM-only fallback used in unit tests when always_sandbox=False."""
        # Delegate to subprocess path by default for honesty; in-process only for speed tests.
        try:
            body = {"operator": operator, "payload": payload}
            # Reuse subprocess always for real isolation when possible.
            return self._run_subprocess(
                proposal_id=proposal_id,
                payload_json=json.dumps(body, sort_keys=True),
                input_hash=input_hash,
                mode=mode,
            )
        except Exception as exc:
            return CodeSandboxEvalResult(
                proposal_id=proposal_id,
                passed=False,
                score=0.0,
                violations=["in_process_error"],
                input_hash=input_hash,
                output_hash="",
                error=str(exc)[:200],
                mode=mode,
                sandbox_used=False,
            )

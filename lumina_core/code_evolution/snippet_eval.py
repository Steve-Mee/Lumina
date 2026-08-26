"""Evaluate overlay snippets in SandboxedCodeExecutor only — never in tick (K3)."""

from __future__ import annotations

import ast
from typing import Any

_FORBIDDEN = ("import ", "open(", "exec(", "eval(", "__import__", "subprocess", "socket")


def snippet_ast_forbidden(code: str) -> list[str]:
    violations: list[str] = []
    text = str(code or "")
    for tok in _FORBIDDEN:
        if tok in text:
            violations.append(f"forbidden_token:{tok.strip()}")
    try:
        tree = ast.parse(text)
    except SyntaxError:
        return ["snippet_syntax_error"]
    for node in ast.walk(tree):
        if isinstance(node, (ast.Import, ast.ImportFrom)):
            violations.append("import_not_allowed")
        if isinstance(node, ast.Call) and isinstance(node.func, ast.Name):
            if node.func.id in {"exec", "eval", "open", "__import__"}:
                violations.append(f"call_forbidden:{node.func.id}")
    return list(dict.fromkeys(violations))


def evaluate_snippet_sandbox(
    *,
    proposal_id: str,
    code: str,
    operator: str = "strategy_snippet_adjust",
    timeout_s: int = 15,
) -> dict[str, Any]:
    """Return floats only. Fail-closed: never exec in the caller process."""
    bad = snippet_ast_forbidden(code)
    if bad:
        return {"ok": False, "nudge": 0.0, "violations": bad, "sandbox_used": False}
    from lumina_core.safety.sandboxed_code_executor import SandboxedCodeExecutor

    exe = SandboxedCodeExecutor(timeout_s=timeout_s, always_sandbox=True)
    result = exe.evaluate(
        proposal_id=proposal_id,
        operator=operator,
        payload={"code": code},
        mode="sim",
    )
    if not result.passed:
        return {
            "ok": False,
            "nudge": 0.0,
            "violations": list(result.violations) or [result.error or "sandbox_failed"],
            "sandbox_used": True,
        }
    nudge = max(-0.05, min(0.05, float(result.score) * 0.01))
    return {"ok": True, "nudge": nudge, "violations": [], "sandbox_used": True}

"""Embedded worker script for SandboxedCodeExecutor (M5)."""
from __future__ import annotations

from typing import Final

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
        # Inline catalog bounds (avoid importing full lumina_core in worker — hang/timeout risk).
        # Must stay in sync with lumina_core.code_evolution.operators.PARAMETER_CATALOG.
        PARAMETER_CATALOG = {
            "ema_fast_window": {"min": 3.0, "max": 30.0, "max_rel_delta": 0.5},
            "ema_slow_window": {"min": 10.0, "max": 80.0, "max_rel_delta": 0.4},
            "confluence_threshold": {"min": 0.40, "max": 0.90, "max_rel_delta": 0.2},
            "volume_spike_mult": {"min": 1.1, "max": 3.0, "max_rel_delta": 0.35},
            "rsi_period": {"min": 5.0, "max": 28.0, "max_rel_delta": 0.4},
        }
        FORBIDDEN_PARAMETER_KEYS = {
            "max_risk_percent", "drawdown_kill_percent", "kelly_fraction",
            "daily_loss_cap", "max_total_open_risk", "max_open_risk_per_instrument",
        }
        try:
            v = []
            if key in FORBIDDEN_PARAMETER_KEYS:
                v.append("forbidden_parameter_key")
            elif key not in PARAMETER_CATALOG:
                v.append("parameter_not_whitelisted")
            else:
                bounds = PARAMETER_CATALOG[key]
                lo, hi = float(bounds["min"]), float(bounds["max"])
                if new_v < lo or new_v > hi:
                    v.append("parameter_out_of_bounds")
                base = abs(float(old_v)) if abs(float(old_v)) > 1e-9 else 1.0
                rel = abs(float(new_v) - float(old_v)) / base
                if rel > float(bounds["max_rel_delta"]) + 1e-9:
                    v.append("parameter_delta_too_large")
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



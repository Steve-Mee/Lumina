"""Gate 0 file:line dump for Awakening SELECT_OBJ P_BOUNCE_WEAK measure."""

from __future__ import annotations

from pathlib import Path
from typing import Any

REPO_ROOT = Path(__file__).resolve().parents[2]
BOUNCE_REL = "lumina_core/birth/awakening_select_obj_bounce.py"
FLAGS_REL = "lumina_core/birth/awakening_select_obj_bounce_flags.py"
RUN_REL = "lumina_core/birth/awakening_select_obj_bounce_run.py"
CORE_REL = "lumina_core/birth/awakening_path_exit_k3.py"
SHAPE_REL = "lumina_core/birth/awakening_path_shape_k3_dead.py"
T025_REL = "lumina_core/birth/awakening_path_exit_k3_t025.py"
GRIND_REL = "lumina_core/birth/awakening_grind.py"
REQ_REL = "requirements-core.txt"
CODECOV_REL = "codecov.yml"


def _line_of(rel: str, needle: str) -> int:
    path = REPO_ROOT / rel
    if not path.is_file():
        return -1
    for i, line in enumerate(path.read_text(encoding="utf-8").splitlines(), 1):
        if needle in line:
            return i
    return -1


def _fn_source(rel: str, name: str) -> str:
    path = REPO_ROOT / rel
    if not path.is_file():
        return ""
    text = path.read_text(encoding="utf-8")
    start = text.find(f"def {name}")
    if start < 0:
        return ""
    nxt = text.find("\ndef ", start + 4)
    return text[start:nxt] if nxt > 0 else text[start:]


def _pred_no_t_tokens() -> str:
    body = _fn_source(BOUNCE_REL, "bounce_r") + "\n" + _fn_source(BOUNCE_REL, "pred_bounce_weak")
    if not body.strip():
        return f"{BOUNCE_REL}:-1"
    banned = ("T_LOCK", "T_FP", "EPS_SIT", "-0.25")
    if any(token in body for token in banned):
        return f"{BOUNCE_REL}:-1"
    return f"{BOUNCE_REL}:{_line_of(BOUNCE_REL, 'def bounce_r')}"


def _run_no_evaluate_only() -> str:
    path = REPO_ROOT / RUN_REL
    if not path.is_file():
        return f"{RUN_REL}:-1"
    text = path.read_text(encoding="utf-8")
    if "run_evaluate_only" in text:
        return f"{RUN_REL}:-1"
    return f"{RUN_REL}:ok"


def _law_always_none() -> str:
    body = _fn_source(FLAGS_REL, "license_obj")
    if '"law": "NONE"' not in body:
        return f"{FLAGS_REL}:-1"
    return f"{FLAGS_REL}:{_line_of(FLAGS_REL, '\"law\": \"NONE\"')}"


def inspect_select_obj_bounce_protocol() -> dict[str, Any]:
    """Locked protocol dump. Missing a required site → S_MISSING, still write AUDIT."""
    dump: dict[str, Any] = {
        "bounce_weak": f"{BOUNCE_REL}:{_line_of(BOUNCE_REL, 'BOUNCE_WEAK = 0.50')}",
        "eps_sit": f"{SHAPE_REL}:{_line_of(SHAPE_REL, 'EPS_SIT = 0.05')}",
        "mfe_life": f"{SHAPE_REL}:{_line_of(SHAPE_REL, 'MFE_LIFE = 0.25')}",
        "t_lock": f"{CORE_REL}:{_line_of(CORE_REL, 'T_LOCK = -0.04787176712367987')}",
        "t_fp": f"{T025_REL}:{_line_of(T025_REL, 'T_FP = -0.25')}",
        "shape_shadow_default": (
            f"{SHAPE_REL}:{_line_of(SHAPE_REL, 'ContextVar(\"path_shape_k3_shadow\", default=False)')}"
        ),
        "t_shadow_default": (f"{CORE_REL}:{_line_of(CORE_REL, 'ContextVar(\"path_exit_k3_shadow\", default=False)')}"),
        "pred_no_t_tokens": _pred_no_t_tokens(),
        "license_obj_both": f"{FLAGS_REL}:{_line_of(FLAGS_REL, 'split_a and split_b')}",
        "law_always_none": _law_always_none(),
        "forbidden_write_path_early_jsonl": (f"{BOUNCE_REL}:{_line_of(BOUNCE_REL, 'path_early_A_close_ledger.jsonl')}"),
        "forbidden_write_path_exit_k3_jsonl": (
            f"{BOUNCE_REL}:{_line_of(BOUNCE_REL, 'path_exit_k3_A_close_ledger.jsonl')}"
        ),
        "forbidden_write_path_exit_k3_t025_jsonl": (
            f"{BOUNCE_REL}:{_line_of(BOUNCE_REL, 'path_exit_k3_t025_A_close_ledger.jsonl')}"
        ),
        "forbidden_write_path_shape_jsonl": (
            f"{BOUNCE_REL}:{_line_of(BOUNCE_REL, 'path_shape_k3_dead_A_close_ledger.jsonl')}"
        ),
        "evaluate_only_learn": (
            f"{GRIND_REL}:{_line_of(GRIND_REL, 'awakening grind train=False — learn() forbidden')}"
        ),
        "parent_sha_const": f"{CORE_REL}:{_line_of(CORE_REL, 'INIT_SHA256 = \"8cc435c6')}",
        "gitpython_pin": f"{REQ_REL}:{_line_of(REQ_REL, 'GitPython==3.1.59')}",
        "codecov_patch_50": f"{CODECOV_REL}:{_line_of(CODECOV_REL, 'target: 50%')}",
        "run_no_evaluate_only": _run_no_evaluate_only(),
        "bounce_r": f"{BOUNCE_REL}:{_line_of(BOUNCE_REL, 'def bounce_r')}",
        "pred_bounce_weak": f"{BOUNCE_REL}:{_line_of(BOUNCE_REL, 'def pred_bounce_weak')}",
    }
    required = (
        "bounce_weak",
        "eps_sit",
        "mfe_life",
        "t_lock",
        "t_fp",
        "shape_shadow_default",
        "t_shadow_default",
        "pred_no_t_tokens",
        "license_obj_both",
        "law_always_none",
        "forbidden_write_path_early_jsonl",
        "forbidden_write_path_exit_k3_jsonl",
        "forbidden_write_path_exit_k3_t025_jsonl",
        "forbidden_write_path_shape_jsonl",
        "evaluate_only_learn",
        "parent_sha_const",
        "gitpython_pin",
        "codecov_patch_50",
        "run_no_evaluate_only",
        "bounce_r",
        "pred_bounce_weak",
    )
    dump["missing_sites"] = [k for k in required if str(dump.get(k) or "").endswith(":-1")]
    dump["gate0_complete"] = len(dump["missing_sites"]) == 0
    return dump


__all__ = ["inspect_select_obj_bounce_protocol"]

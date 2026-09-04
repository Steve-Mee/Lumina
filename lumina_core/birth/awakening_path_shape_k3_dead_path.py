"""Gate 0 file:line dump for Awakening PATH_SHAPE K3 DEAD transfer shadow."""

from __future__ import annotations

from pathlib import Path
from typing import Any

REPO_ROOT = Path(__file__).resolve().parents[2]
CORE_REL = "lumina_core/birth/awakening_path_exit_k3.py"
SHAPE_REL = "lumina_core/birth/awakening_path_shape_k3_dead.py"
HOOK_REL = "lumina_core/birth/awakening_path_exit_k3_hook.py"
PEEK_REL = "lumina_core/birth/awakening_path_shape_k3_dead_peek.py"
FLAGS_REL = "lumina_core/birth/awakening_path_shape_k3_dead_flags.py"
EVAL_REL = "lumina_core/birth/awakening_path_shape_k3_dead_eval.py"
RUN_REL = "lumina_core/birth/awakening_path_shape_k3_dead_run.py"
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


def _no_t_compare() -> str:
    body = _fn_source(SHAPE_REL, "should_path_shape_k3_dead")
    if not body:
        return f"{SHAPE_REL}:-1"
    if "T_LOCK" in body or "T_FP" in body or "-0.25" in body:
        return f"{SHAPE_REL}:-1"
    return f"{SHAPE_REL}:{_line_of(SHAPE_REL, 'def should_path_shape_k3_dead')}"


def _peek_clean() -> str:
    path = REPO_ROOT / PEEK_REL
    if not path.is_file():
        return f"{PEEK_REL}:-1"
    text = path.read_text(encoding="utf-8")
    if 'stash["mae_usd"]' in text or "stash['mae_usd']" in text:
        return f"{PEEK_REL}:-1"
    return f"{PEEK_REL}:{_line_of(PEEK_REL, 'def _peek_excursion_usd')}"


def _not_set_true(rel: str) -> str:
    path = REPO_ROOT / rel
    if not path.is_file():
        return f"{rel}:-1"
    text = path.read_text(encoding="utf-8")
    if "PATH_EXIT_K3_SHADOW.set(True)" in text:
        return f"{rel}:-1"
    return f"{rel}:ok"


def inspect_path_shape_k3_dead_protocol() -> dict[str, Any]:
    """Locked protocol dump. Missing a required site = no Gate 2."""
    dump: dict[str, Any] = {
        "eps_sit": f"{SHAPE_REL}:{_line_of(SHAPE_REL, 'EPS_SIT = 0.05')}",
        "mfe_life": f"{SHAPE_REL}:{_line_of(SHAPE_REL, 'MFE_LIFE = 0.25')}",
        "t_lock": f"{CORE_REL}:{_line_of(CORE_REL, 'T_LOCK = -0.04787176712367987')}",
        "t_fp": f"{T025_REL}:{_line_of(T025_REL, 'T_FP = -0.25')}",
        "shape_shadow_default": (
            f"{SHAPE_REL}:{_line_of(SHAPE_REL, 'ContextVar(\"path_shape_k3_shadow\", default=False)')}"
        ),
        "t_shadow_default": (f"{CORE_REL}:{_line_of(CORE_REL, 'ContextVar(\"path_exit_k3_shadow\", default=False)')}"),
        "should_no_t_compare": _no_t_compare(),
        "after_open_telem": (f"{HOOK_REL}:{_line_of(HOOK_REL, 'def after_open_telem_path_exit_k3')}"),
        "peek_no_stash_write": _peek_clean(),
        "shape_set_eval": f"{EVAL_REL}:{_line_of(EVAL_REL, 'PATH_SHAPE_K3_SHADOW.set')}",
        "shape_set_run": f"{RUN_REL}:{_line_of(RUN_REL, 'PATH_SHAPE_K3_SHADOW.set')}",
        "t_shadow_not_set_true_eval": _not_set_true(EVAL_REL),
        "t_shadow_not_set_true_run": _not_set_true(RUN_REL),
        "license_shape_both": f"{FLAGS_REL}:{_line_of(FLAGS_REL, 'split_a and split_b')}",
        "license_transfer_both": f"{FLAGS_REL}:{_line_of(FLAGS_REL, 'moved_a and moved_b')}",
        "transfer_ok_requires_shape_split": (
            f"{RUN_REL}:{_line_of(RUN_REL, 'TRANSFER_OK unreachable unless Gate 1 was SHAPE_SPLIT')}"
        ),
        "forbidden_write_path_early_jsonl": (f"{SHAPE_REL}:{_line_of(SHAPE_REL, 'path_early_A_close_ledger.jsonl')}"),
        "forbidden_write_path_exit_k3_t025_jsonl": (
            f"{SHAPE_REL}:{_line_of(SHAPE_REL, 'path_exit_k3_t025_A_close_ledger.jsonl')}"
        ),
        "evaluate_only_learn": (
            f"{GRIND_REL}:{_line_of(GRIND_REL, 'awakening grind train=False — learn() forbidden')}"
        ),
        "parent_sha_const": f"{CORE_REL}:{_line_of(CORE_REL, 'INIT_SHA256 = \"8cc435c6')}",
        "gitpython_pin": f"{REQ_REL}:{_line_of(REQ_REL, 'GitPython==3.1.59')}",
        "codecov_patch_50": f"{CODECOV_REL}:{_line_of(CODECOV_REL, 'target: 50%')}",
        "mutual_exclusion": (f"{HOOK_REL}:{_line_of(HOOK_REL, 'T-family shadow and shape shadow both on')}"),
    }
    required = (
        "eps_sit",
        "mfe_life",
        "t_lock",
        "t_fp",
        "shape_shadow_default",
        "t_shadow_default",
        "should_no_t_compare",
        "after_open_telem",
        "peek_no_stash_write",
        "shape_set_eval",
        "shape_set_run",
        "t_shadow_not_set_true_eval",
        "t_shadow_not_set_true_run",
        "license_shape_both",
        "license_transfer_both",
        "transfer_ok_requires_shape_split",
        "forbidden_write_path_early_jsonl",
        "forbidden_write_path_exit_k3_t025_jsonl",
        "evaluate_only_learn",
        "parent_sha_const",
        "gitpython_pin",
        "codecov_patch_50",
        "mutual_exclusion",
    )
    dump["missing_sites"] = [k for k in required if str(dump.get(k) or "").endswith(":-1")]
    dump["gate0_complete"] = len(dump["missing_sites"]) == 0
    return dump


__all__ = ["inspect_path_shape_k3_dead_protocol"]

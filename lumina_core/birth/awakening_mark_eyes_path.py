"""Gate 0 file:line dump for Awakening MARK_EYES."""

from __future__ import annotations

from pathlib import Path
from typing import Any

REPO_ROOT = Path(__file__).resolve().parents[2]
CORE_REL = "lumina_core/birth/awakening_mark_eyes.py"
OBS_REL = "lumina_core/birth/awakening_mark_eyes_obs.py"
ENV_REL = "lumina_core/birth/awakening_mark_eyes_env.py"
FLAGS_REL = "lumina_core/birth/awakening_mark_eyes_flags.py"
BUILDER_REL = "lumina_core/rl/observation_builder.py"
EXIT_REL = "lumina_core/birth/awakening_path_exit_k3.py"
SHAPE_REL = "lumina_core/birth/awakening_path_shape_k3_dead.py"
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


def _on_step_clean() -> str:
    body = _fn_source(OBS_REL, "on_step")
    if not body.strip():
        cls = (REPO_ROOT / OBS_REL).read_text(encoding="utf-8")
        start = cls.find("def on_step")
        if start < 0:
            return f"{OBS_REL}:-1"
        nxt = cls.find("\n    def ", start + 4)
        body = cls[start:nxt] if nxt > 0 else cls[start:]
    banned = ("high", "low", "mae_usd", "mfe")
    if any(token in body for token in banned):
        return f"{OBS_REL}:-1"
    return f"{OBS_REL}:{_line_of(OBS_REL, 'def on_step')}"


def inspect_mark_eyes_protocol() -> dict[str, Any]:
    """Locked protocol dump. Missing a required site → S_MISSING, still write AUDIT."""
    dump: dict[str, Any] = {
        "observation_dim_43": f"{BUILDER_REL}:{_line_of(BUILDER_REL, 'OBSERVATION_DIM = 43')}",
        "mark_eyes_obs_dim_46": f"{CORE_REL}:{_line_of(CORE_REL, 'MARK_EYES_OBS_DIM = 46')}",
        "timesteps_10000": f"{CORE_REL}:{_line_of(CORE_REL, 'MARK_EYES_PPO_TIMESTEPS = 10_000')}",
        "hold_norm_120": f"{CORE_REL}:{_line_of(CORE_REL, 'HOLD_NORM = 120.0')}",
        "child_zip": f"{CORE_REL}:{_line_of(CORE_REL, 'CHILD_ZIP_NAME = \"awakening_mark_eyes_pi_star.zip\"')}",
        "init_refused_parent": f"{CORE_REL}:{_line_of(CORE_REL, 'birth_exit_pi_star.zip')}",
        "on_step_no_wick": _on_step_clean(),
        "concat_requires_43": f"{OBS_REL}:{_line_of(OBS_REL, 'len(base)==')}",
        "wrapper_obs_shape_46": f"{ENV_REL}:{_line_of(ENV_REL, 'shape=(46,)')}",
        "path_exit_shadow_default": (
            f"{EXIT_REL}:{_line_of(EXIT_REL, 'ContextVar(\"path_exit_k3_shadow\", default=False)')}"
        ),
        "path_shape_shadow_default": (
            f"{SHAPE_REL}:{_line_of(SHAPE_REL, 'ContextVar(\"path_shape_k3_shadow\", default=False)')}"
        ),
        "license_eyes_both": f"{FLAGS_REL}:{_line_of(FLAGS_REL, 'moved_a and moved_b')}",
        "evaluate_only_learn": (
            f"{GRIND_REL}:{_line_of(GRIND_REL, 'awakening grind train=False — learn() forbidden')}"
        ),
        "parent_sha_const": f"{EXIT_REL}:{_line_of(EXIT_REL, 'INIT_SHA256 = \"8cc435c6')}",
        "gitpython_pin": f"{REQ_REL}:{_line_of(REQ_REL, 'GitPython==3.1.59')}",
        "codecov_patch_50": f"{CODECOV_REL}:{_line_of(CODECOV_REL, 'target: 50%')}",
        "forbidden_write_parent_zip": f"{CORE_REL}:{_line_of(CORE_REL, 'birth_exit_pi_star.zip')}",
        "forbidden_write_path_early_jsonl": (
            f"{CORE_REL}:{_line_of(CORE_REL, 'path_early_A_close_ledger.jsonl')}"
        ),
        "forbidden_write_path_exit_k3_jsonl": (
            f"{CORE_REL}:{_line_of(CORE_REL, 'path_exit_k3_A_close_ledger.jsonl')}"
        ),
        "state_on_step": f"{OBS_REL}:{_line_of(OBS_REL, 'def on_step')}",
        "concat_mark_eyes": f"{OBS_REL}:{_line_of(OBS_REL, 'def concat_mark_eyes')}",
    }
    required = (
        "observation_dim_43",
        "mark_eyes_obs_dim_46",
        "timesteps_10000",
        "hold_norm_120",
        "child_zip",
        "init_refused_parent",
        "on_step_no_wick",
        "concat_requires_43",
        "wrapper_obs_shape_46",
        "path_exit_shadow_default",
        "path_shape_shadow_default",
        "license_eyes_both",
        "evaluate_only_learn",
        "parent_sha_const",
        "gitpython_pin",
        "codecov_patch_50",
        "forbidden_write_parent_zip",
        "forbidden_write_path_early_jsonl",
        "forbidden_write_path_exit_k3_jsonl",
    )
    dump["missing_sites"] = [k for k in required if str(dump.get(k) or "").endswith(":-1")]
    dump["gate0_complete"] = len(dump["missing_sites"]) == 0
    return dump


__all__ = ["inspect_mark_eyes_protocol"]

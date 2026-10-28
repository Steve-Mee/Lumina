"""Gate 0 file:line dump for Awakening hole-tax protocol."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from lumina_core.birth.awakening_select_path import inspect_select_protocol

REPO_ROOT = Path(__file__).resolve().parents[2]
TAX_REL = "lumina_core/birth/awakening_hole_tax.py"
TAX_RUN_REL = "lumina_core/birth/awakening_hole_tax_run.py"
SELECT_ENV_REL = "lumina_core/birth/awakening_select_env.py"
SELECT_RUN_REL = "lumina_core/birth/awakening_select_run.py"
EXPORT_REL = "lumina_core/birth/birth_exit_policy_export.py"
FIXTURE_REL = "lumina_core/birth/synthetic_cloud_fixture.py"


def _line_of(rel: str, needle: str) -> int:
    path = REPO_ROOT / rel
    if not path.is_file():
        return -1
    for i, line in enumerate(path.read_text(encoding="utf-8").splitlines(), 1):
        if needle in line:
            return i
    return -1


def inspect_hole_tax_protocol() -> dict[str, Any]:
    """Locked protocol dump. Missing a required site = Gate 0 fail."""
    select = inspect_select_protocol()
    dump: dict[str, Any] = {
        "apply_hole_tax": f"{TAX_REL}:{_line_of(TAX_REL, 'def apply_hole_tax')}",
        "hole_tax_r_const": f"{TAX_REL}:{_line_of(TAX_REL, 'AWAKENING_HOLE_TAX_R = 1.0')}",
        "timesteps_const": (
            f"{TAX_REL}:{_line_of(TAX_REL, 'AWAKENING_HOLE_TAX_PPO_TIMESTEPS = 10_000')}"
        ),
        "hole_reason": f"{TAX_REL}:{_line_of(TAX_REL, 'HOLE_REASON = \"stop\"')}",
        "hole_regime": f"{TAX_REL}:{_line_of(TAX_REL, 'HOLE_REGIME = \"NEUTRAL\"')}",
        "env_tax_r_default": f"{SELECT_ENV_REL}:{_line_of(SELECT_ENV_REL, 'tax_r: float = 0.0')}",
        "env_hook": f"{SELECT_ENV_REL}:{_line_of(SELECT_ENV_REL, 'apply_hole_tax(process_r, reason, regime)')}",
        "init_path_resolver": f"{TAX_REL}:{_line_of(TAX_REL, 'def resolve_hole_tax_init_path')}",
        "init_sha_assert": f"{TAX_REL}:{_line_of(TAX_REL, 'def assert_init_sha')}",
        "init_sha_const": f"{TAX_REL}:{_line_of(TAX_REL, 'INIT_SHA256 =')}",
        "control_sha_const": f"{TAX_REL}:{_line_of(TAX_REL, 'CONTROL_SHA256 =')}",
        "control_init_refuse": f"{TAX_REL}:{_line_of(TAX_REL, 'def assert_not_control_init')}",
        "gitignored_refuse": f"{EXPORT_REL}:{_line_of(EXPORT_REL, 'def is_gitignored_ppo_zip')}",
        "isolated_workspace": f"{TAX_REL}:{_line_of(TAX_REL, 'def isolated_workspace')}",
        "forbidden_writes": f"{TAX_REL}:{_line_of(TAX_REL, 'FORBIDDEN_WRITE_NAMES')}",
        "train_seed_const": f"{TAX_REL}:{_line_of(TAX_REL, 'TRAIN_SEED = 20260901')}",
        "eval_a_seed": f"{TAX_REL}:{_line_of(TAX_REL, 'EVAL_A_SEED = 20260902')}",
        "eval_b_seed": f"{TAX_REL}:{_line_of(TAX_REL, 'EVAL_B_SEED = 20260903')}",
        "train_seed_refuse": f"{TAX_REL}:{_line_of(TAX_REL, 'def assert_train_seed')}",
        "holdout_b_path_refuse": f"{TAX_REL}:{_line_of(TAX_REL, 'def assert_not_holdout_b_path')}",
        "fixture_generator": f"{FIXTURE_REL}:{_line_of(FIXTURE_REL, 'SOURCE_LABEL =')}",
        "budget_assert": f"{TAX_REL}:{_line_of(TAX_REL, 'def assert_budget')}",
        "learn_site": f"{TAX_RUN_REL}:{_line_of(TAX_RUN_REL, 'model.learn(')}",
        "select_learn_hooks": f"{SELECT_RUN_REL}:{_line_of(SELECT_RUN_REL, 'def run_select_train')}",
        "child_sidecar": f"{TAX_REL}:{_line_of(TAX_REL, 'def child_sidecar_payload')}",
        "hole_substitution": f"{TAX_REL}:{_line_of(TAX_REL, 'def hole_substitution')}",
        "select_overfit": f"{TAX_REL}:{_line_of(TAX_REL, 'def select_overfit')}",
        "hole_moved": f"{TAX_REL}:{_line_of(TAX_REL, 'def hole_moved')}",
        "mes5": select.get("mes5"),
        "qty_one": select.get("qty_one"),
        "clip": select.get("clip"),
        "process_r": select.get("process_r"),
        "plan_fill": select.get("plan_fill"),
        "chatter_train": select.get("chatter_train"),
        "envelope_train": select.get("envelope_train"),
        "calibrate_train": select.get("calibrate_train"),
        "G_MISWIRE": select.get("G_MISWIRE"),
    }
    required = (
        "apply_hole_tax",
        "hole_tax_r_const",
        "timesteps_const",
        "env_hook",
        "env_tax_r_default",
        "init_path_resolver",
        "init_sha_assert",
        "control_init_refuse",
        "gitignored_refuse",
        "isolated_workspace",
        "train_seed_refuse",
        "budget_assert",
        "learn_site",
        "child_sidecar",
        "hole_substitution",
        "select_overfit",
        "hole_moved",
    )
    dump["missing_sites"] = [k for k in required if str(dump.get(k) or "").endswith(":-1")]
    dump["gate0_complete"] = len(dump["missing_sites"]) == 0
    return dump


__all__ = ["inspect_hole_tax_protocol"]

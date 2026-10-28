"""Gate 0 file:line dump for Awakening selection protocol."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from lumina_core.birth.awakening_edge_path import inspect_grind_geometry_path
from lumina_core.birth.awakening_mech_path import inspect_grind_live_path

REPO_ROOT = Path(__file__).resolve().parents[2]
SELECT_REL = "lumina_core/birth/awakening_select.py"
SELECT_ENV_REL = "lumina_core/birth/awakening_select_env.py"
SELECT_RUN_REL = "lumina_core/birth/awakening_select_run.py"
GRIND_RUN_REL = "lumina_core/birth/awakening_grind_run.py"
EXPORT_REL = "lumina_core/birth/birth_exit_policy_export.py"
FIXTURE_REL = "lumina_core/birth/synthetic_cloud_fixture.py"
FOUNDATION_REL = "lumina_core/birth/foundation_complete.py"
WEIGHTS_REL = "lumina_core/rl/ppo_trainer_weights.py"
TRAIN_REL = "lumina_core/rl/ppo_trainer_train.py"


def _line_of(rel: str, needle: str) -> int:
    path = REPO_ROOT / rel
    if not path.is_file():
        return -1
    for i, line in enumerate(path.read_text(encoding="utf-8").splitlines(), 1):
        if needle in line:
            return i
    return -1


def inspect_select_protocol() -> dict[str, Any]:
    """Locked protocol dump. Missing a required site = Gate 0 fail."""
    geo = inspect_grind_geometry_path()
    live = inspect_grind_live_path()
    dump: dict[str, Any] = {
        "init_path_resolver": f"{SELECT_REL}:{_line_of(SELECT_REL, 'def resolve_select_init_path')}",
        "init_sha_assert": f"{SELECT_REL}:{_line_of(SELECT_REL, 'def assert_init_sha')}",
        "init_sha_const": f"{SELECT_REL}:{_line_of(SELECT_REL, 'INIT_SHA256 =')}",
        "gitignored_refuse": f"{EXPORT_REL}:{_line_of(EXPORT_REL, 'def is_gitignored_ppo_zip')}",
        "pi_star_geometry": f"{EXPORT_REL}:{_line_of(EXPORT_REL, 'def resolve_pi_star_path')}",
        "isolated_workspace": f"{SELECT_REL}:{_line_of(SELECT_REL, 'def isolated_workspace')}",
        "forbidden_writes": f"{SELECT_REL}:{_line_of(SELECT_REL, 'FORBIDDEN_WRITE_NAMES')}",
        "train_seed_const": f"{SELECT_REL}:{_line_of(SELECT_REL, 'TRAIN_SEED = 20260901')}",
        "eval_a_seed": f"{SELECT_REL}:{_line_of(SELECT_REL, 'EVAL_A_SEED = 20260902')}",
        "eval_b_seed": f"{SELECT_REL}:{_line_of(SELECT_REL, 'EVAL_B_SEED = 20260903')}",
        "train_seed_refuse": f"{SELECT_REL}:{_line_of(SELECT_REL, 'def assert_train_seed')}",
        "holdout_b_path_refuse": f"{SELECT_REL}:{_line_of(SELECT_REL, 'def assert_not_holdout_b_path')}",
        "fixture_generator": f"{FIXTURE_REL}:{_line_of(FIXTURE_REL, 'SOURCE_LABEL =')}",
        "budget_pin": f"{SELECT_REL}:{_line_of(SELECT_REL, 'AWAKENING_SELECT_PPO_TIMESTEPS = 10_000')}",
        "budget_assert": f"{SELECT_REL}:{_line_of(SELECT_REL, 'def assert_budget')}",
        "polish_quantum": f"{FOUNDATION_REL}:{_line_of(FOUNDATION_REL, 'polish_steps = min(10_000')}",
        "learn_site": f"{SELECT_RUN_REL}:{_line_of(SELECT_RUN_REL, 'model.learn(')}",
        "save_weights": f"{WEIGHTS_REL}:{_line_of(WEIGHTS_REL, 'def save_weights')}",
        "ppo_learn_trainer": f"{TRAIN_REL}:{_line_of(TRAIN_REL, 'model.learn(total_timesteps=total_timesteps')}",
        "child_sidecar": f"{SELECT_REL}:{_line_of(SELECT_REL, 'def child_sidecar_payload')}",
        "policy_path_eval": f"{GRIND_RUN_REL}:{_line_of(GRIND_RUN_REL, 'policy_path: Path | str | None = None')}",
        "eval_train_false": f"{GRIND_RUN_REL}:{_line_of(GRIND_RUN_REL, 'if TRAIN:')}",
        "chatter_train": f"{SELECT_ENV_REL}:{_line_of(SELECT_ENV_REL, 'ForceOpenChatterBound()')}",
        "envelope_train": f"{SELECT_ENV_REL}:{_line_of(SELECT_ENV_REL, 'decide_stage2_participation(')}",
        "calibrate_train": f"{SELECT_ENV_REL}:{_line_of(SELECT_ENV_REL, 'calibrate_birth_stops(')}",
        "mes5": geo.get("mes5"),
        "qty_one": geo.get("qty_one"),
        "clip": geo.get("clip"),
        "process_r": geo.get("trade_r"),
        "plan_fill": geo.get("plan_birth_exit_fill"),
        "envelope_eval": live.get("envelope_site"),
        "chatter_eval": live.get("chatter_site"),
        "refractory_eval": live.get("refractory_site"),
        "G_MISWIRE": geo.get("G_MISWIRE"),
        "envelope_enabled_kwarg": live.get("envelope_enabled_kwarg"),
        "chatter_bound_constructed": live.get("chatter_bound_constructed"),
    }
    required = (
        "init_path_resolver",
        "init_sha_assert",
        "gitignored_refuse",
        "isolated_workspace",
        "train_seed_refuse",
        "budget_pin",
        "budget_assert",
        "learn_site",
        "policy_path_eval",
        "chatter_train",
        "envelope_train",
        "calibrate_train",
    )
    dump["missing_sites"] = [k for k in required if str(dump.get(k) or "").endswith(":-1")]
    dump["gate0_complete"] = len(dump["missing_sites"]) == 0
    return dump


__all__ = ["inspect_select_protocol"]

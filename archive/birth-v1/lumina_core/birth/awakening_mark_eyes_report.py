"""MARK_EYES audit / verdict / flags writers. Proof stamped false."""

from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from lumina_core.birth.awakening_mark_eyes import (
    FAMILY,
    FLAGS_NAME,
    GATE0_MAIN_SHA,
    INIT_SHA256,
    MARK_EYES_OBS_DIM,
    MARK_EYES_PPO_TIMESTEPS,
    PARENT_BRANCH,
    SOURCE,
    TRAIN_SEED,
    assert_isolated_write,
    honesty_paragraph,
)
from lumina_core.birth.awakening_mark_eyes_flags import license_eyes
from lumina_core.birth.awakening_mark_eyes_tables import table_t0, table_t1, table_t2, table_t3
from lumina_core.rl.observation_builder import OBSERVATION_DIM

DEAD_BODY_LAW = (
    "LAW: paper-MAE / T_LOCK / T_FP / DEAD / BOUNCE families are closed as controllers\n"
    "on parent 8cc435c6. This window is a new body with mark-path eyes. Proof=false."
)


def write_mark_eyes_reports(
    *,
    reports: Path,
    overall: str,
    proto: dict[str, Any],
    parent_sha: str,
    child_sha: str,
    actual_timesteps: int,
    optimizer_steps: int,
    ticks_sha16: str,
    init_policy: str,
    learn_called: bool,
    path_early_present: bool,
    hooks_false: bool,
    workspace_isolated: bool,
    forbidden_init_refused: bool,
    leg_a: dict[str, Any],
    leg_b: dict[str, Any],
    gate0_sha: str = GATE0_MAIN_SHA,
) -> dict[str, Any]:
    now = datetime.now(timezone.utc).isoformat()
    artifacts = reports / "artifacts"
    artifacts.mkdir(parents=True, exist_ok=True)
    licensed = license_eyes(leg_a, leg_b)
    tag = str(licensed.get("tag") or "S_MISSING")
    law = str(licensed.get("law") or "NONE")
    family = str(licensed.get("licensed_next_family") or "H_NONE")
    t0 = table_t0(
        origin_sha=gate0_sha,
        parent_sha=parent_sha,
        child_sha=child_sha,
        init_policy=init_policy,
        actual_timesteps=actual_timesteps,
        optimizer_steps=optimizer_steps,
        ticks_sha16=ticks_sha16,
    )
    t1 = table_t1(
        actual_timesteps=actual_timesteps,
        optimizer_steps=optimizer_steps,
        workspace_isolated=workspace_isolated,
        forbidden_init_refused=forbidden_init_refused,
    )
    t2 = table_t2(leg_a, leg_b)
    t3 = table_t3(licensed, overall=overall)
    flags_payload = {
        "source": SOURCE,
        "obs_dim_global": int(OBSERVATION_DIM),
        "obs_dim_eyes": int(MARK_EYES_OBS_DIM),
        "timesteps": int(MARK_EYES_PPO_TIMESTEPS),
        "train_seed": int(TRAIN_SEED),
        "init_policy": str(init_policy),
        "parent_sha256": str(parent_sha or INIT_SHA256),
        "child_sha256": str(child_sha),
        "actual_timesteps": int(actual_timesteps),
        "optimizer_steps": int(optimizer_steps),
        "replay_ran": bool(learn_called and path_early_present),
        "learn_called": bool(learn_called),
        "A": leg_a,
        "B": leg_b,
        "tag": tag,
        "HOLE_MOVED_A": bool(licensed.get("HOLE_MOVED_A")),
        "HOLE_MOVED_B": bool(licensed.get("HOLE_MOVED_B")),
        "law": law,
        "licensed_next_family": family,
        "evolution_proof_stamped": False,
        "REAL": "no",
        "playground": False,
        "hook_default": False,
        "shape_default": False,
        "t_family_shadow_on": False,
        "overall": overall,
    }
    flags_path = assert_isolated_write(artifacts / FLAGS_NAME)
    flags_path.write_text(json.dumps(flags_payload, indent=2, default=str) + "\n", encoding="utf-8")
    honesty = honesty_paragraph(
        tag=tag, law=law, licensed_next_family=family, actual_timesteps=actual_timesteps
    )
    audit = [
        "# AWAKENING_MARK_EYES_AUDIT",
        "",
        "## Gate 0",
        f"- origin/main SHA `{gate0_sha}`",
        f"- parent branch used `{PARENT_BRANCH}`",
        f"- OBSERVATION_DIM `{OBSERVATION_DIM}`",
        f"- parent sha match `{parent_sha or INIT_SHA256}`",
        "- dead-family flags present (shape/t025/bounce if on disk)",
        f"- hooks default False : {'yes' if hooks_false else 'no'}",
        f"- date: `{now}`",
        "",
        "## Eyes",
        f"- MarkEyesState file:line `{proto.get('state_on_step')}`",
        f"- concat_mark_eyes file:line `{proto.get('concat_mark_eyes')}`",
        f"- wrapper obs shape file:line `{proto.get('wrapper_obs_shape_46')}`",
        "",
        "## Train",
        f"- init=scratch `{init_policy}`",
        f"- timesteps actual / cap `{actual_timesteps}` / `{MARK_EYES_PPO_TIMESTEPS}`",
        f"- child sha256 `{child_sha}`",
        f"- isolated workspace `{workspace_isolated}`",
        "",
        "## Eval",
        json.dumps(t2, indent=2, default=str),
        "",
        "## Flags",
        json.dumps(flags_payload, indent=2, default=str),
        "",
        "## Honesty",
        honesty,
        "",
        "## Protocol inspect",
        json.dumps(proto, indent=2, default=str),
        "",
        "## T0 / T1 / T3",
        json.dumps(t0, indent=2, default=str),
        json.dumps(t1, indent=2, default=str),
        json.dumps(t3, indent=2, default=str),
        "",
    ]
    assert_isolated_write(reports / "AWAKENING_MARK_EYES_AUDIT.md").write_text(
        "\n".join(audit) + "\n", encoding="utf-8"
    )
    verdict = [
        "# AWAKENING_MARK_EYES_VERDICT",
        "",
        f"**Overall:** `{overall}`",
        f"**Date:** {now}",
        f"**Child sha256:** `{child_sha}`",
        f"**init_policy:** `{init_policy}`",
        f"**actual_timesteps:** `{actual_timesteps}`",
        f"**optimizer_steps:** `{optimizer_steps}`",
        f"**learn_called:** `{str(bool(learn_called)).lower()}`",
        f"**Tag:** `{tag}`",
        f"**Law:** `{law}`",
        f"**Family:** `{FAMILY}`",
        f"**licensed_next_family:** `{family}`",
        "**Evolution Proof stamped:** `False`",
        "**Playground:** `no`",
        "**REAL:** `no`",
        "",
        "### T0 — identity",
        json.dumps(t0, indent=2, default=str),
        "",
        "### T1 — train",
        json.dumps(t1, indent=2, default=str),
        "",
        "### T2 — eval vs path_early",
        json.dumps(t2, indent=2, default=str),
        "",
        "### T3 — license",
        json.dumps(t3, indent=2, default=str),
        "",
        "### Honesty",
        honesty,
        "",
    ]
    assert_isolated_write(reports / "AWAKENING_MARK_EYES_VERDICT.md").write_text(
        "\n".join(verdict) + "\n", encoding="utf-8"
    )
    block = (
        "\n---\n\n"
        "## This ticket — Awakening MARK_EYES (new body, mark-path eyes)\n\n"
        f"{DEAD_BODY_LAW}\n"
        "**Prompt:** Does a NEW policy body, born with mark-path eyes, trained one pinned "
        "10_000-step shot on TRAIN seed only, move the hole AND raise policy mean_r on BOTH "
        "eval seeds versus the frozen path_early book of parent zip 8cc435c6?\n"
        f"**Train:** one shot timesteps=10000 seed=20260901 init=scratch actual={actual_timesteps}.\n"
        f"**Landed:** Gate 0 SHA `{gate0_sha}`. Parent `{PARENT_BRANCH}`.\n"
        f"**learn_called**={str(bool(learn_called)).lower()} child_sha={child_sha[:16] if child_sha else ''}\n"
        f"**Leg A** n_H={leg_a.get('n_H')} n_H_early={leg_a.get('n_H_early')} "
        f"mean_r={leg_a.get('mean_r_policy')} HOLE_MOVED={leg_a.get('HOLE_MOVED')}\n"
        f"**Leg B** n_H={leg_b.get('n_H')} n_H_early={leg_b.get('n_H_early')} "
        f"mean_r={leg_b.get('mean_r_policy')} HOLE_MOVED={leg_b.get('HOLE_MOVED')}\n"
        f"**Tag / law:** `{tag}` / `{law}` family=`{family}`\n"
        f"**Overall:** `{overall}`\n"
        "**SSOT:** `AWAKENING_MARK_EYES_AUDIT.md` / `AWAKENING_MARK_EYES_VERDICT.md`\n"
    )
    for rel in (reports / "LUMINA_BIRTH_EXPERIMENT_LOG.md", reports / "artifacts" / "LUMINA_BIRTH_EXPERIMENT_LOG.md"):
        if rel.is_file() or rel.parent.is_dir():
            with rel.open("a", encoding="utf-8") as fh:
                fh.write(block)
    return flags_payload


__all__ = ["DEAD_BODY_LAW", "write_mark_eyes_reports"]

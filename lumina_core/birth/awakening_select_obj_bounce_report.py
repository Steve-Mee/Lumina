"""SELECT_OBJ P_BOUNCE_WEAK audit / verdict / flags writers. Score only. Law NONE."""

from __future__ import annotations

import hashlib
import json
import re
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from lumina_core.birth.awakening_select_obj_bounce import (
    BOUNCE_WEAK,
    EPS_SIT_HIST,
    FAMILY,
    FLAGS_NAME,
    GATE0_MAIN_SHA,
    INIT_SHA256,
    K27_FLAGS_NAME,
    LAW_NONE,
    MFE_LIFE_HIST,
    PARENT_BRANCH,
    PATH_A_NAME,
    PATH_B_NAME,
    PATH_EARLY_A_NAME,
    PATH_EARLY_B_NAME,
    PATH_SHAPE_A_NAME,
    PATH_SHAPE_B_NAME,
    SHAPE_FLAGS_NAME,
    T025_A_NAME,
    T025_B_NAME,
    T025_FLAGS_NAME,
    T_FP_HIST,
    T_LOCK_HIST,
    assert_isolated_write,
    honesty_paragraph,
)
from lumina_core.birth.awakening_select_obj_bounce_flags import license_obj
from lumina_core.birth.awakening_select_obj_bounce_tables import table_t0, table_t4


def _file_sha256(path: Path) -> str:
    if not path.is_file():
        return ""
    digest = hashlib.sha256()
    digest.update(path.read_bytes())
    return digest.hexdigest()


def _read_tag(path: Path) -> str:
    if not path.is_file():
        return ""
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError, TypeError):
        return ""
    return str(payload.get("tag") or "")


def _constants_unchanged() -> bool:
    core = Path("lumina_core/birth/awakening_path_exit_k3.py").read_text(encoding="utf-8")
    t025 = Path("lumina_core/birth/awakening_path_exit_k3_t025.py").read_text(encoding="utf-8")
    shape = Path("lumina_core/birth/awakening_path_shape_k3_dead.py").read_text(encoding="utf-8")
    return (
        "T_LOCK = -0.04787176712367987" in core
        and "T_FP = -0.25" in t025
        and "EPS_SIT = 0.05" in shape
        and "MFE_LIFE = 0.25" in shape
    )


def _forbidden_grep() -> dict[str, Any]:
    birth = Path("lumina_core/birth")
    banned = "training" + "_reward"
    ident = re.compile(rf"(?<![A-Za-z0-9_]){re.escape(banned)}(?![A-Za-z0-9_])")
    hits_reward: list[str] = []
    hits_learn: list[str] = []
    for path in sorted(birth.rglob("*.py")):
        text = path.read_text(encoding="utf-8")
        if ident.search(text):
            hits_reward.append(str(path))
        if "model.learn(" in text:
            hits_learn.append(str(path))
    return {"hygiene_token_in_birth": hits_reward, "model_learn_in_birth": hits_learn, "playground": False}


def write_select_obj_bounce_reports(
    *,
    reports: Path,
    overall: str,
    zip_sha: str,
    measure_a: dict[str, Any],
    measure_b: dict[str, Any],
    proto: dict[str, Any],
    sha_a: str,
    sha_b: str,
    path_early_present: bool,
    hooks_false: bool,
    gate0_sha: str = GATE0_MAIN_SHA,
    n_policy: int | None = None,
) -> dict[str, Any]:
    now = datetime.now(timezone.utc).isoformat()
    artifacts = reports / "artifacts"
    artifacts.mkdir(parents=True, exist_ok=True)
    licensed = license_obj(measure_a, measure_b)
    tag = str(licensed.get("tag") or "S_MISSING")
    law = str(licensed.get("law") or LAW_NONE)
    family = str(licensed.get("licensed_next_family") or "H_NONE")
    t0 = table_t0(
        None,
        sha_a=sha_a,
        sha_b=sha_b,
        optimizer_steps=0,
        hooks_false=hooks_false,
        artifacts=artifacts,
        present=path_early_present,
        n_policy=n_policy,
    )
    t4 = table_t4(artifacts)
    flags_payload = {
        "source": "path_early_measure",
        "BOUNCE_WEAK": float(BOUNCE_WEAK),
        "EPS_SIT_HIST": float(EPS_SIT_HIST),
        "MFE_LIFE_HIST": float(MFE_LIFE_HIST),
        "T_LOCK_HIST": float(T_LOCK_HIST),
        "T_FP_HIST": float(T_FP_HIST),
        "replay_ran": False,
        "learn_called": False,
        "gate1_tag": tag,
        "A_measure": measure_a,
        "B_measure": measure_b,
        "tag": tag,
        "S_SPLIT_A": bool(licensed.get("S_SPLIT_A")),
        "S_SPLIT_B": bool(licensed.get("S_SPLIT_B")),
        "law": law,
        "licensed_next_family": family,
        "gate1": "NONE",
        "optimizer_steps": 0,
        "evaluated_zip_sha256": zip_sha or INIT_SHA256,
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
        gate1_tag=tag,
        lift_a=float(measure_a.get("lift") or 0.0),
        lift_b=float(measure_b.get("lift") or 0.0),
        min_bounce_a=measure_a.get("min_bounce_U"),
        min_bounce_b=measure_b.get("min_bounce_U"),
        tag=tag,
        licensed_next_family=family,
    )
    unchanged = _constants_unchanged()
    source = {
        "parent_sha256": zip_sha or INIT_SHA256,
        "path_early_A_sha256": sha_a or _file_sha256(artifacts / PATH_EARLY_A_NAME),
        "path_early_B_sha256": sha_b or _file_sha256(artifacts / PATH_EARLY_B_NAME),
        "path_exit_k3_A_sha256": _file_sha256(artifacts / PATH_A_NAME),
        "path_exit_k3_B_sha256": _file_sha256(artifacts / PATH_B_NAME),
        "path_exit_k3_t025_A_sha256": _file_sha256(artifacts / T025_A_NAME),
        "path_exit_k3_t025_B_sha256": _file_sha256(artifacts / T025_B_NAME),
        "path_shape_k3_dead_A_sha256": _file_sha256(artifacts / PATH_SHAPE_A_NAME),
        "path_shape_k3_dead_B_sha256": _file_sha256(artifacts / PATH_SHAPE_B_NAME),
    }
    shape_tag = _read_tag(artifacts / SHAPE_FLAGS_NAME)
    t025_tag = _read_tag(artifacts / T025_FLAGS_NAME)
    k27_tag = _read_tag(artifacts / K27_FLAGS_NAME)
    audit = [
        "# AWAKENING_SELECT_OBJ_BOUNCE_AUDIT",
        "",
        "## Gate 0",
        f"- origin/main SHA `{gate0_sha}`",
        f"- parent branch used `{PARENT_BRANCH}`",
        f"- T_LOCK / T_FP / EPS_SIT / MFE_LIFE unchanged : {'yes' if unchanged else 'no'}",
        f"- SHAPE flags tag if present `{shape_tag or 'absent'}`",
        f"- T025 flags tag if present `{t025_tag or 'absent'}`",
        f"- path_exit_k3 flags tag if present `{k27_tag or 'absent'}`",
        "- PATH_EXIT_K3_SHADOW default False",
        "- PATH_SHAPE_K3_SHADOW default False",
        f"- date: `{now}`",
        "",
        "## Score",
        f"- bounce_r file:line `{proto.get('bounce_r')}`",
        f"- pred_bounce_weak file:line `{proto.get('pred_bounce_weak')}`",
        f"- BOUNCE_WEAK file:line `{proto.get('bounce_weak')}`",
        "",
        "## Source",
        f"- parent sha256 `{source['parent_sha256']}`",
        f"- path_early A/B sha256 `{source['path_early_A_sha256']}` / `{source['path_early_B_sha256']}`",
        f"- path_exit_k3 (#27) A/B sha256 `{source['path_exit_k3_A_sha256']}` / `{source['path_exit_k3_B_sha256']}`",
        f"- path_exit_k3_t025 A/B sha256 `{source['path_exit_k3_t025_A_sha256']}` / `{source['path_exit_k3_t025_B_sha256']}`",
        f"- path_shape_k3_dead A/B sha256 `{source['path_shape_k3_dead_A_sha256']}` / `{source['path_shape_k3_dead_B_sha256']}`",
        "",
        "## Gate 1",
        json.dumps({"A": measure_a, "B": measure_b, "OBJ": licensed}, indent=2, default=str),
        "",
        "## Gate 2",
        "- replay_ran=false",
        "- learn_called=false",
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
        "## Tm / T0 / T4",
        json.dumps({"A": measure_a, "B": measure_b, "BOUNCE_WEAK": BOUNCE_WEAK}, indent=2, default=str),
        json.dumps(t0, indent=2, default=str),
        json.dumps(t4, indent=2, default=str),
        "",
        "## Forbidden-path grep",
        json.dumps(_forbidden_grep(), indent=2, default=str),
        "",
    ]
    audit_path = assert_isolated_write(reports / "AWAKENING_SELECT_OBJ_BOUNCE_AUDIT.md")
    audit_path.write_text("\n".join(audit) + "\n", encoding="utf-8")
    verdict = [
        "# AWAKENING_SELECT_OBJ_BOUNCE_VERDICT",
        "",
        f"**Overall:** `{overall}`",
        f"**Date:** {now}",
        f"**Evaluated zip sha256:** `{zip_sha or INIT_SHA256}`",
        "**optimizer_steps:** `0`",
        "**replay_ran:** `false`",
        "**learn_called:** `false`",
        f"**BOUNCE_WEAK:** `{BOUNCE_WEAK}`",
        f"**gate1_tag:** `{tag}`",
        f"**Tag:** `{tag}`",
        f"**Law:** `{law}`",
        f"**Family:** `{FAMILY}`",
        f"**licensed_next_family:** `{family}`",
        "**Evolution Proof stamped:** `False`",
        "**Playground:** `no`",
        "**REAL:** `no`",
        "",
        "### Tm — Gate 1 measure",
        json.dumps({"A": measure_a, "B": measure_b, "BOUNCE_WEAK": BOUNCE_WEAK}, indent=2, default=str),
        "",
        "### T0 — identity",
        json.dumps(t0, indent=2, default=str),
        "",
        "### T4 — read-only prior hole",
        json.dumps(t4, indent=2, default=str),
        "",
        "### Honesty",
        honesty,
        "",
        "Playground does not open. No learn(). No flatten. Hook default off. Evolution Proof stamped: False.",
        "",
    ]
    verdict_path = assert_isolated_write(reports / "AWAKENING_SELECT_OBJ_BOUNCE_VERDICT.md")
    verdict_path.write_text("\n".join(verdict) + "\n", encoding="utf-8")
    block = f"""
---

## This ticket — Awakening SELECT_OBJ P_BOUNCE_WEAK (score measure, no flatten)

**Prompt:** On the frozen path_early A/B books, does a pre-declared WEAK-bounce score at k=3 — recovered R off paper MAE ≤ 0.50 — concentrate the hole versus winners under the locked path_early split algebra?
**Train:** none. optimizer_steps=0. Parent zip 8cc435c6 only. BOUNCE_WEAK={BOUNCE_WEAK}. No flatten. No learn().
**Landed:** Gate 0 SHA `{gate0_sha}`. Parent `{PARENT_BRANCH}`.
**replay_ran**=false learn_called=false gate1_tag={tag}
**Leg A** n_U3={measure_a.get("n_U3")} n_H3={measure_a.get("n_H3")} n_W3={measure_a.get("n_W3")} n_h_hit={measure_a.get("n_h_hit")} lift={measure_a.get("lift")} min_bounce={measure_a.get("min_bounce_U")}
**Leg B** n_U3={measure_b.get("n_U3")} n_H3={measure_b.get("n_H3")} n_W3={measure_b.get("n_W3")} n_h_hit={measure_b.get("n_h_hit")} lift={measure_b.get("lift")} min_bounce={measure_b.get("min_bounce_U")}
**Tag / law:** `{tag}` / `{law}` family=`{family}`
**Overall:** `{overall}`
**SSOT:** `AWAKENING_SELECT_OBJ_BOUNCE_AUDIT.md` / `AWAKENING_SELECT_OBJ_BOUNCE_VERDICT.md`
"""
    for rel in (reports / "LUMINA_BIRTH_EXPERIMENT_LOG.md", reports / "artifacts" / "LUMINA_BIRTH_EXPERIMENT_LOG.md"):
        if rel.is_file() or rel.parent.is_dir():
            with rel.open("a", encoding="utf-8") as fh:
                fh.write(block)
    return flags_payload


__all__ = ["write_select_obj_bounce_reports"]

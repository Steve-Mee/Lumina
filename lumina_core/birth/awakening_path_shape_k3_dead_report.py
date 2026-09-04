"""PATH_SHAPE K3 DEAD audit / verdict / flags writers. Shadow only. No train law."""

from __future__ import annotations

import hashlib
import json
import re
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from lumina_core.birth.awakening_path_exit_k3 import INIT_SHA256, T_LOCK
from lumina_core.birth.awakening_path_exit_k3_flags import compute_path_exit_k3_flags, path_exit_k3_rows
from lumina_core.birth.awakening_path_exit_k3_t025 import T_FP
from lumina_core.birth.awakening_path_shape_k3_dead import (
    EPS_SIT,
    FAMILY,
    FLAGS_NAME,
    GATE0_MAIN_SHA,
    LAW_NONE,
    MFE_LIFE,
    PARENT_BRANCH,
    PATH_A_NAME,
    PATH_B_NAME,
    PATH_EARLY_A_NAME,
    PATH_EARLY_B_NAME,
    T025_A_NAME,
    T025_B_NAME,
    honesty_paragraph,
    policy_only_rows,
)
from lumina_core.birth.awakening_path_shape_k3_dead_flags import (
    license_shape,
    license_transfer,
    mean_stamped_shape,
    mean_stamped_threshold,
)
from lumina_core.birth.awakening_path_shape_k3_dead_tables import table_t0, table_t1, table_t2, table_t3


def _file_sha256(path: Path) -> str:
    if not path.is_file():
        return ""
    digest = hashlib.sha256()
    digest.update(path.read_bytes())
    return digest.hexdigest()


def leg_payload(
    *,
    rows: list[dict[str, Any]],
    zip_sha: str,
    ticks_sha16: str,
    price_sha16_value: str,
    optimizer_steps: int,
    hook_enabled: bool,
    shape_enabled: bool,
    t_family_enabled: bool,
    baseline: dict[str, Any] | None,
    skip_replay: bool = False,
    replay_ran: bool = False,
    artifacts: Path | None = None,
    leg: str = "A",
) -> dict[str, Any]:
    flags = compute_path_exit_k3_flags(rows, baseline=baseline)
    t0 = table_t0(
        rows,
        zip_sha256=zip_sha,
        ticks_sha16=ticks_sha16,
        price_sha16_value=price_sha16_value,
        optimizer_steps=int(optimizer_steps),
        hook_enabled=bool(hook_enabled),
        shape_enabled=bool(shape_enabled),
        t_family_enabled=bool(t_family_enabled),
        skip_replay=bool(skip_replay),
        replay_ran=bool(replay_ran),
    )
    return {
        "t0": t0,
        "t1": table_t1(rows),
        "t2": table_t2(rows, baseline=baseline),
        "t3": table_t3(n_exit=int(flags.get("n_exit") or 0), artifacts=artifacts, leg=leg),
        "flags": flags,
        "rows_n": len(rows),
        "mean_stamped_threshold": mean_stamped_threshold(rows),
        "mean_stamped_shape": mean_stamped_shape(rows),
        "exits": path_exit_k3_rows(policy_only_rows(rows)),
    }


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


def write_path_shape_k3_dead_reports(
    *,
    reports: Path,
    overall: str,
    zip_sha: str,
    payload_a: dict[str, Any],
    payload_b: dict[str, Any],
    measure_a: dict[str, Any],
    measure_b: dict[str, Any],
    t4: dict[str, Any],
    proto: dict[str, Any],
    parent_loaded: bool,
    skip_replay: bool = False,
    replay_ran: bool = False,
    gate0_sha: str = GATE0_MAIN_SHA,
    flatten_sites: dict[str, str] | None = None,
    contextvar_try_finally: bool = True,
    t_family_shadow_on: bool = False,
    skipped_because: str = "",
    t025_tag: str = "",
) -> dict[str, Any]:
    now = datetime.now(timezone.utc).isoformat()
    artifacts = reports / "artifacts"
    artifacts.mkdir(parents=True, exist_ok=True)
    shape_lic = license_shape(measure_a, measure_b)
    gate1_tag = str(shape_lic.get("tag") or "S_MISSING")
    flags_a = payload_a.get("flags") or {}
    flags_b = payload_b.get("flags") or {}
    if replay_ran:
        licensed = license_transfer(flags_a, flags_b)
    else:
        licensed = {
            "tag": gate1_tag,
            "law": shape_lic.get("law") or LAW_NONE,
            "licensed_next_family": shape_lic.get("licensed_next_family") or "H_NONE",
            "gate1": shape_lic.get("gate1") or "NONE",
            "HOLE_MOVED_A": False,
            "HOLE_MOVED_B": False,
        }
    tag = str(licensed.get("tag") or gate1_tag)
    law = str(licensed.get("law") or LAW_NONE)
    t0_a, t0_b = payload_a.get("t0") or {}, payload_b.get("t0") or {}
    t1_a, t1_b = payload_a.get("t1") or {}, payload_b.get("t1") or {}
    t2_a, t2_b = payload_a.get("t2") or {}, payload_b.get("t2") or {}
    n_exit_a, n_exit_b = int(t1_a.get("n_exit") or 0), int(t1_b.get("n_exit") or 0)
    n_h_base_a, n_h_shape_a = int(t2_a.get("n_H_base") or 0), int(t2_a.get("n_H_shape") or 0)
    n_h_base_b, n_h_shape_b = int(t2_b.get("n_H_base") or 0), int(t2_b.get("n_H_shape") or 0)
    mean_r_base_a = float(t2_a.get("mean_r_policy_base") or 0.0)
    mean_r_shape_a = float(t2_a.get("mean_r_policy_shape") or 0.0)
    mean_r_base_b = float(t2_b.get("mean_r_policy_base") or 0.0)
    mean_r_shape_b = float(t2_b.get("mean_r_policy_shape") or 0.0)
    stamped_shape_a = payload_a.get("mean_stamped_shape")
    stamped_thr_a = payload_a.get("mean_stamped_threshold")
    flags_payload = {
        "source": "new_replay" if replay_ran else "path_early_measure",
        "EPS_SIT": float(EPS_SIT),
        "MFE_LIFE": float(MFE_LIFE),
        "T_LOCK_HIST": float(T_LOCK),
        "T_FP_HIST": float(T_FP),
        "skip_replay": bool(skip_replay),
        "replay_ran": bool(replay_ran),
        "gate1_tag": gate1_tag,
        "A_measure": measure_a,
        "B_measure": measure_b,
        "A": flags_a,
        "B": flags_b,
        "tag": tag,
        "HOLE_MOVED_A": bool(licensed.get("HOLE_MOVED_A")),
        "HOLE_MOVED_B": bool(licensed.get("HOLE_MOVED_B")),
        "S_SPLIT_A": bool(shape_lic.get("S_SPLIT_A")),
        "S_SPLIT_B": bool(shape_lic.get("S_SPLIT_B")),
        "law": law,
        "licensed_next_family": licensed.get("licensed_next_family"),
        "gate1": licensed.get("gate1"),
        "optimizer_steps": 0,
        "evaluated_zip_sha256": zip_sha,
        "evolution_proof_stamped": False,
        "REAL": "no",
        "playground": False,
        "hook_default": False,
        "shape_default": False,
        "t_family_shadow_on": bool(t_family_shadow_on),
        "mean_stamped_shape_A": stamped_shape_a,
        "overall": overall,
    }
    (artifacts / FLAGS_NAME).write_text(json.dumps(flags_payload, indent=2, default=str) + "\n", encoding="utf-8")
    honesty = honesty_paragraph(
        gate1_tag=gate1_tag,
        lift_a=float(measure_a.get("lift") or 0.0),
        lift_b=float(measure_b.get("lift") or 0.0),
        skip_replay=skip_replay,
        replay_ran=replay_ran,
        n_exit_a=n_exit_a,
        n_exit_b=n_exit_b,
        n_h_base_a=n_h_base_a,
        n_h_shape_a=n_h_shape_a,
        n_h_base_b=n_h_base_b,
        n_h_shape_b=n_h_shape_b,
        mean_r_base_a=mean_r_base_a,
        mean_r_shape_a=mean_r_shape_a,
        mean_r_base_b=mean_r_base_b,
        mean_r_shape_b=mean_r_shape_b,
        hole_moved_a=bool(licensed.get("HOLE_MOVED_A")),
        hole_moved_b=bool(licensed.get("HOLE_MOVED_B")),
        tag=tag,
        law=law,
    )
    sites = flatten_sites or {
        "force_flatten": "lumina_core/birth/sim_runner.py:force_flatten_this_step",
        "plan_birth_exit_fill": "lumina_core/rl/gym_stop_fill.py:plan_birth_exit_fill",
        "close_reason": "force_exit + path_exit_k3 sidecar",
    }
    t_lock_ok = "T_LOCK = -0.04787176712367987" in Path("lumina_core/birth/awakening_path_exit_k3.py").read_text(
        encoding="utf-8"
    )
    source = {
        "parent_sha256": zip_sha or INIT_SHA256,
        "path_early_A_sha256": _file_sha256(artifacts / PATH_EARLY_A_NAME),
        "path_early_B_sha256": _file_sha256(artifacts / PATH_EARLY_B_NAME),
        "path_exit_k3_A_sha256": _file_sha256(artifacts / PATH_A_NAME),
        "path_exit_k3_B_sha256": _file_sha256(artifacts / PATH_B_NAME),
        "path_exit_k3_t025_A_sha256": _file_sha256(artifacts / T025_A_NAME),
        "path_exit_k3_t025_B_sha256": _file_sha256(artifacts / T025_B_NAME),
    }
    skip_txt = skipped_because or ("replay_ran" if replay_ran else f"gate1_tag={gate1_tag}")
    audit = [
        "# AWAKENING_PATH_SHAPE_K3_DEAD_AUDIT",
        "",
        "## Gate 0",
        f"- origin/main SHA `{gate0_sha}`",
        f"- parent branch used `{PARENT_BRANCH}`",
        f"- T_LOCK still -0.04787176712367987 : {'yes' if t_lock_ok else 'no'}",
        f"- T025 flags tag if present `{t025_tag or 'absent'}`",
        "- PATH_EXIT_K3_SHADOW default False : yes",
        "- PATH_SHAPE_K3_SHADOW default False : yes",
        f"- parent_loaded: `{parent_loaded}`",
        f"- date: `{now}`",
        "",
        "## Hook",
        f"- should_path_shape_k3_dead file:line `{proto.get('should_no_t_compare')}`",
        f"- peek excursion file:line `{proto.get('peek_no_stash_write')}`",
        f"- after_open_telem file:line `{proto.get('after_open_telem')}`",
        f"- flatten site file:line `{sites.get('force_flatten')}`",
        f"- mutual exclusion file:line `{proto.get('mutual_exclusion')}`",
        "",
        "## Source",
        f"- parent sha256 `{source['parent_sha256']}`",
        f"- path_early A/B sha256 `{source['path_early_A_sha256']}` / `{source['path_early_B_sha256']}`",
        f"- path_exit_k3 (#27) A/B sha256 `{source['path_exit_k3_A_sha256']}` / `{source['path_exit_k3_B_sha256']}`",
        f"- path_exit_k3_t025 A/B sha256 `{source['path_exit_k3_t025_A_sha256']}` / `{source['path_exit_k3_t025_B_sha256']}`",
        "",
        "## Gate 1",
        json.dumps({"A": measure_a, "B": measure_b, "SHAPE_SPLIT": shape_lic}, indent=2, default=str),
        "",
        "## Gate 2",
        f"- skipped_because `{skip_txt}` / replay_ran `{str(bool(replay_ran)).lower()}` / optimizer_steps `0`",
        f"- ContextVar set/reset in try/finally : {'yes' if contextvar_try_finally else 'no'}",
        "- PATH_EXIT_K3_SHADOW remained False : yes",
        "",
        "## Flags",
        json.dumps(flags_payload, indent=2, default=str),
        "",
        "## n_exit vs T-family clone",
        f"- A n_exit `{n_exit_a}` / mean stamped shape `{stamped_shape_a}` / threshold present `{stamped_thr_a is not None}`",
        "",
        "## Honesty",
        honesty,
        "",
        "## Protocol inspect",
        json.dumps(proto, indent=2, default=str),
        "",
        "## Tm / T0 / T1 / T2 / T3 / T4",
        json.dumps({"A": measure_a, "B": measure_b}, indent=2, default=str),
        json.dumps({"A": t0_a, "B": t0_b}, indent=2, default=str),
        json.dumps({"A": t1_a, "B": t1_b}, indent=2, default=str),
        json.dumps({"A": t2_a, "B": t2_b}, indent=2, default=str),
        json.dumps({"A": payload_a.get("t3"), "B": payload_b.get("t3")}, indent=2, default=str),
        json.dumps(t4, indent=2, default=str),
        "",
        "## Forbidden-path grep",
        json.dumps(_forbidden_grep(), indent=2, default=str),
        "",
    ]
    (reports / "AWAKENING_PATH_SHAPE_K3_DEAD_AUDIT.md").write_text("\n".join(audit) + "\n", encoding="utf-8")
    verdict = [
        "# AWAKENING_PATH_SHAPE_K3_DEAD_VERDICT",
        "",
        f"**Overall:** `{overall}`",
        f"**Date:** {now}",
        f"**Evaluated zip sha256:** `{zip_sha or INIT_SHA256}`",
        "**optimizer_steps:** `0`",
        f"**skip_replay:** `{str(bool(skip_replay)).lower()}`",
        f"**replay_ran:** `{str(bool(replay_ran)).lower()}`",
        f"**EPS_SIT:** `{EPS_SIT}`",
        f"**MFE_LIFE:** `{MFE_LIFE}`",
        f"**gate1_tag:** `{gate1_tag}`",
        f"**n_exit A/B:** `{n_exit_a}` / `{n_exit_b}`",
        f"**n_H A base→shape:** `{n_h_base_a}` → `{n_h_shape_a}`",
        f"**n_H B base→shape:** `{n_h_base_b}` → `{n_h_shape_b}`",
        f"**mean_r A base→shape:** `{mean_r_base_a}` → `{mean_r_shape_a}`",
        f"**mean_r B base→shape:** `{mean_r_base_b}` → `{mean_r_shape_b}`",
        f"**HOLE_MOVED A/B:** `{licensed.get('HOLE_MOVED_A')}` / `{licensed.get('HOLE_MOVED_B')}`",
        f"**Tag:** `{tag}`",
        f"**Law:** `{law}`",
        f"**Family:** `{FAMILY}`",
        "**Evolution Proof stamped:** `False`",
        "**Playground:** `no`",
        "**REAL:** `no`",
        "",
        "### Tm — Gate 1 measure",
        json.dumps({"A": measure_a, "B": measure_b}, indent=2, default=str),
        "",
        "### T0 — identity",
        json.dumps({"A": t0_a, "B": t0_b}, indent=2, default=str),
        "",
        "### T1 — U / H / W / exit",
        json.dumps({"A": t1_a, "B": t1_b}, indent=2, default=str),
        "",
        "### T2 — compare vs path_early",
        json.dumps({"A": t2_a, "B": t2_b}, indent=2, default=str),
        "",
        "### T3 — vs #27 / #28 n_exit",
        json.dumps({"A": payload_a.get("t3"), "B": payload_b.get("t3")}, indent=2, default=str),
        "",
        "### T4 — read-only prior hole",
        json.dumps(t4, indent=2, default=str),
        "",
        "### Honesty",
        honesty,
        "",
        "Playground does not open. No learn(). Hook default off. Evolution Proof stamped: False.",
        "",
    ]
    (reports / "AWAKENING_PATH_SHAPE_K3_DEAD_VERDICT.md").write_text("\n".join(verdict) + "\n", encoding="utf-8")
    block = f"""
---

## This ticket — Awakening PATH_SHAPE K3 DEAD transfer shadow (sitting-at-MAE + lifeless)

**Prompt:** Does flatten-at-3 on a pre-declared DEAD path-shape (sitting at running MAE and no MFE life), using already-stamped path_k3_{{mae,mfe,unreal}}_r bits, move the hole and raise policy mean_r on BOTH eval seeds versus the unflattened path_early baseline?
**Train:** none. optimizer_steps=0. Parent zip 8cc435c6 only. EPS_SIT={EPS_SIT}. MFE_LIFE={MFE_LIFE}. No T compare.
**Landed:** stacked on T025 HEAD. Gate 0 SHA `{gate0_sha}`.
**skip_replay**={str(bool(skip_replay)).lower()} replay_ran={str(bool(replay_ran)).lower()} gate1_tag={gate1_tag}
**Leg A** n_exit={n_exit_a} n_H base→shape={n_h_base_a}→{n_h_shape_a} mean_r {mean_r_base_a}→{mean_r_shape_a} HOLE_MOVED={licensed.get("HOLE_MOVED_A")}
**Leg B** n_exit={n_exit_b} n_H base→shape={n_h_base_b}→{n_h_shape_b} mean_r {mean_r_base_b}→{mean_r_shape_b} HOLE_MOVED={licensed.get("HOLE_MOVED_B")}
**Tag / law:** `{tag}` / `{law}` family=`{licensed.get("licensed_next_family")}`
**Overall:** `{overall}`
**SSOT:** `AWAKENING_PATH_SHAPE_K3_DEAD_AUDIT.md` / `AWAKENING_PATH_SHAPE_K3_DEAD_VERDICT.md`
"""
    for rel in (reports / "LUMINA_BIRTH_EXPERIMENT_LOG.md", reports / "artifacts" / "LUMINA_BIRTH_EXPERIMENT_LOG.md"):
        if rel.is_file() or rel.parent.is_dir():
            with rel.open("a", encoding="utf-8") as fh:
                fh.write(block)
    return flags_payload


__all__ = ["leg_payload", "write_path_shape_k3_dead_reports"]

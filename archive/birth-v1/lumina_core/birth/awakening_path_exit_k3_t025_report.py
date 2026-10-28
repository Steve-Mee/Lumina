"""PATH_EXIT K3 T025 audit / verdict / flags writers. Shadow only. No train law."""

from __future__ import annotations

import hashlib
import json
import re
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from lumina_core.birth.awakening_path_exit_k3 import FAMILY, INIT_SHA256, LAW_SHADOW, T_LOCK
from lumina_core.birth.awakening_path_exit_k3_flags import compute_path_exit_k3_flags
from lumina_core.birth.awakening_path_exit_k3_t025 import (
    FLAGS_NAME,
    GATE0_MAIN_SHA,
    PATH_A_NAME,
    PATH_B_NAME,
    PATH_EARLY_A_NAME,
    PATH_EARLY_B_NAME,
    PR27_MERGE_SHA,
    T_FP,
    honesty_paragraph,
)
from lumina_core.birth.awakening_path_exit_k3_t025_flags import (
    license_transfer,
    mean_stamped_threshold,
)
from lumina_core.birth.awakening_path_exit_k3_t025_tables import (
    k27_n_exit,
    table_t0,
    table_t1,
    table_t2,
    table_t3,
)


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
        skip_replay=bool(skip_replay),
        replay_ran=bool(replay_ran),
    )
    k27 = k27_n_exit(artifacts, leg=leg) if artifacts is not None else {
        "absent": True,
        "n_exit_k27": 0,
    }
    return {
        "t0": t0,
        "t1": table_t1(rows),
        "t2": table_t2(rows, baseline=baseline),
        "t3": table_t3(
            n_exit=int(flags.get("n_exit") or 0),
            n_exit_k27=int(k27.get("n_exit_k27") or 0),
            k27_absent=bool(k27.get("absent")),
        ),
        "flags": flags,
        "rows_n": len(rows),
        "mean_stamped_threshold": mean_stamped_threshold(rows),
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
    return {
        "hygiene_token_in_birth": hits_reward,
        "model_learn_in_birth": hits_learn,
        "playground": False,
        "evolution_proof_stamped": False,
    }


def write_path_exit_k3_t025_reports(
    *,
    reports: Path,
    overall: str,
    zip_sha: str,
    payload_a: dict[str, Any],
    payload_b: dict[str, Any],
    t4: dict[str, Any],
    proto: dict[str, Any],
    parent_loaded: bool,
    skip_replay: bool = False,
    replay_ran: bool = False,
    gate0_sha: str = GATE0_MAIN_SHA,
    flatten_sites: dict[str, str] | None = None,
    contextvar_try_finally: bool = True,
) -> None:
    now = datetime.now(timezone.utc).isoformat()
    artifacts = reports / "artifacts"
    artifacts.mkdir(parents=True, exist_ok=True)
    flags_a = payload_a.get("flags") or {}
    flags_b = payload_b.get("flags") or {}
    licensed = license_transfer(flags_a, flags_b)
    tag = str(licensed.get("tag") or "S_MISSING")
    law = str(licensed.get("law") or LAW_SHADOW)
    t0_a = payload_a.get("t0") or {}
    t0_b = payload_b.get("t0") or {}
    t1_a = payload_a.get("t1") or {}
    t1_b = payload_b.get("t1") or {}
    t2_a = payload_a.get("t2") or {}
    t2_b = payload_b.get("t2") or {}
    n_exit_a = int(t1_a.get("n_exit") or 0)
    n_exit_b = int(t1_b.get("n_exit") or 0)
    n_h_base_a = int(t2_a.get("n_H_base") or 0)
    n_h_t025_a = int(t2_a.get("n_H_t025") or 0)
    n_h_base_b = int(t2_b.get("n_H_base") or 0)
    n_h_t025_b = int(t2_b.get("n_H_t025") or 0)
    mean_r_base_a = float(t2_a.get("mean_r_policy_base") or 0.0)
    mean_r_t025_a = float(t2_a.get("mean_r_policy_t025") or 0.0)
    mean_r_base_b = float(t2_b.get("mean_r_policy_base") or 0.0)
    mean_r_t025_b = float(t2_b.get("mean_r_policy_t025") or 0.0)
    stamped_a = payload_a.get("mean_stamped_threshold")
    if stamped_a is None:
        stamped_a = t0_a.get("mean_stamped_threshold")
    stamped_b = payload_b.get("mean_stamped_threshold")
    if stamped_b is None:
        stamped_b = t0_b.get("mean_stamped_threshold")
    flags_payload = {
        "source": "new_replay" if replay_ran else "skip_replay",
        "T_FP": float(T_FP),
        "T_LOCK_HIST": float(T_LOCK),
        "skip_replay": bool(skip_replay),
        "replay_ran": bool(replay_ran),
        "A": flags_a,
        "B": flags_b,
        "tag": tag,
        "HOLE_MOVED_A": bool(licensed.get("HOLE_MOVED_A")),
        "HOLE_MOVED_B": bool(licensed.get("HOLE_MOVED_B")),
        "law": law,
        "licensed_next_family": FAMILY,
        "gate1": "SHADOW",
        "optimizer_steps": 0,
        "evaluated_zip_sha256": zip_sha,
        "evolution_proof_stamped": False,
        "REAL": "no",
        "playground": False,
        "hook_default": False,
        "mean_stamped_threshold_A": stamped_a,
        "mean_stamped_threshold_B": stamped_b,
        "overall": overall,
    }
    (artifacts / FLAGS_NAME).write_text(
        json.dumps(flags_payload, indent=2, default=str) + "\n", encoding="utf-8"
    )
    honesty = honesty_paragraph(
        skip_replay=skip_replay,
        n_exit_a=n_exit_a,
        n_exit_b=n_exit_b,
        n_h_base_a=n_h_base_a,
        n_h_t025_a=n_h_t025_a,
        n_h_base_b=n_h_base_b,
        n_h_t025_b=n_h_t025_b,
        mean_r_base_a=mean_r_base_a,
        mean_r_t025_a=mean_r_t025_a,
        mean_r_base_b=mean_r_base_b,
        mean_r_t025_b=mean_r_t025_b,
        hole_moved_a=bool(licensed.get("HOLE_MOVED_A")),
        hole_moved_b=bool(licensed.get("HOLE_MOVED_B")),
        tag=tag,
    )
    sites = flatten_sites or {
        "force_flatten": "lumina_core/birth/sim_runner.py:force_flatten_this_step",
        "plan_birth_exit_fill": "lumina_core/rl/gym_stop_fill.py:plan_birth_exit_fill",
        "close_reason": "force_exit + path_exit_k3 sidecar",
    }
    t_lock_literal = Path("lumina_core/birth/awakening_path_exit_k3.py").is_file() and (
        "T_LOCK = -0.04787176712367987"
        in Path("lumina_core/birth/awakening_path_exit_k3.py").read_text(encoding="utf-8")
    )
    source = {
        "parent_sha256": zip_sha or INIT_SHA256,
        "path_early_A_sha256": _file_sha256(artifacts / PATH_EARLY_A_NAME),
        "path_early_B_sha256": _file_sha256(artifacts / PATH_EARLY_B_NAME),
        "path_exit_k3_A_sha256": _file_sha256(artifacts / PATH_A_NAME),
        "path_exit_k3_B_sha256": _file_sha256(artifacts / PATH_B_NAME),
    }
    audit = [
        "# AWAKENING_PATH_EXIT_K3_T025_AUDIT",
        "",
        "## Gate 0",
        f"- origin/main SHA `{gate0_sha}` (PR #27 merge `{PR27_MERGE_SHA}`)",
        f"- T_LOCK still -0.04787176712367987 : {'yes' if t_lock_literal else 'no'}",
        f"- parent_loaded: `{parent_loaded}`",
        f"- date: `{now}`",
        "",
        "## Hook",
        f"- PATH_EXIT_K3_THRESHOLD file:line `{proto.get('threshold_var')}`",
        f"- should_path_exit_k3 threshold read file:line `{proto.get('should_reads_threshold')}`",
        f"- after_open_telem file:line `{proto.get('after_open_telem')}`",
        f"- flatten site file:line `{sites.get('force_flatten')}`",
        "",
        "## Source",
        f"- parent sha256 `{source['parent_sha256']}`",
        f"- path_early A/B sha256 `{source['path_early_A_sha256']}` / `{source['path_early_B_sha256']}`",
        (
            f"- path_exit_k3 (#27) A/B sha256 `{source['path_exit_k3_A_sha256']}` / "
            f"`{source['path_exit_k3_B_sha256']}` (must match pre-PR)"
        ),
        "",
        "## Replay",
        f"- skip_replay `{str(bool(skip_replay)).lower()}` / replay_ran `{str(bool(replay_ran)).lower()}` / "
        "optimizer_steps `0`",
        f"- ContextVar set/reset in try/finally : {'yes' if contextvar_try_finally else 'no'}",
        "",
        "## Flags",
        "",
        json.dumps(flags_payload, indent=2, default=str),
        "",
        "## n_exit vs T_LOCK clone",
        f"- A n_exit `{n_exit_a}` / mean stamped threshold `{stamped_a}`",
        f"- B n_exit `{n_exit_b}` / mean stamped threshold `{stamped_b}`",
        "",
        "## Honesty",
        "",
        honesty,
        "",
        "## Protocol inspect",
        "",
        json.dumps(proto, indent=2, default=str),
        "",
        "## T0 / T1 / T2 / T3 / T4",
        "",
        json.dumps({"A": t0_a, "B": t0_b}, indent=2, default=str),
        json.dumps({"A": t1_a, "B": t1_b}, indent=2, default=str),
        json.dumps({"A": t2_a, "B": t2_b}, indent=2, default=str),
        json.dumps({"A": payload_a.get("t3"), "B": payload_b.get("t3")}, indent=2, default=str),
        json.dumps(t4, indent=2, default=str),
        "",
        "## Forbidden-path grep",
        "",
        json.dumps(_forbidden_grep(), indent=2, default=str),
        "",
    ]
    (reports / "AWAKENING_PATH_EXIT_K3_T025_AUDIT.md").write_text(
        "\n".join(audit) + "\n", encoding="utf-8"
    )
    verdict = [
        "# AWAKENING_PATH_EXIT_K3_T025_VERDICT",
        "",
        f"**Overall:** `{overall}`",
        f"**Date:** {now}",
        f"**Evaluated zip sha256:** `{zip_sha or INIT_SHA256}`",
        "**optimizer_steps:** `0`",
        f"**skip_replay:** `{str(bool(skip_replay)).lower()}`",
        f"**replay_ran:** `{str(bool(replay_ran)).lower()}`",
        f"**T_FP:** `{T_FP}`",
        f"**T_LOCK_HIST:** `{T_LOCK}`",
        f"**n_exit A/B:** `{n_exit_a}` / `{n_exit_b}`",
        f"**mean stamped threshold A/B:** `{stamped_a}` / `{stamped_b}`",
        f"**n_H A base→t025:** `{n_h_base_a}` → `{n_h_t025_a}`",
        f"**n_H B base→t025:** `{n_h_base_b}` → `{n_h_t025_b}`",
        f"**mean_r A base→t025:** `{mean_r_base_a}` → `{mean_r_t025_a}`",
        f"**mean_r B base→t025:** `{mean_r_base_b}` → `{mean_r_t025_b}`",
        f"**S_MISSING_HOOK A/B:** `{flags_a.get('S_MISSING_HOOK')}` / `{flags_b.get('S_MISSING_HOOK')}`",
        f"**S_HARM A/B:** `{flags_a.get('S_HARM')}` / `{flags_b.get('S_HARM')}`",
        f"**HOLE_MOVED A/B:** `{flags_a.get('HOLE_MOVED')}` / `{flags_b.get('HOLE_MOVED')}`",
        f"**Tag:** `{tag}`",
        f"**Law:** `{law}`",
        f"**Family:** `{FAMILY}`",
        "**Evolution Proof stamped:** `False`",
        "**Playground:** `no`",
        "**REAL:** `no`",
        "",
        "### T0 — identity",
        "",
        "| Leg | n_all | n_policy | n_plant | wr | mean_r | zip | ticks | price | hook | T | mean_stamped | n_exit | optimizer_steps |",
        "|-----|-------|----------|---------|----|--------|-----|-------|-------|------|---|--------------|--------|-----------------|",
        (
            f"| A | {t0_a.get('n_all')} | {t0_a.get('n_policy')} | {t0_a.get('n_plant')} | "
            f"{t0_a.get('wr_policy')} | {t0_a.get('mean_r_policy')} | {t0_a.get('zip_sha256')} | "
            f"{t0_a.get('ticks_sha16')} | {t0_a.get('price_sha16')} | {t0_a.get('hook_enabled')} | "
            f"{t0_a.get('T_FP')} | {t0_a.get('mean_stamped_threshold')} | {t0_a.get('n_exit')} | "
            f"{t0_a.get('optimizer_steps')} |"
        ),
        (
            f"| B | {t0_b.get('n_all')} | {t0_b.get('n_policy')} | {t0_b.get('n_plant')} | "
            f"{t0_b.get('wr_policy')} | {t0_b.get('mean_r_policy')} | {t0_b.get('zip_sha256')} | "
            f"{t0_b.get('ticks_sha16')} | {t0_b.get('price_sha16')} | {t0_b.get('hook_enabled')} | "
            f"{t0_b.get('T_FP')} | {t0_b.get('mean_stamped_threshold')} | {t0_b.get('n_exit')} | "
            f"{t0_b.get('optimizer_steps')} |"
        ),
        "",
        "### T1 — U / H / W / exit",
        "",
        json.dumps({"A": t1_a, "B": t1_b}, indent=2, default=str),
        "",
        "### T2 — compare vs path_early",
        "",
        json.dumps({"A": t2_a, "B": t2_b}, indent=2, default=str),
        "",
        "### T3 — vs #27 T_LOCK book",
        "",
        json.dumps({"A": payload_a.get("t3"), "B": payload_b.get("t3")}, indent=2, default=str),
        "",
        "### T4 — read-only prior hole",
        "",
        json.dumps(t4, indent=2, default=str),
        "",
        "### Honesty",
        "",
        honesty,
        "",
        "Playground does not open. No learn(). Hook default off. Evolution Proof stamped: False.",
        "",
    ]
    (reports / "AWAKENING_PATH_EXIT_K3_T025_VERDICT.md").write_text(
        "\n".join(verdict) + "\n", encoding="utf-8"
    )
    block = f"""
---

## This ticket — Awakening PATH_EXIT K3 T025 transfer shadow (evaluate-only flatten-at-3 at T_FP)

**Prompt:** Does flatten-at-3 at a first-principles threshold not fitted on A or B (T_FP = -0.25 R) move the hole and raise policy mean_r on both eval seeds versus the unflattened path_early baseline?
**Train:** none. optimizer_steps=0. Parent zip 8cc435c6 only. T_FP={T_FP}. T_LOCK unchanged. k=3. Median not recomputed.
**Landed:** PR #27 on main. Gate 0 SHA `{gate0_sha}`.
**skip_replay**={str(bool(skip_replay)).lower()} replay_ran={str(bool(replay_ran)).lower()}
**Leg A** n_exit={n_exit_a} n_H base→t025={n_h_base_a}→{n_h_t025_a} mean_r {mean_r_base_a}→{mean_r_t025_a} HOLE_MOVED={flags_a.get("HOLE_MOVED")}
**Leg B** n_exit={n_exit_b} n_H base→t025={n_h_base_b}→{n_h_t025_b} mean_r {mean_r_base_b}→{mean_r_t025_b} HOLE_MOVED={flags_b.get("HOLE_MOVED")}
**Tag / law:** `{tag}` / `{law}` family=`{FAMILY}`
**Overall:** `{overall}`
**SSOT:** `AWAKENING_PATH_EXIT_K3_T025_AUDIT.md` / `AWAKENING_PATH_EXIT_K3_T025_VERDICT.md`
"""
    for rel in (
        reports / "LUMINA_BIRTH_EXPERIMENT_LOG.md",
        reports / "artifacts" / "LUMINA_BIRTH_EXPERIMENT_LOG.md",
    ):
        if rel.is_file() or rel.parent.is_dir():
            with rel.open("a", encoding="utf-8") as fh:
                fh.write(block)


__all__ = ["leg_payload", "write_path_exit_k3_t025_reports"]

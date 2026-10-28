"""PATH_EXIT K3 audit / verdict / flags writers. Shadow only. No train law."""

from __future__ import annotations

import json
import re
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from lumina_core.birth.awakening_path_exit_k3 import (
    FAMILY,
    GATE0_MAIN_SHA,
    INIT_SHA256,
    LAW_SHADOW,
    PR26_MERGE_SHA,
    T_LOCK,
    honesty_paragraph,
)
from lumina_core.birth.awakening_path_exit_k3_flags import (
    compute_path_exit_k3_flags,
    empty_baseline,
    license_from_a,
)
from lumina_core.birth.awakening_path_exit_k3_tables import (
    table_t0,
    table_t1,
    table_t2,
    table_t3,
    table_t5,
)


def leg_payload(
    *,
    rows: list[dict[str, Any]],
    zip_sha: str,
    ticks_sha16: str,
    price_sha16_value: str,
    optimizer_steps: int,
    hook_enabled: bool,
    baseline: dict[str, Any] | None,
    baseline_rows: list[dict[str, Any]] | None,
    skip_replay: bool = False,
    replay_ran: bool = False,
    paper_drop_h: int = 43,
    paper_drop_w: int = 12,
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
    return {
        "t0": t0,
        "t1": table_t1(rows),
        "t2": table_t2(rows, baseline=baseline),
        "t3": table_t3(
            n_exit=int(flags.get("n_exit") or 0),
            paper_drop_h=int(paper_drop_h),
            paper_drop_w=int(paper_drop_w),
        ),
        "t5": table_t5(rows, baseline_rows),
        "flags": flags,
        "rows_n": len(rows),
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


def write_path_exit_k3_reports(
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
) -> None:
    now = datetime.now(timezone.utc).isoformat()
    (reports / "artifacts").mkdir(parents=True, exist_ok=True)
    flags_a = payload_a.get("flags") or {}
    flags_b = payload_b.get("flags") or {}
    licensed = license_from_a(flags_a, flags_b)
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
    n_h_base = int(t2_a.get("n_H_base") or 0)
    n_h_shadow = int(t2_a.get("n_H_shadow") or 0)
    flags_payload = {
        "skip_replay": bool(skip_replay),
        "replay_ran": bool(replay_ran),
        "A": flags_a,
        "B": flags_b,
        "tag": tag,
        "law": law,
        "licensed_next_family": FAMILY,
        "gate1": law,
        "T_LOCK": T_LOCK,
        "optimizer_steps": 0,
        "evaluated_zip_sha256": zip_sha,
        "evolution_proof_stamped": False,
        "REAL": "no",
        "playground": False,
        "hook_default": False,
        "overall": overall,
    }
    (reports / "artifacts" / "awakening_path_exit_k3_flags.json").write_text(
        json.dumps(flags_payload, indent=2, default=str) + "\n", encoding="utf-8"
    )
    honesty = honesty_paragraph(
        skip_replay=skip_replay,
        n_exit_a=n_exit_a,
        n_exit_b=n_exit_b,
        n_h_base_a=n_h_base,
        n_h_shadow_a=n_h_shadow,
        tag=tag,
    )
    sites = flatten_sites or {
        "force_flatten": "lumina_core/birth/sim_runner.py:force_flatten_this_step",
        "plan_birth_exit_fill": "lumina_core/rl/gym_stop_fill.py:plan_birth_exit_fill",
        "close_reason": "force_exit + path_exit_k3 sidecar",
    }
    audit = [
        "# AWAKENING_PATH_EXIT_K3_AUDIT",
        "",
        "## Gate 0",
        f"- origin/main SHA `{gate0_sha}` (PR #26 merge `{PR26_MERGE_SHA}`)",
        f"- parent_loaded: `{parent_loaded}`",
        f"- date: `{now}`",
        "",
        "## Flatten path (existing close physics)",
        "",
        json.dumps(sites, indent=2),
        "",
        f"- T_LOCK `{T_LOCK}` (PATH_EARLY / PATH_UNREAL_K3 leg A threshold). Not recomputed.",
        "- k=3 only. Plant / FORCE_OPEN never flattened.",
        "",
        "## Protocol inspect",
        "",
        json.dumps(proto, indent=2, default=str),
        "",
        "## Flags",
        "",
        json.dumps(flags_payload, indent=2, default=str),
        "",
        "## Honesty",
        "",
        honesty,
        "",
        "## T0 / T1 / T2 / T3 / T4 / T5",
        "",
        json.dumps({"A": t0_a, "B": t0_b}, indent=2, default=str),
        json.dumps({"A": t1_a, "B": t1_b}, indent=2, default=str),
        json.dumps({"A": t2_a, "B": t2_b}, indent=2, default=str),
        json.dumps({"A": payload_a.get("t3"), "B": payload_b.get("t3")}, indent=2, default=str),
        json.dumps(t4, indent=2, default=str),
        json.dumps({"A": payload_a.get("t5"), "B": payload_b.get("t5")}, indent=2, default=str),
        "",
        "## Forbidden-path grep",
        "",
        json.dumps(_forbidden_grep(), indent=2, default=str),
        "",
    ]
    (reports / "AWAKENING_PATH_EXIT_K3_AUDIT.md").write_text("\n".join(audit) + "\n", encoding="utf-8")
    verdict = [
        "# AWAKENING_PATH_EXIT_K3_VERDICT",
        "",
        f"**Overall:** `{overall}`",
        f"**Date:** {now}",
        f"**Evaluated zip sha256:** `{zip_sha or INIT_SHA256}`",
        "**optimizer_steps:** `0`",
        f"**skip_replay:** `{str(bool(skip_replay)).lower()}`",
        f"**replay_ran:** `{str(bool(replay_ran)).lower()}`",
        f"**T_LOCK:** `{T_LOCK}`",
        f"**n_exit A/B:** `{n_exit_a}` / `{n_exit_b}`",
        f"**n_H A base→shadow:** `{n_h_base}` → `{n_h_shadow}`",
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
        "| Leg | n_all | n_policy | n_plant | wr | mean_r | hook | n_exit | optimizer_steps |",
        "|-----|-------|----------|---------|----|--------|------|--------|-----------------|",
        (
            f"| A | {t0_a.get('n_all')} | {t0_a.get('n_policy')} | {t0_a.get('n_plant')} | "
            f"{t0_a.get('wr_policy')} | {t0_a.get('mean_r_policy')} | {t0_a.get('hook_enabled')} | "
            f"{t0_a.get('n_exit')} | {t0_a.get('optimizer_steps')} |"
        ),
        (
            f"| B | {t0_b.get('n_all')} | {t0_b.get('n_policy')} | {t0_b.get('n_plant')} | "
            f"{t0_b.get('wr_policy')} | {t0_b.get('mean_r_policy')} | {t0_b.get('hook_enabled')} | "
            f"{t0_b.get('n_exit')} | {t0_b.get('optimizer_steps')} |"
        ),
        "",
        "### T1 — U / H / W / exit",
        "",
        f"- A H `{t1_a.get('H')}` W `{t1_a.get('W')}` n_exit={n_exit_a} "
        f"mean_r_exit={t1_a.get('mean_r_exit')} wr_exit={t1_a.get('wr_exit')}",
        f"- B H `{t1_b.get('H')}` W `{t1_b.get('W')}` n_exit={n_exit_b} "
        f"mean_r_exit={t1_b.get('mean_r_exit')} wr_exit={t1_b.get('wr_exit')}",
        "",
        "### T2 — compare vs path_early",
        "",
        json.dumps({"A": t2_a, "B": t2_b}, indent=2, default=str),
        "",
        "### T3 — paper vs live n_exit",
        "",
        json.dumps({"A": payload_a.get("t3"), "B": payload_b.get("t3")}, indent=2, default=str),
        "",
        "### T4 — read-only prior hole",
        "",
        json.dumps(t4, indent=2, default=str),
        "",
        "### T5 — who got flattened",
        "",
        json.dumps({"A": payload_a.get("t5"), "B": payload_b.get("t5")}, indent=2, default=str),
        "",
        "### Honesty",
        "",
        honesty,
        "",
        "Playground does not open. No learn(). Hook default off. Evolution Proof stamped: False.",
        "",
    ]
    (reports / "AWAKENING_PATH_EXIT_K3_VERDICT.md").write_text("\n".join(verdict) + "\n", encoding="utf-8")
    block = f"""
---

## This ticket — Awakening PATH_EXIT K3 shadow (evaluate-only flatten-at-3)

**Prompt:** If we flatten a policy NEUTRAL-open still open at bar 3 when path_k3_unreal_r <= T_LOCK, does the evaluate-only book move the hole (n_H / mean_r) versus the frozen parent path without peeking the rest of the trade and without changing exam dollars?
**Train:** none. optimizer_steps=0. Parent zip 8cc435c6 only. T_LOCK={T_LOCK}. k=3. Median not recomputed.
**Landed:** PR #26 on main. Gate 0 SHA `{gate0_sha}`.
**skip_replay**={str(bool(skip_replay)).lower()} replay_ran={str(bool(replay_ran)).lower()}
**Leg A** n_exit={n_exit_a} n_H base→shadow={n_h_base}→{n_h_shadow} wr_policy={t0_a.get("wr_policy")} tag={flags_a.get("tag")}
**Leg B** n_exit={n_exit_b} n_H={t1_b.get("n_H")} wr_policy={t0_b.get("wr_policy")} tag={flags_b.get("tag")}
**Tag / law:** `{tag}` / `{law}` family=`{FAMILY}`
**Overall:** `{overall}`
**SSOT:** `AWAKENING_PATH_EXIT_K3_AUDIT.md` / `AWAKENING_PATH_EXIT_K3_VERDICT.md`
"""
    for rel in (
        reports / "LUMINA_BIRTH_EXPERIMENT_LOG.md",
        reports / "artifacts" / "LUMINA_BIRTH_EXPERIMENT_LOG.md",
    ):
        if rel.is_file() or rel.parent.is_dir():
            with rel.open("a", encoding="utf-8") as fh:
                fh.write(block)


__all__ = ["empty_baseline", "leg_payload", "write_path_exit_k3_reports"]

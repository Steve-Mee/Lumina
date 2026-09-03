"""PATH_UNREAL_K3 audit / verdict / flags writers. Measure-only, no train law."""

from __future__ import annotations

import json
import re
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from lumina_core.birth.awakening_path_early_flags import FAMILY_H_NONE
from lumina_core.birth.awakening_path_unreal_k3 import (
    GATE0_MAIN_SHA,
    INIT_SHA256,
    LOCKED_COV_H_A,
    LOCKED_COV_W_A,
    LOCKED_LIFT_A,
    PR25_MERGE_SHA,
    P_K3_UNREAL_RED,
    SOURCE_PATH_EARLY_JSONL,
    WORKER_TEST_TOUCHED,
    honesty_paragraph,
)
from lumina_core.birth.awakening_path_unreal_k3_flags import (
    CANDIDATE_NAMES,
    compute_path_unreal_k3_flags,
    license_from_ab_k3,
)
from lumina_core.birth.awakening_path_unreal_k3_tables import (
    table_t0,
    table_t1,
    table_t1b,
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
    skip_replay: bool = False,
    replay_ran: bool = False,
    source: str = SOURCE_PATH_EARLY_JSONL,
    source_a_sha256: str = "",
    source_b_sha256: str = "",
) -> dict[str, Any]:
    flags = compute_path_unreal_k3_flags(rows)
    t0 = table_t0(
        rows,
        zip_sha256=zip_sha,
        ticks_sha16=ticks_sha16,
        price_sha16_value=price_sha16_value,
        optimizer_steps=int(optimizer_steps),
        skip_replay=bool(skip_replay),
        replay_ran=bool(replay_ran),
        source=source,
        source_a_sha256=source_a_sha256,
        source_b_sha256=source_b_sha256,
    )
    return {
        "t0": t0,
        "t1": table_t1(rows),
        "t1b": table_t1b(rows),
        "t2": table_t2(rows),
        "t3": table_t3(rows),
        "t5": table_t5(rows),
        "flags": flags,
        "rows_n": len(rows),
    }


def _md_cell(cell: dict[str, Any]) -> str:
    return f"n={cell.get('n')} wr={cell.get('wr')} mean_r={cell.get('mean_r')} mean_usd={cell.get('mean_usd')}"


def _t2_table(grid: dict[str, Any]) -> list[str]:
    lines = [
        "| P | threshold | n_defined | missing_share | cov_H | cov_W | lift | S_SPLIT | S_HARM | S_THIN | missing |",
        "|---|-----------|-----------|---------------|-------|-------|------|---------|--------|--------|---------|",
    ]
    for name in CANDIDATE_NAMES:
        row = grid.get(name) or {}
        lines.append(
            f"| `{name}` | {row.get('threshold')} | {row.get('n_defined')} | {row.get('missing_share')} | "
            f"{row.get('cov_H')} | {row.get('cov_W')} | {row.get('lift')} | "
            f"{row.get('S_SPLIT')} | {row.get('S_HARM')} | {row.get('S_THIN')} | {row.get('missing')} |"
        )
    return lines


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
        "flatten_at_3": False,
        "playground": False,
    }


def write_path_unreal_k3_reports(
    *,
    reports: Path,
    overall: str,
    zip_sha: str,
    payload_a: dict[str, Any],
    payload_b: dict[str, Any],
    t4: dict[str, Any],
    proto: dict[str, Any],
    parent_loaded: bool,
    source: str,
    source_a_sha256: str,
    source_b_sha256: str,
    missing_share_a: float,
    path_chosen: str,
    skip_replay: bool = False,
    replay_ran: bool = False,
    gate0_sha: str = GATE0_MAIN_SHA,
) -> None:
    now = datetime.now(timezone.utc).isoformat()
    (reports / "artifacts").mkdir(parents=True, exist_ok=True)
    flags_a = payload_a.get("flags") or {}
    flags_b = payload_b.get("flags") or {}
    licensed = license_from_ab_k3(flags_a, flags_b)
    tag = str(licensed.get("tag") or "S_NONE")
    winning = str(licensed.get("winning_P") or "none")
    family = str(licensed.get("licensed_next_family") or FAMILY_H_NONE)
    t0_a = payload_a.get("t0") or {}
    t0_b = payload_b.get("t0") or {}
    t1_a = payload_a.get("t1") or {}
    t1_b = payload_b.get("t1") or {}
    t2_a = payload_a.get("t2") or {}
    cand_a = (flags_a.get("candidates") or {}).get(P_K3_UNREAL_RED) or {}
    n_u3_a = int(t1_a.get("n_Uk3") or 0)
    n_u3_b = int(t1_b.get("n_Uk3") or 0)
    flags_payload = {
        "source": source,
        "source_A_sha256": source_a_sha256,
        "source_B_sha256": source_b_sha256,
        "skip_replay": bool(skip_replay),
        "replay_ran": bool(replay_ran),
        "A": flags_a,
        "B": flags_b,
        "tag": tag,
        "winning_P": winning,
        "licensed_next_family": family,
        "gate1": "NONE",
        "optimizer_steps": 0,
        "evaluated_zip_sha256": zip_sha,
        "evolution_proof_stamped": False,
        "REAL": "no",
        "overall": overall,
    }
    (reports / "artifacts" / "path_unreal_k3_flags.json").write_text(
        json.dumps(flags_payload, indent=2, default=str) + "\n", encoding="utf-8"
    )
    honesty = honesty_paragraph(
        source=source,
        skip_replay=skip_replay,
        replay_ran=replay_ran,
        n_u_a=int(t1_a.get("n_U") or 0),
        n_u_b=int(t1_b.get("n_U") or 0),
        n_u3_a=n_u3_a,
        n_u3_b=n_u3_b,
        tag=tag,
        family=family,
    )
    audit = [
        "# AWAKENING_PATH_UNREAL_K3_AUDIT",
        "",
        "## Gate 0",
        f"- origin/main SHA `{gate0_sha}`",
        f"- PR #25 merge SHA `{PR25_MERGE_SHA}`",
        f"- worker-test touched: {'yes' if WORKER_TEST_TOUCHED else 'no'}",
        f"- parent_loaded: `{parent_loaded}`",
        f"- date: `{now}`",
        "",
        "## Source",
        f"- path_early A/B sha256 `{source_a_sha256}` / `{source_b_sha256}`",
        f"- missing_share k=3 A `{missing_share_a}`",
        f"- path chosen: {path_chosen}",
        f"- parent zip sha256 `{zip_sha or INIT_SHA256}`",
        f"- skip_replay `{str(bool(skip_replay)).lower()}` replay_ran `{str(bool(replay_ran)).lower()}`",
        "",
        "## Protocol inspect",
        "",
        json.dumps(proto, indent=2, default=str),
        "",
        "## Flags",
        "",
        json.dumps(flags_payload, indent=2, default=str),
        "",
        "## Reproduction vs PATH_EARLY A P_K3_UNREAL_RED",
        f"- lift `{cand_a.get('lift')}` (locked `{LOCKED_LIFT_A}`)",
        f"- cov_H `{cand_a.get('cov_H')}` (locked `{LOCKED_COV_H_A}`)",
        f"- cov_W `{cand_a.get('cov_W')}` (locked `{LOCKED_COV_W_A}`)",
        f"- n_Uk3 `{n_u3_a}` (locked 117)",
        "",
        "## Honesty",
        "",
        honesty,
        "",
        "- law NONE, flatten no, Playground no, Proof false",
        "",
        "## T0 / T1 / T1b / T2 / T3 / T4 / T5",
        "",
        json.dumps({"A": t0_a, "B": t0_b}, indent=2, default=str),
        json.dumps({"A": t1_a, "B": t1_b}, indent=2, default=str),
        json.dumps({"A": payload_a.get("t1b"), "B": payload_b.get("t1b")}, indent=2, default=str),
        json.dumps({"A": payload_a.get("t2"), "B": payload_b.get("t2")}, indent=2, default=str),
        json.dumps({"A": payload_a.get("t3"), "B": payload_b.get("t3")}, indent=2, default=str),
        json.dumps(t4, indent=2, default=str),
        json.dumps({"A": payload_a.get("t5"), "B": payload_b.get("t5")}, indent=2, default=str),
        "",
        "## Forbidden-path grep",
        "",
        json.dumps(_forbidden_grep(), indent=2, default=str),
        "",
    ]
    (reports / "AWAKENING_PATH_UNREAL_K3_AUDIT.md").write_text("\n".join(audit) + "\n", encoding="utf-8")
    verdict = [
        "# AWAKENING_PATH_UNREAL_K3_VERDICT",
        "",
        f"**Overall:** `{overall}`",
        f"**Date:** {now}",
        f"**Source:** `{source}`",
        f"**Evaluated zip sha256:** `{zip_sha or INIT_SHA256}`",
        "**optimizer_steps:** `0`",
        f"**skip_replay:** `{str(bool(skip_replay)).lower()}`",
        f"**replay_ran:** `{str(bool(replay_ran)).lower()}`",
        f"**S_MISSING_U A/B:** `{flags_a.get('S_MISSING_U')}` / `{flags_b.get('S_MISSING_U')}`",
        f"**S_MISSING_PATH A/B:** `{flags_a.get('S_MISSING_PATH')}` / `{flags_b.get('S_MISSING_PATH')}`",
        f"**S_THIN A/B:** `{flags_a.get('S_THIN')}` / `{flags_b.get('S_THIN')}`",
        f"**Winning P A/B:** `{flags_a.get('winning_P')}` / `{flags_b.get('winning_P')}`",
        f"**Tag:** `{tag}`",
        f"**Licensed next family:** `{family}`",
        "**Gate 1 law:** `NONE`",
        "**Evolution Proof stamped:** `False`",
        "**REAL:** `no`",
        "",
        "### T0 — source identity",
        "",
        "| Leg | source | n_all | n_policy | wr_policy | optimizer_steps | skip_replay | replay_ran |",
        "|-----|--------|-------|----------|-----------|-----------------|-------------|------------|",
        (
            f"| A | {t0_a.get('source')} | {t0_a.get('n_all')} | {t0_a.get('n_policy')} | "
            f"{t0_a.get('wr_policy')} | {t0_a.get('optimizer_steps')} | "
            f"{t0_a.get('skip_replay')} | {t0_a.get('replay_ran')} |"
        ),
        (
            f"| B | {t0_b.get('source')} | {t0_b.get('n_all')} | {t0_b.get('n_policy')} | "
            f"{t0_b.get('wr_policy')} | {t0_b.get('optimizer_steps')} | "
            f"{t0_b.get('skip_replay')} | {t0_b.get('replay_ran')} |"
        ),
        "",
        f"- source_A_sha256 `{source_a_sha256}`",
        f"- source_B_sha256 `{source_b_sha256}`",
        "",
        "### T1 — universe U / H / W and U_3",
        "",
        f"- A U: `{_md_cell(t1_a.get('U') or {})}` n_U={t1_a.get('n_U')} "
        f"n_Uk3={t1_a.get('n_Uk3')} n_Hk3={t1_a.get('n_Hk3')} n_Wk3={t1_a.get('n_Wk3')} "
        f"n_died_before_3={t1_a.get('n_died_before_3')}",
        f"- A H: `{_md_cell(t1_a.get('H') or {})}`",
        f"- A W: `{_md_cell(t1_a.get('W') or {})}`",
        f"- B U: `{_md_cell(t1_b.get('U') or {})}` n_U={t1_b.get('n_U')} "
        f"n_Uk3={t1_b.get('n_Uk3')} n_Hk3={t1_b.get('n_Hk3')} n_Wk3={t1_b.get('n_Wk3')} "
        f"n_died_before_3={t1_b.get('n_died_before_3')}",
        f"- B H: `{_md_cell(t1_b.get('H') or {})}`",
        f"- B W: `{_md_cell(t1_b.get('W') or {})}`",
        "",
        "### T1b — path_k3_unreal_r plus contrast keys",
        "",
        json.dumps({"A": payload_a.get("t1b"), "B": payload_b.get("t1b")}, indent=2, default=str),
        "",
        "### T2 — single candidate P_K3_UNREAL_RED",
        "",
        "#### Leg A",
        "",
        *_t2_table(t2_a),
        "",
        "#### Leg B",
        "",
        *_t2_table(payload_b.get("t2") or {}),
        "",
        "### T3 — paper counterfactual",
        "",
        f"- A: `{payload_a.get('t3')}`",
        f"- B: `{payload_b.get('t3')}`",
        "",
        "### T4 — read-only contrast (policy hole n / mean_r)",
        "",
        json.dumps(t4, indent=2, default=str),
        "",
        "### T5 — opposite-tail READ_ONLY_FLIP",
        "",
        json.dumps({"A": payload_a.get("t5"), "B": payload_b.get("t5")}, indent=2, default=str),
        "",
        "### Honesty",
        "",
        honesty,
        "",
        "Playground does not open. No learn(). Gate 1 law: NONE. Flatten-at-3 shipped: no.",
        "",
    ]
    (reports / "AWAKENING_PATH_UNREAL_K3_VERDICT.md").write_text("\n".join(verdict) + "\n", encoding="utf-8")
    block = f"""
---

## This ticket — Awakening PATH_UNREAL_K3 autopsy (measure-only)

**Prompt:** Among policy NEUTRAL opens still open at locked k=3, does path_k3_unreal_r separate hole from +R?
**Train:** none. optimizer_steps=0. Parent zip 8cc435c6 only. Candidate set size 1: P_K3_UNREAL_RED.
**Landed:** PR #25 on main. Gate 0 SHA `{gate0_sha}`.
**Source:** `{source}` skip_replay={str(bool(skip_replay)).lower()} replay_ran={str(bool(replay_ran)).lower()}
**Leg A** n_U={t1_a.get("n_U")} n_H={t1_a.get("n_H")} n_W={t1_a.get("n_W")} U_3={n_u3_a} wr_policy={t0_a.get("wr_policy")} tag={flags_a.get("tag")} winning_P={flags_a.get("winning_P")}.
**Leg B** n_U={t1_b.get("n_U")} n_H={t1_b.get("n_H")} n_W={t1_b.get("n_W")} U_3={n_u3_b} wr_policy={t0_b.get("wr_policy")} tag={flags_b.get("tag")} winning_P={flags_b.get("winning_P")}.
**Tag / winning P:** `{tag}` / `{winning}` licensed=`{family}`
**Overall:** `{overall}`
**SSOT:** `AWAKENING_PATH_UNREAL_K3_AUDIT.md` / `AWAKENING_PATH_UNREAL_K3_VERDICT.md`
"""
    for rel in (
        reports / "LUMINA_BIRTH_EXPERIMENT_LOG.md",
        reports / "artifacts" / "LUMINA_BIRTH_EXPERIMENT_LOG.md",
    ):
        if rel.is_file() or rel.parent.is_dir():
            with rel.open("a", encoding="utf-8") as fh:
                fh.write(block)


__all__ = ["leg_payload", "write_path_unreal_k3_reports"]

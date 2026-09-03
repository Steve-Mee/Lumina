"""PATH_EARLY audit / verdict / flags writers. Measure-only, no train law."""

from __future__ import annotations

import json
import re
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from lumina_core.birth.awakening_path_early import (
    INIT_SHA256,
    compute_path_early_flags,
    honesty_paragraph,
    license_from_ab,
)
from lumina_core.birth.awakening_path_early_flags import FAMILY_H_NONE, K_LOCKED, PATH_CANDIDATE_NAMES
from lumina_core.birth.awakening_path_early_path import PATH_STASH_ATTR_PATHS
from lumina_core.birth.awakening_path_early_tables import (
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
) -> dict[str, Any]:
    flags = compute_path_early_flags(rows)
    t0 = table_t0(
        rows,
        zip_sha256=zip_sha,
        ticks_sha16=ticks_sha16,
        price_sha16_value=price_sha16_value,
        optimizer_steps=int(optimizer_steps),
        skip_replay=bool(skip_replay),
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
    for name in PATH_CANDIDATE_NAMES:
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
    early_src = (birth / "awakening_path_early.py").read_text(encoding="utf-8")
    run_src = (birth / "awakening_path_early_run.py").read_text(encoding="utf-8")
    flatten = "flatten" + "-at-k" in early_src or "PATH_EXIT" in run_src and "implement" in run_src
    return {
        "hygiene_token_in_birth": hits_reward,
        "model_learn_in_birth": hits_learn,
        "path_exit_controller": flatten,
    }


def _paper_mae_costume(t1b: dict[str, Any]) -> str:
    notes: list[str] = []
    for key in ("path_k3_mae_r", "path_k5_mae_r"):
        cell = t1b.get(key) or {}
        h_med = (cell.get("H_k") or {}).get("median")
        w_med = (cell.get("W_k") or {}).get("median")
        if h_med is None or w_med is None:
            continue
        if float(h_med) < -3.0 and float(w_med) < -3.0:
            notes.append(
                f"{key} paper median H={h_med} W={w_med} (orders past −1 R on both). "
                "Costume risk; candidate not dropped."
            )
    if not notes:
        return "Paper MAE at locked k is recorded as a diagnostic split only. No tax. No flatten."
    return " ".join(notes)


def write_path_early_reports(
    *,
    reports: Path,
    overall: str,
    zip_sha: str,
    payload_a: dict[str, Any],
    payload_b: dict[str, Any],
    t4: dict[str, Any],
    proto: dict[str, Any],
    parent_loaded: bool,
    gate0_sha: str,
    fixture_a: dict[str, Any] | None = None,
    fixture_b: dict[str, Any] | None = None,
    skip_replay: bool = False,
) -> None:
    now = datetime.now(timezone.utc).isoformat()
    (reports / "artifacts").mkdir(parents=True, exist_ok=True)
    flags_a = payload_a.get("flags") or {}
    flags_b = payload_b.get("flags") or {}
    licensed = license_from_ab(flags_a, flags_b)
    tag = str(licensed.get("tag") or "S_NONE")
    winning = str(licensed.get("winning_P") or "none")
    family = str(licensed.get("licensed_next_family") or FAMILY_H_NONE)
    t0_a = payload_a.get("t0") or {}
    t0_b = payload_b.get("t0") or {}
    t1_a = payload_a.get("t1") or {}
    t1_b = payload_b.get("t1") or {}
    t2_a = payload_a.get("t2") or {}
    k_a = t1_a.get("k") or {}
    flags_payload = {
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
        "skip_replay": bool(skip_replay),
    }
    (reports / "artifacts" / "awakening_path_early_flags.json").write_text(
        json.dumps(flags_payload, indent=2, default=str) + "\n", encoding="utf-8"
    )
    stash_lines = ["| key | extraction path |", "|-----|-----------------|"]
    for key, path in PATH_STASH_ATTR_PATHS.items():
        stash_lines.append(f"| `{key}` | `{path}` |")
    fix_a = fixture_a or {}
    fix_b = fixture_b or {}
    n_u3_a = int((k_a.get("3") or {}).get("n_Uk") or 0)
    n_u5_a = int((k_a.get("5") or {}).get("n_Uk") or 0)
    honesty = honesty_paragraph(
        tag,
        winning,
        skip_replay=skip_replay,
        n_u_a=int(t1_a.get("n_U") or 0),
        n_u_b=int(t1_b.get("n_U") or 0),
        n_u3_a=n_u3_a,
        n_u5_a=n_u5_a,
        family=family,
    )
    audit = [
        "# AWAKENING PATH EARLY AUDIT",
        "",
        "## Mission",
        "",
        "Among policy trades that OPEN in NEUTRAL and are still open at locked bar k, "
        "does a path signal knowable at bar k (not at close, not the full-trade MAE) "
        "separate eventual hole H from eventual winners W?",
        "Measure-only. Gate 1 law NONE. No PATH_EXIT. No learn().",
        f"**Date:** {now}",
        f"**Gate 0 (PR #24 land):** `{gate0_sha}`",
        f"**parent_loaded:** `{parent_loaded}`",
        "",
        "## Prior closed science (do not reopen)",
        "",
        "- PR #22 ENTRY: hole already NEUTRAL at OPEN. Family OPEN_DECISION (closed as controller).",
        "- PR #23 OPEN_SPLIT: five external open bits → S_NONE. Licensed H_NONE.",
        "- PR #24 OPEN_POLICY_SIGNAL: value + entropy at OPEN → S_NONE. Licensed H_NONE.",
        "- This ticket: locked-k path bits among still-open trades.",
        "",
        "## Frozen hashes (parent / control / hole-tax) + bytes",
        "",
        "| Role | sha256 | bytes |",
        "|------|--------|-------|",
        "| PARENT / Birth-exit π* | `8cc435c68a37b0a070e38bccc4bfd402d4a802396bd7cd2fcce02f50acf69a03` | 202268 |",
        "| CONTROL / PR #20 child | `db7daf3b978fe80624608e27111627b5b9c3070e71118c66673df996123dd029` | 202271 |",
        "| HOLE-TAX child | `ca2ae0e5fa6f0e54215fe6c833e2ebff608b5e99426a6e75ff5f7167d6bb0325` | 202271 |",
        "",
        "## Gate 0 protocol dump (inspect_path_early_protocol)",
        "",
        json.dumps(proto, indent=2, default=str),
        "",
        "## Snapshot sites",
        "",
        f"snapshot function: `{proto.get('snapshot_site')}`",
        *stash_lines,
        "",
        "## Fixture reuse (A/B ticks_sha16, price_sha16, reused_manifest)",
        "",
        f"- A ticks_sha16=`{fix_a.get('ticks_sha16', t0_a.get('ticks_sha16'))}` "
        f"price_sha16=`{fix_a.get('price_sha16', t0_a.get('price_sha16'))}` "
        f"reused_manifest=`{fix_a.get('reused_manifest')}`",
        f"- B ticks_sha16=`{fix_b.get('ticks_sha16', t0_b.get('ticks_sha16'))}` "
        f"price_sha16=`{fix_b.get('price_sha16', t0_b.get('price_sha16'))}` "
        f"reused_manifest=`{fix_b.get('reused_manifest')}`",
        "",
        "## Evaluate-only call (run_evaluate_only kwargs, optimizer_steps)",
        "",
        f"call site: `{proto.get('run_evaluate_only_call')}`",
        "runtime=`select_runtime()`, ledger_source=`awakening_path_early`, "
        "exploration_steps=0 (via s5_envelope_kwargs), TRAIN=False.",
        f"**optimizer_steps:** `0` (A t0={t0_a.get('optimizer_steps')} B t0={t0_b.get('optimizer_steps')})",
        "",
        "## T0 identity + wire-vs-POLICY_SIGNAL-A",
        "",
        json.dumps({"A": t0_a, "B": t0_b}, indent=2, default=str),
        "",
        "Wire vs POLICY_SIGNAL A: wr_policy baseline 0.293 n_policy 150. "
        "AND-stop fires only if both deltas exceed 0.03 / 15.",
        "",
        "## T1 U / H / W plus per-k U_k",
        "",
        json.dumps({"A": t1_a, "B": t1_b}, indent=2, default=str),
        "",
        "## T1b path-key distributions (null mean when n_defined=0)",
        "",
        json.dumps({"A": payload_a.get("t1b"), "B": payload_b.get("t1b")}, indent=2, default=str),
        "",
        "## Paper-wick honesty",
        "",
        _paper_mae_costume(payload_a.get("t1b") or {}),
        "",
        "## T2 path candidate grid",
        "",
        json.dumps({"A": payload_a.get("t2"), "B": payload_b.get("t2")}, indent=2, default=str),
        "",
        "## T3 paper counterfactual",
        "",
        json.dumps({"A": payload_a.get("t3"), "B": payload_b.get("t3")}, indent=2, default=str),
        "",
        "## T4 read-only contrast",
        "",
        json.dumps(t4, indent=2, default=str),
        "",
        "## T5 opposite-tail (READ_ONLY_FLIP, cannot win)",
        "",
        json.dumps({"A": payload_a.get("t5"), "B": payload_b.get("t5")}, indent=2, default=str),
        "",
        "## Licensing decision (A SSOT)",
        "",
        f"**Tag:** `{tag}`  **Winning P:** `{winning}`  **Licensed next family:** `{family}`  **Gate 1 law:** `NONE`",
        honesty,
        "",
        "## Forbidden-path grep (learn, " + "training" + "_reward, PATH_EXIT controller)",
        "",
        json.dumps(_forbidden_grep(), indent=2, default=str),
        "",
        "## Capital / autonomy / experiment",
        "",
        "- **Capital:** SIM only. No flatten-at-k. Close-time MAE is not a k-feature.",
        "- **Autonomy:** frozen π* unchanged; the organism measures whether early path "
        "separates hole from winners among trades still open at locked k.",
        "- **Experiment:** one variable (locked-k path split). Open-time families stay closed. "
        "Playground stays closed. Representation rebuild is the next ticket only if S_NONE.",
        "",
    ]
    (reports / "AWAKENING_PATH_EARLY_AUDIT.md").write_text("\n".join(audit) + "\n", encoding="utf-8")
    verdict = [
        "# AWAKENING PATH EARLY VERDICT",
        "",
        f"**Overall:** `{overall}`",
        f"**Date:** {now}",
        f"**Evaluated zip sha256:** `{INIT_SHA256}`",
        "**optimizer_steps:** `0`",
        f"**skip_replay:** `{str(bool(skip_replay)).lower()}`",
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
        "### T0 — book identity",
        "",
        "| Leg | n_all | n_policy | n_plant | wr_policy | mean_r_policy | zip sha16 | ticks_sha16 | price_sha16 | optimizer_steps | skip_replay |",
        "|-----|-------|----------|---------|-----------|---------------|-----------|-------------|-------------|-----------------|-------------|",
        (
            f"| A | {t0_a.get('n_all')} | {t0_a.get('n_policy')} | {t0_a.get('n_plant')} | "
            f"{t0_a.get('wr_policy')} | {t0_a.get('mean_r_policy')} | {(zip_sha or '')[:16]} | "
            f"{t0_a.get('ticks_sha16')} | {t0_a.get('price_sha16')} | {t0_a.get('optimizer_steps')} | "
            f"{t0_a.get('skip_replay')} |"
        ),
        (
            f"| B | {t0_b.get('n_all')} | {t0_b.get('n_policy')} | {t0_b.get('n_plant')} | "
            f"{t0_b.get('wr_policy')} | {t0_b.get('mean_r_policy')} | {(zip_sha or '')[:16]} | "
            f"{t0_b.get('ticks_sha16')} | {t0_b.get('price_sha16')} | {t0_b.get('optimizer_steps')} | "
            f"{t0_b.get('skip_replay')} |"
        ),
        "",
        "### T1 — universe U / H / W and U_k",
        "",
        f"- A U: `{_md_cell(t1_a.get('U') or {})}` n_U={t1_a.get('n_U')} k={t1_a.get('k')}",
        f"- A H: `{_md_cell(t1_a.get('H') or {})}`",
        f"- A W: `{_md_cell(t1_a.get('W') or {})}`",
        f"- B U: `{_md_cell(t1_b.get('U') or {})}` n_U={t1_b.get('n_U')} k={t1_b.get('k')}",
        f"- B H: `{_md_cell(t1_b.get('H') or {})}`",
        f"- B W: `{_md_cell(t1_b.get('W') or {})}`",
        "",
        "### T1b — path distributions",
        "",
        json.dumps({"A": payload_a.get("t1b"), "B": payload_b.get("t1b")}, indent=2, default=str),
        "",
        "### T2 — path candidate grid",
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
        _paper_mae_costume(payload_a.get("t1b") or {}),
        "",
        "Playground does not open. No learn(). Gate 1 law: NONE.",
        "",
    ]
    (reports / "AWAKENING_PATH_EARLY_VERDICT.md").write_text("\n".join(verdict) + "\n", encoding="utf-8")
    k_locked = ",".join(str(k) for k in K_LOCKED)
    block = f"""
---

## This ticket — Awakening PATH_EARLY autopsy (measure-only)

**Prompt:** Among policy NEUTRAL opens still open at locked k={k_locked}, do k-bar path bits separate hole from +R?
**Train:** none. optimizer_steps=0. Parent zip 8cc435c6 only.
**Landed:** PR #24 on main before replay. Gate 0 SHA `{gate0_sha}`.
**Leg A** seed 20260902 n_U={t1_a.get("n_U")} n_H={t1_a.get("n_H")} n_W={t1_a.get("n_W")} U_3={n_u3_a} U_5={n_u5_a} wr_policy={t0_a.get("wr_policy")} tag={flags_a.get("tag")} winning_P={flags_a.get("winning_P")}.
**Leg B** seed 20260903 n_U={t1_b.get("n_U")} n_H={t1_b.get("n_H")} n_W={t1_b.get("n_W")} wr_policy={t0_b.get("wr_policy")} tag={flags_b.get("tag")} winning_P={flags_b.get("winning_P")}.
**Tag / winning P:** `{tag}` / `{winning}` licensed=`{family}`
**Overall:** `{overall}`
**SSOT:** `AWAKENING_PATH_EARLY_AUDIT.md` / `AWAKENING_PATH_EARLY_VERDICT.md`
"""
    for rel in (
        reports / "LUMINA_BIRTH_EXPERIMENT_LOG.md",
        reports / "artifacts" / "LUMINA_BIRTH_EXPERIMENT_LOG.md",
    ):
        if rel.is_file() or rel.parent.is_dir():
            with rel.open("a", encoding="utf-8") as fh:
                fh.write(block)


__all__ = ["leg_payload", "write_path_early_reports"]

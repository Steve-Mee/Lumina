"""OPEN_SPLIT audit / verdict / flags / ledger writers. Measure-only, no train law."""

from __future__ import annotations

import json
import re
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from lumina_core.birth.awakening_open_split import (
    CANDIDATE_NAMES,
    INIT_SHA256,
    compute_open_split_flags,
    honesty_paragraph,
    license_from_ab,
)
from lumina_core.birth.awakening_open_split_path import STASH_ATTR_PATHS
from lumina_core.birth.awakening_open_split_tables import table_t0, table_t1, table_t2, table_t3

STASH_KEYS = tuple(STASH_ATTR_PATHS.keys())


def leg_payload(
    *,
    rows: list[dict[str, Any]],
    zip_sha: str,
    ticks_sha16: str,
    price_sha16_value: str,
    optimizer_steps: int,
) -> dict[str, Any]:
    flags = compute_open_split_flags(rows)
    t0 = table_t0(
        rows,
        zip_sha256=zip_sha,
        ticks_sha16=ticks_sha16,
        price_sha16_value=price_sha16_value,
        optimizer_steps=int(optimizer_steps),
    )
    return {
        "t0": t0,
        "t1": table_t1(rows),
        "t2": table_t2(rows),
        "t3": table_t3(rows),
        "flags": flags,
        "rows_n": len(rows),
        "stash_produced": _stash_produced(rows),
    }


def _stash_produced(rows: list[dict[str, Any]]) -> dict[str, str]:
    out: dict[str, str] = {}
    for key in STASH_KEYS:
        present = any(key in r and r.get(key) is not None for r in rows)
        out[key] = "produced" if present else "missing"
    return out


def _md_cell(cell: dict[str, Any]) -> str:
    return f"n={cell.get('n')} wr={cell.get('wr')} mean_r={cell.get('mean_r')} mean_usd={cell.get('mean_usd')}"


def _t2_table(grid: dict[str, Any]) -> list[str]:
    lines = [
        "| F | n_defined | missing_share | cov_H | cov_W | lift | S_SPLIT | S_HARM | missing |",
        "|---|-----------|---------------|-------|-------|------|---------|--------|---------|",
    ]
    for name in CANDIDATE_NAMES:
        row = grid.get(name) or {}
        lines.append(
            f"| `{name}` | {row.get('n_defined')} | {row.get('missing_share')} | "
            f"{row.get('cov_H')} | {row.get('cov_W')} | {row.get('lift')} | "
            f"{row.get('S_SPLIT')} | {row.get('S_HARM')} | {row.get('missing')} |"
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
    split_src = (birth / "awakening_open_split.py").read_text(encoding="utf-8")
    run_src = (birth / "awakening_open_split_run.py").read_text(encoding="utf-8")
    envelope_fn = "decide_stage2" + "_participation("
    controller = envelope_fn in split_src or envelope_fn in run_src
    return {
        "hygiene_token_in_birth": hits_reward,
        "model_learn_in_birth": hits_learn,
        "open_filter_controller": controller,
    }


def write_open_split_reports(
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
) -> None:
    now = datetime.now(timezone.utc).isoformat()
    (reports / "artifacts").mkdir(parents=True, exist_ok=True)
    flags_a = payload_a.get("flags") or {}
    flags_b = payload_b.get("flags") or {}
    licensed = license_from_ab(flags_a, flags_b)
    tag = str(licensed.get("tag") or "S_NONE")
    winning = str(licensed.get("winning_F") or "none")
    family = str(licensed.get("licensed_next_family") or "OPEN_DECISION")
    t0_a = payload_a.get("t0") or {}
    t0_b = payload_b.get("t0") or {}
    t1_a = payload_a.get("t1") or {}
    t1_b = payload_b.get("t1") or {}
    t2_a = payload_a.get("t2") or {}
    cand_a = (flags_a.get("candidates") or {}).get(winning) or {}
    lift_a = cand_a.get("lift") if winning != "none" else None
    flags_payload = {
        "A": flags_a,
        "B": flags_b,
        "tag": tag,
        "winning_F": winning,
        "licensed_next_family": family,
        "gate1": "NONE",
        "optimizer_steps": 0,
        "evaluated_zip_sha256": zip_sha,
        "evolution_proof_stamped": False,
        "REAL": "no",
        "overall": overall,
    }
    (reports / "artifacts" / "awakening_open_split_flags.json").write_text(
        json.dumps(flags_payload, indent=2, default=str) + "\n", encoding="utf-8"
    )
    produced_a = payload_a.get("stash_produced") or {}
    produced_b = payload_b.get("stash_produced") or {}
    stash_lines = [
        "| key | attr path | A | B |",
        "|-----|-----------|---|---|",
    ]
    for key, path in STASH_ATTR_PATHS.items():
        stash_lines.append(
            f"| `{key}` | `{path}` | {produced_a.get(key, 'missing')} | {produced_b.get(key, 'missing')} |"
        )
    fix_a = fixture_a or {}
    fix_b = fixture_b or {}
    audit = [
        "# AWAKENING OPEN SPLIT AUDIT",
        "",
        "## Mission",
        "",
        "Among policy trades that OPEN in NEUTRAL, which feature knowable at the open bar "
        "separates `stop × close NEUTRAL` (hole H) from +R closes (winners W)?",
        "Measure-only. Gate 1 law NONE. No open-mask. No learn().",
        f"**Date:** {now}",
        f"**Gate 0 (PR #22 land):** `{gate0_sha}`",
        f"**parent_loaded:** `{parent_loaded}`",
        "",
        "## Frozen hashes (parent / control / hole-tax) + bytes",
        "",
        "| Role | sha256 | bytes |",
        "|------|--------|-------|",
        "| PARENT / Birth-exit π* | `8cc435c68a37b0a070e38bccc4bfd402d4a802396bd7cd2fcce02f50acf69a03` | 202268 |",
        "| CONTROL / PR #20 child | `db7daf3b978fe80624608e27111627b5b9c3070e71118c66673df996123dd029` | 202271 |",
        "| HOLE-TAX child | `ca2ae0e5fa6f0e54215fe6c833e2ebff608b5e99426a6e75ff5f7167d6bb0325` | 202271 |",
        "",
        "## Gate 0 protocol dump (inspect_open_split_protocol)",
        "",
        json.dumps(proto, indent=2, default=str),
        "",
        "## Live open-stash sites (file:line + attribute path per key)",
        "",
        f"gather_open_features: `{proto.get('gather_open_features')}`",
        f"stamp_open_host: `{proto.get('stamp_open_host')}`",
        f"start_open_telem optional: `{proto.get('start_open_telem_optional')}`",
        "",
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
        "runtime=`select_runtime()`, ledger_source=`awakening_open_split`, "
        "exploration_steps=0 (via s5_envelope_kwargs), TRAIN=False.",
        f"**optimizer_steps:** `0` (A t0={t0_a.get('optimizer_steps')} B t0={t0_b.get('optimizer_steps')})",
        "",
        "## T0 identity + wire-vs-autopsy-A",
        "",
        json.dumps({"A": t0_a, "B": t0_b}, indent=2, default=str),
        "",
        "Wire vs PR #22 autopsy A: wr_policy baseline 0.373 n_policy 150. "
        "AND-stop fires only if both deltas exceed 0.03 / 15.",
        "",
        "## T1 U / H / W",
        "",
        json.dumps({"A": t1_a, "B": t1_b}, indent=2, default=str),
        "",
        "## T2 candidate grid",
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
        "## Licensing decision (A SSOT)",
        "",
        f"**Tag:** `{tag}`  **Winning F:** `{winning}`  **Licensed next family:** `{family}`  **Gate 1 law:** `NONE`",
        honesty_paragraph(tag, winning, lift_a if isinstance(lift_a, float) else None),
        "",
        "## Forbidden-path grep (learn, " + "training" + "_reward, OPEN_FILTER controller)",
        "",
        json.dumps(_forbidden_grep(), indent=2, default=str),
        "",
        "## Capital / autonomy / experiment",
        "",
        "- **Capital:** SIM only. Exam dollars stay the fill. No mask on live participation.",
        "- **Autonomy:** measurement compounds; the organism learns whether NEUTRAL-open is one door or two.",
        "- **Experiment:** one variable (at-OPEN split inside NEUTRAL-open). Close-tax family stays closed. Blanket NEUTRAL-refuse stays forbidden.",
        "",
    ]
    (reports / "AWAKENING_OPEN_SPLIT_AUDIT.md").write_text("\n".join(audit) + "\n", encoding="utf-8")
    verdict = [
        "# AWAKENING OPEN SPLIT VERDICT",
        "",
        f"**Overall:** `{overall}`",
        f"**Date:** {now}",
        f"**Evaluated zip sha256:** `{INIT_SHA256}`",
        "**optimizer_steps:** `0`",
        f"**S_MISSING_U A/B:** `{flags_a.get('S_MISSING_U')}` / `{flags_b.get('S_MISSING_U')}`",
        f"**S_THIN A/B:** `{flags_a.get('S_THIN')}` / `{flags_b.get('S_THIN')}`",
        f"**Winning F A/B:** `{flags_a.get('winning_F')}` / `{flags_b.get('winning_F')}`",
        f"**Tag:** `{tag}`",
        f"**Licensed next family:** `{family}`",
        "**Gate 1 law:** `NONE`",
        "**Evolution Proof stamped:** `False`",
        "**REAL:** `no`",
        "",
        "### T0 — book identity",
        "",
        "| Leg | n_all | n_policy | n_plant | wr_policy | mean_r_policy | zip sha16 | ticks_sha16 | price_sha16 | optimizer_steps |",
        "|-----|-------|----------|---------|-----------|---------------|-----------|-------------|-------------|-----------------|",
        (
            f"| A | {t0_a.get('n_all')} | {t0_a.get('n_policy')} | {t0_a.get('n_plant')} | "
            f"{t0_a.get('wr_policy')} | {t0_a.get('mean_r_policy')} | {(zip_sha or '')[:16]} | "
            f"{t0_a.get('ticks_sha16')} | {t0_a.get('price_sha16')} | {t0_a.get('optimizer_steps')} |"
        ),
        (
            f"| B | {t0_b.get('n_all')} | {t0_b.get('n_policy')} | {t0_b.get('n_plant')} | "
            f"{t0_b.get('wr_policy')} | {t0_b.get('mean_r_policy')} | {(zip_sha or '')[:16]} | "
            f"{t0_b.get('ticks_sha16')} | {t0_b.get('price_sha16')} | {t0_b.get('optimizer_steps')} |"
        ),
        "",
        "### T1 — universe U / H / W",
        "",
        f"- A U: `{_md_cell(t1_a.get('U') or {})}` n_U={t1_a.get('n_U')} share_H={t1_a.get('share_H')} share_W={t1_a.get('share_W')}",
        f"- A H: `{_md_cell(t1_a.get('H') or {})}`",
        f"- A W: `{_md_cell(t1_a.get('W') or {})}`",
        f"- B U: `{_md_cell(t1_b.get('U') or {})}` n_U={t1_b.get('n_U')} share_H={t1_b.get('share_H')} share_W={t1_b.get('share_W')}",
        f"- B H: `{_md_cell(t1_b.get('H') or {})}`",
        f"- B W: `{_md_cell(t1_b.get('W') or {})}`",
        "",
        "### T2 — candidate grid",
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
        "### Honesty",
        "",
        honesty_paragraph(tag, winning, lift_a if isinstance(lift_a, float) else None),
        "",
        "Playground does not open. No learn(). Gate 1 law: NONE.",
        "",
    ]
    (reports / "AWAKENING_OPEN_SPLIT_VERDICT.md").write_text("\n".join(verdict) + "\n", encoding="utf-8")
    block = f"""
---

## This ticket — Awakening OPEN_SPLIT autopsy (measure-only)

**Prompt:** Among policy NEUTRAL opens, which at-OPEN feature separates hole from +R?
**Train:** none. optimizer_steps=0. Parent zip 8cc435c6 only.
**Landed:** PR #22 on main before replay (record merge SHA or green HEAD). Gate 0 SHA `{gate0_sha}`.
**Leg A** seed 20260902 n_U={t1_a.get("n_U")} n_H={t1_a.get("n_H")} n_W={t1_a.get("n_W")} wr_policy={t0_a.get("wr_policy")} tag={flags_a.get("tag")} winning_F={flags_a.get("winning_F")}.
**Leg B** seed 20260903 n_U={t1_b.get("n_U")} n_H={t1_b.get("n_H")} n_W={t1_b.get("n_W")} wr_policy={t0_b.get("wr_policy")} tag={flags_b.get("tag")} winning_F={flags_b.get("winning_F")}.
**Tag / winning F:** `{tag}` / `{winning}` licensed=`{family}`
**Overall:** `{overall}`
**SSOT:** `AWAKENING_OPEN_SPLIT_AUDIT.md` / `AWAKENING_OPEN_SPLIT_VERDICT.md`
"""
    for rel in (
        reports / "LUMINA_BIRTH_EXPERIMENT_LOG.md",
        reports / "artifacts" / "LUMINA_BIRTH_EXPERIMENT_LOG.md",
    ):
        if rel.is_file() or rel.parent.is_dir():
            with rel.open("a", encoding="utf-8") as fh:
                fh.write(block)


__all__ = ["leg_payload", "write_open_split_reports"]

"""ENTRY autopsy audit / verdict / ledger writers. Measure-only, no train law."""

from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from lumina_core.birth.awakening_entry_autopsy import (
    INIT_SHA256,
    compute_entry_flags,
    honesty_paragraph,
    policy_only_rows,
    table_t0,
    table_t1,
    table_t2,
    table_t3,
)


def leg_payload(
    *,
    rows: list[dict[str, Any]],
    zip_sha: str,
    ticks_sha16: str,
    price_sha16_value: str,
    optimizer_steps: int,
) -> dict[str, Any]:
    policy = policy_only_rows(rows)
    flags = compute_entry_flags(rows)
    t0 = table_t0(
        rows,
        zip_sha256=zip_sha,
        ticks_sha16=ticks_sha16,
        price_sha16_value=price_sha16_value,
        optimizer_steps=int(optimizer_steps),
    )
    return {
        "t0": t0,
        "t1": table_t1(policy),
        "t2": table_t2(policy),
        "t3": table_t3(policy),
        "flags": flags,
        "rows_n": len(rows),
    }


def _md_cell(cell: dict[str, Any]) -> str:
    mae = cell.get("median_mae_r")
    mfe = cell.get("median_mfe_r")
    mae_s = "missing" if mae is None else f"{mae}"
    mfe_s = "missing" if mfe is None else f"{mfe}"
    return (
        f"n={cell.get('n')} wr={cell.get('wr')} mean_r={cell.get('mean_r')} "
        f"mean_usd={cell.get('mean_usd')} entry_NEUTRAL={cell.get('n_entry_neutral')} "
        f"entry_TREND={cell.get('n_entry_trend')} entry_UNKNOWN={cell.get('n_entry_unknown')} "
        f"frac_neu={cell.get('frac_entry_neutral')} frac_tr={cell.get('frac_entry_trend')} "
        f"frac_flip={cell.get('frac_regime_flip')} median_held={cell.get('median_bars_held')} "
        f"p25={cell.get('p25_bars_held')} p75={cell.get('p75_bars_held')} "
        f"median_mae_r={mae_s} median_mfe_r={mfe_s}"
    )


def write_entry_autopsy_reports(
    *,
    reports: Path,
    overall: str,
    family: str,
    zip_sha: str,
    payload_a: dict[str, Any],
    payload_b: dict[str, Any],
    t4: dict[str, Any],
    proto: dict[str, Any],
    parent_loaded: bool,
) -> None:
    now = datetime.now(timezone.utc).isoformat()
    (reports / "artifacts").mkdir(parents=True, exist_ok=True)
    flags_a = payload_a.get("flags") or {}
    flags_b = payload_b.get("flags") or {}
    t0_a = payload_a.get("t0") or {}
    t0_b = payload_b.get("t0") or {}
    t1_a = payload_a.get("t1") or {}
    t1_b = payload_b.get("t1") or {}
    flags_payload = {
        "A": flags_a,
        "B": flags_b,
        "licensed_future_family": family,
        "gate1": "NONE",
        "optimizer_steps": 0,
        "evaluated_zip_sha256": zip_sha,
        "missing_fields": list(flags_a.get("missing_fields") or []),
        "evolution_proof_stamped": False,
        "REAL": "no",
        "overall": overall,
    }
    (reports / "artifacts" / "awakening_entry_autopsy_flags.json").write_text(
        json.dumps(flags_payload, indent=2, default=str) + "\n", encoding="utf-8"
    )
    audit = [
        "# AWAKENING ENTRY AUTOPSY AUDIT",
        "",
        f"**Date:** {now}",
        "**Engine:** BRO-v2 evaluate-only parent replay (no PPO update)",
        "**Capital:** SIM / certified-shadow. REAL=no. NT=no.",
        f"**Evaluated zip sha256:** `{zip_sha}`",
        "**optimizer_steps:** `0`",
        f"**parent_loaded:** `{parent_loaded}`",
        "",
        "## Gate 0 protocol",
        "",
        json.dumps(proto, indent=2, default=str),
        "",
        "## Leg A (seed 20260902) — disk re-read",
        "",
        json.dumps(payload_a, indent=2, default=str),
        "",
        "## Leg B (seed 20260903) — disk re-read",
        "",
        json.dumps(payload_b, indent=2, default=str),
        "",
        "## T4 existing-book close-only contrast (read-only)",
        "",
        json.dumps(t4, indent=2, default=str),
        "",
        "## Gate 1 law",
        "",
        "NONE. No open-mask. No extra tax. No NEUTRAL drop. No time-stop rewrite.",
        f"Licensed future family string: `{family}` — not shipped as a controller.",
        "",
    ]
    (reports / "AWAKENING_ENTRY_AUTOPSY_AUDIT.md").write_text("\n".join(audit) + "\n", encoding="utf-8")
    verdict = [
        "# AWAKENING ENTRY AUTOPSY VERDICT",
        "",
        f"**Overall:** `{overall}`",
        f"**Date:** {now}",
        f"**Evaluated zip sha256:** `{INIT_SHA256}`",
        "**optimizer_steps:** `0`",
        f"**H_MISSING_ENTRY A/B:** `{flags_a.get('H_MISSING_ENTRY')}` / `{flags_b.get('H_MISSING_ENTRY')}`",
        f"**H_ENTRY_NEUTRAL A/B:** `{flags_a.get('H_ENTRY_NEUTRAL')}` / `{flags_b.get('H_ENTRY_NEUTRAL')}`",
        f"**H_ENTRY_FLIP A/B:** `{flags_a.get('H_ENTRY_FLIP')}` / `{flags_b.get('H_ENTRY_FLIP')}`",
        f"**H_FIRST_TOUCH A/B:** `{flags_a.get('H_FIRST_TOUCH')}` / `{flags_b.get('H_FIRST_TOUCH')}`",
        f"**Licensed future family:** `{family}`",
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
        "### T1 — hole cell vs contrast (policy-only)",
        "",
        f"- A hole (stop×NEUTRAL): `{_md_cell(t1_a.get('hole') or {})}`",
        f"- A target: `{_md_cell(t1_a.get('target') or {})}`",
        f"- B hole (stop×NEUTRAL): `{_md_cell(t1_b.get('hole') or {})}`",
        f"- B target: `{_md_cell(t1_b.get('target') or {})}`",
        "",
        "### T2 — entry_regime × close_reason (policy-only)",
        "",
        f"- A trigger cells: `{json.dumps((payload_a.get('t2') or {}).get('trigger'), default=str)}`",
        f"- A small: `{(payload_a.get('t2') or {}).get('small')}`",
        f"- B trigger cells: `{json.dumps((payload_b.get('t2') or {}).get('trigger'), default=str)}`",
        f"- B small: `{(payload_b.get('t2') or {}).get('small')}`",
        "",
        "### T3 — first-touch vs bleed on the hole",
        "",
        f"- A: `{payload_a.get('t3')}`",
        f"- B: `{payload_b.get('t3')}`",
        "",
        "### T4 — existing-book close-only contrast (read-only)",
        "",
        json.dumps(t4, indent=2, default=str),
        "",
        "### Honesty",
        "",
        honesty_paragraph(family),
        "",
        "Playground does not open. No second learn(). Gate 1 law: NONE.",
        "",
    ]
    (reports / "AWAKENING_ENTRY_AUTOPSY_VERDICT.md").write_text(
        "\n".join(verdict) + "\n", encoding="utf-8"
    )
    hygiene_token = "training" + "_reward"
    block = f"""
---

## This ticket — Awakening ENTRY hole autopsy (measure-only)

**Prompt:** Where does stop×NEUTRAL start — regime at OPEN or only at CLOSE?
**Train:** none. optimizer_steps=0. Parent zip 8cc435c6 only.
**Hygiene:** {hygiene_token} token removed from birth/; GitPython==3.1.59.
**Leg A** seed 20260902 n_all={t0_a.get('n_all')} n_policy={t0_a.get('n_policy')} wr_policy={t0_a.get('wr_policy')} mean_r={t0_a.get('mean_r_policy')} ticks={t0_a.get('ticks_sha16')} price={t0_a.get('price_sha16')} hole={t1_a.get('hole')} flags={flags_a}.
**Leg B** seed 20260903 n_all={t0_b.get('n_all')} n_policy={t0_b.get('n_policy')} wr_policy={t0_b.get('wr_policy')} mean_r={t0_b.get('mean_r_policy')} ticks={t0_b.get('ticks_sha16')} price={t0_b.get('price_sha16')} hole={t1_b.get('hole')} flags={flags_b}.
**Flags:** A missing={flags_a.get('H_MISSING_ENTRY')} neu={flags_a.get('H_ENTRY_NEUTRAL')} flip={flags_a.get('H_ENTRY_FLIP')} ft={flags_a.get('H_FIRST_TOUCH')}; B missing={flags_b.get('H_MISSING_ENTRY')} neu={flags_b.get('H_ENTRY_NEUTRAL')} flip={flags_b.get('H_ENTRY_FLIP')} ft={flags_b.get('H_FIRST_TOUCH')}. Licensed=`{family}`.
**Overall:** `{overall}`
**SSOT:** `AWAKENING_ENTRY_AUTOPSY_AUDIT.md` / `AWAKENING_ENTRY_AUTOPSY_VERDICT.md`
"""
    for rel in (
        reports / "LUMINA_BIRTH_EXPERIMENT_LOG.md",
        reports / "artifacts" / "LUMINA_BIRTH_EXPERIMENT_LOG.md",
    ):
        if rel.is_file() or rel.parent.is_dir():
            with rel.open("a", encoding="utf-8") as fh:
                fh.write(block)


__all__ = ["leg_payload", "write_entry_autopsy_reports"]

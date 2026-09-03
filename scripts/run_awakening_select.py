#!/usr/bin/env python3
"""Awakening selection: one pinned PPO shot from Birth-exit π*, then eval A/B.

SIM / certified-shadow only. No container.start(), no NT, no REAL, no second learn().
"""

from __future__ import annotations

import json
import os
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

REPO_ROOT = Path(__file__).resolve().parents[1]
REPORTS = REPO_ROOT / "reports" / "birth_cloud_run"
WS_A = REPORTS / "workspace"
WS_B = REPORTS / "workspace_grind_b"
PROOF_WS = REPORTS / "awakening_select" / "workspace"


def _load_or_build_fixture(workspace: Path, *, seed: int, force: bool) -> dict[str, Any]:
    from lumina_core.birth.awakening_select import price_sha16
    from lumina_core.birth.synthetic_cloud_fixture import (
        CloudFixtureSpec,
        persist_cloud_fixture,
        write_fixture_sidecar,
    )
    from lumina_core.birth.tick_cache_persist import certified_tick_cache_present, load_split_cache

    workspace.mkdir(parents=True, exist_ok=True)
    (workspace / "state").mkdir(parents=True, exist_ok=True)
    sidecar = REPORTS / ("01_fixture_manifest.json" if seed == 20260902 else "01_fixture_manifest_B.json")
    reused = False
    if seed == 20260902 and certified_tick_cache_present(workspace) and sidecar.is_file() and not force:
        manifest = json.loads(sidecar.read_text(encoding="utf-8"))
        split = load_split_cache(workspace, holdout_pct=0.20)
        if split is not None and str(manifest.get("hash") or "") == "7e86c2bb1c71d514":
            holdout = list(split.holdout)
            return {
                "manifest": manifest,
                "holdout": holdout,
                "reused_manifest": True,
                "ticks_sha16": str(manifest.get("hash") or ""),
                "bars_sha16": str(manifest.get("raw_ticks_hash") or ""),
                "price_sha16": price_sha16(holdout),
            }
    spec = CloudFixtureSpec(seed=int(seed))
    result = persist_cloud_fixture(workspace, spec=spec)
    write_fixture_sidecar(sidecar, result.fixture_manifest)
    man = dict(result.fixture_manifest)
    holdout = list(result.split.holdout)
    return {
        "manifest": man,
        "holdout": holdout,
        "reused_manifest": reused,
        "ticks_sha16": str(man.get("hash") or man.get("train_hash") or ""),
        "bars_sha16": str(man.get("raw_ticks_hash") or ""),
        "price_sha16": price_sha16(holdout),
    }


def _append_experiment_log(row: str) -> None:
    log_path = REPORTS / "LUMINA_BIRTH_EXPERIMENT_LOG.md"
    with log_path.open("a", encoding="utf-8") as fh:
        fh.write(row)


def _write_verdict(
    *,
    overall: str,
    table_a: dict[str, Any],
    table_b: dict[str, Any],
    proof: dict[str, Any],
    train: dict[str, Any],
    init_sha: str,
) -> None:
    now = datetime.now(timezone.utc).isoformat()
    verdict = [
        "# AWAKENING SELECT VERDICT",
        "",
        f"**Overall:** `{overall}`",
        "",
        f"**Date:** {now}",
        f"**Child sha256:** `{train.get('child_sha256')}`",
        f"**Init sha256:** `{init_sha}` (must stay `8cc435c68a37b0a070e38bccc4bfd402d4a802396bd7cd2fcce02f50acf69a03`)",
        f"**SELECT_NOOP:** `{train.get('select_noop')}`",
        f"**Timesteps pin:** `{train.get('actual_timesteps')}` / requested `{train.get('sidecar', {}).get('timesteps')}`",
        f"**optimizer_steps:** `{train.get('optimizer_steps')}`",
        "",
        "Child vs BASELINE_BIRTH_EXIT (PR #17 skill WR 0.34 / 0.28). Geometry unchanged. Selection shot only.",
        "",
        "| Leg | class | n | wr_all | wr_policy | mean$_all | mean$_policy | mean_r_policy | sharpe | dd% of $50k | occ | plant_n | FO closes | FO bars |",
        "|-----|-------|---|--------|-----------|-----------|--------------|---------------|--------|-------------|-----|---------|-----------|---------|",
        (
            f"| A child | {table_a.get('classification')} | {table_a.get('n')} | {table_a.get('wr_all')} | "
            f"{table_a.get('wr_policy')} | {table_a.get('mean_usd_all')} | {table_a.get('mean_usd_policy')} | "
            f"{table_a.get('mean_r_policy')} | {table_a.get('sharpe')} | {table_a.get('dd_pct_of_50k')} | "
            f"{table_a.get('occ')} | {table_a.get('plant_n')} | {table_a.get('force_open_closes')} | "
            f"{table_a.get('FORCE_OPEN_bars')} |"
        ),
        (
            f"| B child | {table_b.get('classification')} | {table_b.get('n')} | {table_b.get('wr_all')} | "
            f"{table_b.get('wr_policy')} | {table_b.get('mean_usd_all')} | {table_b.get('mean_usd_policy')} | "
            f"{table_b.get('mean_r_policy')} | {table_b.get('sharpe')} | {table_b.get('dd_pct_of_50k')} | "
            f"{table_b.get('occ')} | {table_b.get('plant_n')} | {table_b.get('force_open_closes')} | "
            f"{table_b.get('FORCE_OPEN_bars')} |"
        ),
        "| A baseline | GRIND_REGRESS | 218 | 0.303 | 0.34 | -74.73 | -23.87 | -0.211 | -4.783 | 33.982 | 0.757 | 68 | 68 | 165 |",
        "| B baseline | INCONCLUSIVE | 171 | 0.281 | 0.28 | -44.32 | -26.91 | -0.329 | -3.865 | 15.343 | 0.759 | 21 | 21 | 56 |",
        "",
        "### Exits / hole cell (policy-only stop×NEUTRAL)",
        "",
        f"- A exits stop/target/time_stop = `{table_a.get('exits')}` stop×NEUTRAL `{table_a.get('stop_x_neutral')}` target_mean_r `{table_a.get('target_mean_r')}` time_stop_mean_r `{table_a.get('time_stop_mean_r')}`",
        f"- B exits stop/target/time_stop = `{table_b.get('exits')}` stop×NEUTRAL `{table_b.get('stop_x_neutral')}` target_mean_r `{table_b.get('target_mean_r')}` time_stop_mean_r `{table_b.get('time_stop_mean_r')}`",
        "",
        f"- Evolution Proof stamped: `{proof.get('stamped')}`. passed_inequalities=`{proof.get('passed_inequalities')}`.",
        f"- polish_oos_winrate used: wr_policy_B (`{table_b.get('wr_policy')}`) — policy-only to match PR #17 skill WR.",
        "- Birth receipts / fitness `707b5ab9d6b9af96`: **untouched**.",
        "- REAL: **no**.",
        "- `is_birth_exit_sufficient`: **True** as PR #14 left it.",
        "",
    ]
    (REPORTS / "AWAKENING_SELECT_VERDICT.md").write_text("\n".join(verdict) + "\n", encoding="utf-8")
    _append_experiment_log(
        f"""
---

## This ticket — Awakening selection (one pinned PPO shot)

**Prompt:** Continue frozen Birth-exit π* under process-R for exactly AWAKENING_SELECT_PPO_TIMESTEPS=10000 on TRAIN seed 20260901. Freeze child. Evaluate-only A then B. No second shot.

**Train:** seed=20260901 timesteps={train.get('actual_timesteps')} optimizer_steps={train.get('optimizer_steps')} noop={train.get('select_noop')} child_sha16={(train.get('child_sha256') or '')[:16]} train_ticks={train.get('train_ticks_sha16')} train_price={train.get('train_price_sha16')}.

**Leg A** seed 20260902 hashes {table_a.get('ticks_sha16')}/{table_a.get('bars_sha16')} price={table_a.get('price_sha16')} class=`{table_a.get('classification')}` n={table_a.get('n')} wr_policy={table_a.get('wr_policy')} mean$={table_a.get('mean_usd_all')} sharpe={table_a.get('sharpe')} dd={table_a.get('dd_pct_of_50k')} stop×NEUTRAL={table_a.get('stop_x_neutral')}.

**Leg B** seed 20260903 hashes {table_b.get('ticks_sha16')}/{table_b.get('bars_sha16')} price={table_b.get('price_sha16')} class=`{table_b.get('classification')}` n={table_b.get('n')} wr_policy={table_b.get('wr_policy')} mean$={table_b.get('mean_usd_all')} sharpe={table_b.get('sharpe')} dd={table_b.get('dd_pct_of_50k')} stop×NEUTRAL={table_b.get('stop_x_neutral')}.

**Overall:** `{overall}`. Birth receipts stay PR #14. REAL=no. Evolution Proof stamped={proof.get('stamped')}.

**SSOT:** `AWAKENING_SELECT_AUDIT.md` / `AWAKENING_SELECT_VERDICT.md`
"""
    )


def main() -> int:
    os.environ["LUMINA_FABRIC_SUPERVISOR"] = "0"
    os.environ.setdefault("LUMINA_LOG_LEVEL", "INFO")
    sys.path.insert(0, str(REPO_ROOT))

    from lumina_core.birth.awakening_select import (
        BIRTH_EXIT_WINRATE,
        INIT_SHA256,
        STATUS_INCONCLUSIVE,
        assert_init_sha,
        overall_select_string,
        resolve_select_init_path,
        select_ledger_path,
        select_overfit,
    )
    from lumina_core.birth.birth_exit_policy_export import file_sha256
    from lumina_core.birth.awakening_select_path import inspect_select_protocol
    from lumina_core.birth.awakening_select_run import (
        dump_learn_traceback,
        run_select_eval_leg,
        run_select_train,
        select_leg_table,
    )
    from lumina_core.birth.awakening_mech import load_close_jsonl
    from lumina_core.birth.evolution_proof_gate import (
        evaluate_evolution_proof,
        evolution_proof_state_path,
        save_evolution_proof_record,
    )

    proto = inspect_select_protocol()
    if not proto.get("gate0_complete"):
        print(json.dumps({"status": STATUS_INCONCLUSIVE, "missing": proto.get("missing_sites")}, indent=2))
        return 2
    init_path = resolve_select_init_path(WS_A)
    init_sha = assert_init_sha(init_path)
    assert init_sha == INIT_SHA256

    try:
        train = run_select_train(reports=REPORTS)
    except Exception as exc:
        audit = REPORTS / "AWAKENING_SELECT_AUDIT.md"
        with audit.open("a", encoding="utf-8") as fh:
            fh.write("\n## GATE 1 — learn() failed\n\n```\n")
            fh.write(dump_learn_traceback(exc))
            fh.write("```\n\n**Status:** `SELECT_INCONCLUSIVE_AWAKENING_OPEN`. No invented zip.\n")
        print(json.dumps({"status": STATUS_INCONCLUSIVE, "error": str(exc)}, indent=2))
        return 1

    child = Path(str(train["child_path"]))
    fixture_a = _load_or_build_fixture(WS_A, seed=20260902, force=False)
    metrics_a = run_select_eval_leg(
        holdout=list(fixture_a["holdout"]),
        workspace_root=WS_A,
        reports_dir=REPORTS,
        ledger_path=select_ledger_path(REPORTS, leg="A"),
        policy_path=child,
    )
    rows_a = load_close_jsonl(select_ledger_path(REPORTS, leg="A"))
    table_a = select_leg_table(
        rows_a,
        grind_metrics=metrics_a,
        ticks_sha16=str(fixture_a["ticks_sha16"]),
        bars_sha16=str(fixture_a["bars_sha16"]),
        price_sha16_value=str(fixture_a["price_sha16"]),
        frozen_sha256=str(train["child_sha256"]),
    )

    fixture_b = _load_or_build_fixture(WS_B, seed=20260903, force=True)
    metrics_b = run_select_eval_leg(
        holdout=list(fixture_b["holdout"]),
        workspace_root=WS_B,
        reports_dir=REPORTS,
        ledger_path=select_ledger_path(REPORTS, leg="B"),
        policy_path=child,
    )
    rows_b = load_close_jsonl(select_ledger_path(REPORTS, leg="B"))
    table_b = select_leg_table(
        rows_b,
        grind_metrics=metrics_b,
        ticks_sha16=str(fixture_b["ticks_sha16"]),
        bars_sha16=str(fixture_b["bars_sha16"]),
        price_sha16_value=str(fixture_b["price_sha16"]),
        frozen_sha256=str(train["child_sha256"]),
    )

    overfit = select_overfit(
        wr_policy_a=float(table_a["wr_policy"]),
        wr_policy_b=float(table_b["wr_policy"]),
    )
    overall = overall_select_string(
        str(table_a["classification"]),
        str(table_b["classification"]),
        overfit=overfit,
        noop=bool(train["select_noop"]),
    )
    n_b = int(table_b["n"])
    wr_b = float(table_b["wr_policy"])
    proof_eval = evaluate_evolution_proof(
        birth_exit_winrate=BIRTH_EXIT_WINRATE,
        polish_oos_winrate=wr_b,
        holdout_trades=n_b,
    )
    stamped = False
    payload = {
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "passed": False,
        "reasons": list(proof_eval.reasons),
        "birth_exit_winrate": proof_eval.birth_exit_winrate,
        "polish_oos_winrate": wr_b,
        "winrate_source": "wr_policy_B",
        "winrate_lift": proof_eval.winrate_lift,
        "holdout_trades": n_b,
        "overall": overall,
        "select_overfit": overfit,
        "source": "awakening_select_oos_B",
    }
    if (
        overall.startswith("GRIND_STABLE_AWAKENING_OPEN")
        and not overfit
        and n_b >= 500
        and proof_eval.passed
    ):
        payload["passed"] = True
        save_evolution_proof_record(PROOF_WS, payload)
        stamped = True
    else:
        payload["passed"] = False
        save_evolution_proof_record(PROOF_WS, payload)

    proof = {
        "passed_inequalities": bool(proof_eval.passed),
        "reasons": list(proof_eval.reasons),
        "stamped": stamped,
        "n_b": n_b,
        "wr_policy_b": wr_b,
        "path": str(evolution_proof_state_path(PROOF_WS)),
    }
    _write_verdict(
        overall=overall,
        table_a=table_a,
        table_b=table_b,
        proof=proof,
        train=train,
        init_sha=file_sha256(init_path),
    )
    with (REPORTS / "AWAKENING_SELECT_AUDIT.md").open("a", encoding="utf-8") as fh:
        fh.write("\n## GATE 1 — freeze\n\n")
        fh.write(json.dumps({k: train[k] for k in train if k != "sidecar"}, indent=2, default=str))
        fh.write("\n\n## GATE 2 — child tables\n\n")
        fh.write(json.dumps({"A": table_a, "B": table_b, "overall": overall, "proof": proof}, indent=2, default=str))
        fh.write("\n")
    print(json.dumps({"overall": overall, "stamped": stamped, "noop": train.get("select_noop")}, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

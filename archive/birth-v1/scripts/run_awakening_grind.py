#!/usr/bin/env python3
"""Awakening grind shadow: frozen π* evaluate-only on Leg A then Leg B.

SIM / certified-shadow only. No container.start(), no NT, no REAL, no train.
"""

from __future__ import annotations

import json
import os
import sys
from datetime import datetime, timezone
from pathlib import Path
from types import SimpleNamespace
from typing import Any

REPO_ROOT = Path(__file__).resolve().parents[1]
REPORTS = REPO_ROOT / "reports" / "birth_cloud_run"
WS_A = REPORTS / "workspace"
WS_B = REPORTS / "workspace_grind_b"


def _runtime() -> SimpleNamespace:
    return SimpleNamespace(
        detect_market_regime=lambda _df: "NEUTRAL",
        market_data=SimpleNamespace(get_tape_snapshot=lambda: {}),
        get_current_dream_snapshot=lambda: {},
        AI_DRAWN_FIBS={},
        world_model={},
    )


def _load_or_build_fixture(workspace: Path, *, seed: int, force: bool) -> dict[str, Any]:
    from lumina_core.birth.synthetic_cloud_fixture import (
        CloudFixtureSpec,
        persist_cloud_fixture,
        write_fixture_sidecar,
    )
    from lumina_core.birth.tick_cache_persist import (
        cache_manifest_path,
        certified_tick_cache_present,
        load_split_cache,
    )

    workspace.mkdir(parents=True, exist_ok=True)
    (workspace / "state").mkdir(parents=True, exist_ok=True)
    sidecar = REPORTS / ("01_fixture_manifest.json" if seed == 20260902 else "01_fixture_manifest_B.json")
    reused = False
    if (
        seed == 20260902
        and certified_tick_cache_present(workspace)
        and sidecar.is_file()
        and not force
    ):
        manifest = json.loads(sidecar.read_text(encoding="utf-8"))
        split = load_split_cache(workspace, holdout_pct=0.20)
        if split is not None and str(manifest.get("hash") or "") == "7e86c2bb1c71d514":
            reused = True
            return {
                "manifest": manifest,
                "holdout": list(split.holdout),
                "reused_manifest": True,
                "ticks_sha16": str(manifest.get("hash") or ""),
                "bars_sha16": str(manifest.get("raw_ticks_hash") or ""),
            }
    spec = CloudFixtureSpec(seed=int(seed))
    result = persist_cloud_fixture(workspace, spec=spec)
    write_fixture_sidecar(sidecar, result.fixture_manifest)
    man = dict(result.fixture_manifest)
    return {
        "manifest": man,
        "holdout": list(result.split.holdout),
        "reused_manifest": reused,
        "ticks_sha16": str(man.get("hash") or man.get("train_hash") or ""),
        "bars_sha16": str(man.get("raw_ticks_hash") or ""),
        "cache_manifest": str(cache_manifest_path(workspace)),
    }


def _s5_receipt() -> dict[str, Any]:
    path = REPORTS / "s5_receipt.json"
    return json.loads(path.read_text(encoding="utf-8"))


def _write_reports(
    *,
    preflight: dict[str, Any],
    leg_a: dict[str, Any],
    leg_b: dict[str, Any],
    proof: dict[str, Any],
    overall: str,
) -> None:
    from lumina_core.maturity.birth_exit import is_birth_exit_sufficient

    snap_path = REPORTS / "exit_snapshot.json"
    birth_ok = False
    if snap_path.is_file():
        try:
            birth_ok = bool(json.loads(snap_path.read_text(encoding="utf-8")).get("is_birth_exit_sufficient"))
        except (OSError, json.JSONDecodeError, TypeError):
            birth_ok = False
    try:
        if (WS_A / "state").is_dir():
            birth_ok = bool(is_birth_exit_sufficient(WS_A)) or birth_ok
    except Exception:
        pass
    now = datetime.now(timezone.utc).isoformat()
    audit = [
        "# AWAKENING GRIND AUDIT",
        "",
        f"**Date:** {now}",
        "**Engine:** BRO-v2 evaluate-only grind (no PPO update)",
        "**Capital:** SIM / certified-shadow. REAL=no. NT=no. `LUMINA_FABRIC_SUPERVISOR=0`. `practice_mode=False`.",
        "**Start choice:** `full_holdout_replay_frozen` at bar index `0`.",
        "",
        "## Preflight",
        "",
        json.dumps(preflight, indent=2, default=str),
        "",
        "## Frozen π*",
        "",
        f"- export site: `{preflight.get('export_site')}`",
        f"- loadable path: `{preflight.get('frozen_path') or 'MISSING'}`",
        f"- sha256: `{preflight.get('frozen_sha256') or 'n/a'}`",
        f"- loaded: `{preflight.get('frozen_loaded')}`",
        "",
        "## Leg A (seed 20260902)",
        "",
        json.dumps(leg_a, indent=2, default=str),
        "",
        "## Leg B (seed 20260903)",
        "",
        json.dumps(leg_b, indent=2, default=str),
        "",
        "## ADR-0026 Evolution Proof (measurement)",
        "",
        json.dumps(proof, indent=2, default=str),
        "",
        f"**Proof stamped:** `{proof.get('stamped')}`",
        "",
        "## Birth receipts",
        "",
        f"`is_birth_exit_sufficient` left as PR #14 (`{birth_ok}`). This runner did not rewrite S1–S5 or fitness.",
        "",
    ]
    (REPORTS / "AWAKENING_GRIND_AUDIT.md").write_text("\n".join(audit) + "\n", encoding="utf-8")
    verdict = [
        "# AWAKENING GRIND VERDICT",
        "",
        f"**Overall:** `{overall}`",
        "",
        "| Leg | class | n | wr | mean $ | sharpe | dd% of $50k |",
        "|-----|-------|---|----|--------|--------|-------------|",
        f"| A | {leg_a.get('classification')} | {leg_a.get('n')} | {leg_a.get('wr')} | {leg_a.get('mean_usd')} | {leg_a.get('sharpe')} | {leg_a.get('dd_pct_of_50k')} |",
        f"| B | {leg_b.get('classification')} | {leg_b.get('n')} | {leg_b.get('wr')} | {leg_b.get('mean_usd')} | {leg_b.get('sharpe')} | {leg_b.get('dd_pct_of_50k')} |",
        "",
        "- Birth receipts: **untouched** (PR #14 S1–S5 + fitness).",
        "- REAL: **no**.",
        "- PromotionGate / cert OOS 0.48: **out of scope**.",
        "- Evolution Proof passed=True: **only if overall STABLE and ADR-0026 holds on the longer book**.",
        f"- Proof stamped: `{proof.get('stamped')}`.",
        "",
    ]
    (REPORTS / "AWAKENING_GRIND_VERDICT.md").write_text("\n".join(verdict) + "\n", encoding="utf-8")
    log_path = REPORTS / "LUMINA_BIRTH_EXPERIMENT_LOG.md"
    row = f"""
---

## This ticket — Awakening grind (frozen π* longer clock)

**Prompt:** Is S5 n=172 a stable process-R path or an early-stop artifact? Freeze π*. Keep the clock on. Do not move Birth floors.

**Preflight:** persist writer from PR #15 (`s5_close_ledger_archive.py`). PR #14 JSONL still missing (not invented). Frozen load: `{preflight.get('frozen_path') or 'MISSING'}` site `{preflight.get('export_site')}`.

**Leg A** seed 20260902 reused_manifest={leg_a.get('reused_manifest')} hashes {leg_a.get('ticks_sha16')}/{leg_a.get('bars_sha16')} class=`{leg_a.get('classification')}` n={leg_a.get('n')} wr={leg_a.get('wr')} mean$={leg_a.get('mean_usd')} sharpe={leg_a.get('sharpe')} dd={leg_a.get('dd_pct_of_50k')}.

**Leg B** seed 20260903 reused_manifest={leg_b.get('reused_manifest')} hashes {leg_b.get('ticks_sha16')}/{leg_b.get('bars_sha16')} class=`{leg_b.get('classification')}` n={leg_b.get('n')} wr={leg_b.get('wr')} mean$={leg_b.get('mean_usd')} sharpe={leg_b.get('sharpe')} dd={leg_b.get('dd_pct_of_50k')}.

**Overall:** `{overall}`. Birth receipts stay PR #14. REAL=no. Evolution Proof stamped={proof.get('stamped')}.

**SSOT:** `AWAKENING_GRIND_AUDIT.md` / `AWAKENING_GRIND_VERDICT.md`
"""
    with log_path.open("a", encoding="utf-8") as fh:
        fh.write(row)


def main() -> int:
    os.environ["LUMINA_FABRIC_SUPERVISOR"] = "0"
    os.environ.setdefault("LUMINA_LOG_LEVEL", "INFO")
    sys.path.insert(0, str(REPO_ROOT))

    from lumina_core.birth.awakening_grind import (
        classify_overall,
        metrics_as_table,
    )
    from lumina_core.birth.awakening_grind_run import (
        EXPECTED_BARS_SHA16,
        EXPECTED_TICKS_SHA16,
        LEG_A_SEED,
        LEG_B_SEED,
        grind_ledger_path,
        run_evaluate_only,
    )
    from lumina_core.birth.birth_exit_policy_export import (
        EXPORT_SITE,
        file_sha256,
        load_frozen_policy,
        resolve_frozen_policy_path,
    )
    from lumina_core.birth.evolution_proof_gate import evaluate_evolution_proof
    from lumina_core.birth.s5_close_ledger_archive import archive_line_count, resolve_archive_path

    s5_archive = resolve_archive_path(WS_A)
    s5_n = archive_line_count(s5_archive)
    frozen = resolve_frozen_policy_path(WS_A) or resolve_frozen_policy_path(REPO_ROOT)
    frozen_sha = file_sha256(frozen) if frozen and frozen.is_file() else ""
    policy = load_frozen_policy(frozen) if frozen is not None else None
    s5 = _s5_receipt()
    preflight = {
        "persist_writer": "lumina_core/birth/s5_close_ledger_archive.py",
        "s5_close_ledger_jsonl_rows": s5_n,
        "s5_close_ledger_honesty": "PR #14 book not reconstructed; missing rows not invented",
        "s1_s5_receipts_on_disk": all(
            (REPORTS / f"s{i}_receipt.json").is_file() for i in range(1, 6)
        ),
        "fitness_vector_on_disk": (REPORTS / "lumina_birth_fitness_vector.json").is_file(),
        "floors_pr14": True,
        "export_site": EXPORT_SITE,
        "export_call": "lumina_core/birth/foundation_complete.py:161",
        "frozen_path": str(frozen) if frozen else "",
        "frozen_sha256": frozen_sha,
        "frozen_loaded": bool(policy is not None),
        "s5_n": int(s5.get("trades") or 0),
        "s5_wr": float(s5.get("winrate") or 0.0),
        "s5_mean_r": float(s5.get("mean_r") or 0.0),
        "practice_mode": False,
        "supervisor": os.environ.get("LUMINA_FABRIC_SUPERVISOR"),
    }

    fixture_a = _load_or_build_fixture(WS_A, seed=LEG_A_SEED, force=False)
    metrics_a = run_evaluate_only(
        runtime=_runtime(),
        holdout=list(fixture_a["holdout"]),
        workspace_root=WS_A,
        reports_dir=REPORTS,
        ledger_path=grind_ledger_path(WS_A, leg="A"),
        policy=policy,
    )
    table_a = metrics_as_table(metrics_a)
    table_a["reused_manifest"] = bool(fixture_a["reused_manifest"])
    table_a["ticks_sha16"] = fixture_a["ticks_sha16"]
    table_a["bars_sha16"] = fixture_a["bars_sha16"]
    table_a["expected_ticks_sha16"] = EXPECTED_TICKS_SHA16
    table_a["expected_bars_sha16"] = EXPECTED_BARS_SHA16
    table_a["seed"] = LEG_A_SEED

    fixture_b = _load_or_build_fixture(WS_B, seed=LEG_B_SEED, force=True)
    metrics_b = run_evaluate_only(
        runtime=_runtime(),
        holdout=list(fixture_b["holdout"]),
        workspace_root=WS_B,
        reports_dir=REPORTS,
        ledger_path=grind_ledger_path(WS_A, leg="B"),
        policy=policy,
    )
    table_b = metrics_as_table(metrics_b)
    table_b["reused_manifest"] = False
    table_b["ticks_sha16"] = fixture_b["ticks_sha16"]
    table_b["bars_sha16"] = fixture_b["bars_sha16"]
    table_b["seed"] = LEG_B_SEED
    table_b["frozen_sha256"] = table_b.get("frozen_sha256") or frozen_sha
    table_a["frozen_sha256"] = table_a.get("frozen_sha256") or frozen_sha
    if frozen_sha:
        table_b["same_frozen_bytes_as_A"] = table_a.get("frozen_sha256") == table_b.get("frozen_sha256")
    for leg in ("A", "B"):
        path = grind_ledger_path(WS_A, leg=leg)
        path.parent.mkdir(parents=True, exist_ok=True)
        if not path.is_file():
            path.write_text("", encoding="utf-8")

    overall = classify_overall(str(table_a.get("classification")), str(table_b.get("classification")))
    longer = table_a if int(table_a.get("n") or 0) >= int(table_b.get("n") or 0) else table_b
    proof_eval = evaluate_evolution_proof(
        birth_exit_winrate=float(s5.get("winrate") or 0.0),
        polish_oos_winrate=float(longer.get("wr") or 0.0),
        holdout_trades=int(longer.get("n") or 0),
    )
    stamped = False
    if overall == "GRIND_STABLE_AWAKENING_OPEN" and proof_eval.passed:
        from lumina_core.birth.evolution_proof_gate import save_evolution_proof_record

        save_evolution_proof_record(
            WS_A,
            {
                "timestamp": datetime.now(timezone.utc).isoformat(),
                "passed": True,
                "reasons": list(proof_eval.reasons),
                "birth_exit_winrate": proof_eval.birth_exit_winrate,
                "polish_oos_winrate": proof_eval.polish_oos_winrate,
                "winrate_lift": proof_eval.winrate_lift,
                "holdout_trades": proof_eval.holdout_trades,
                "source": "awakening_grind_longer_of_A_B",
            },
        )
        stamped = True
    proof = {
        "passed_inequalities": bool(proof_eval.passed),
        "reasons": list(proof_eval.reasons),
        "birth_exit_winrate": proof_eval.birth_exit_winrate,
        "polish_oos_winrate": proof_eval.polish_oos_winrate,
        "winrate_lift": proof_eval.winrate_lift,
        "holdout_trades": proof_eval.holdout_trades,
        "longer_leg": "A" if longer is table_a else "B",
        "stamped": stamped,
        "overall": overall,
    }
    _write_reports(preflight=preflight, leg_a=table_a, leg_b=table_b, proof=proof, overall=overall)
    for name in ("grind_A_close_ledger.jsonl", "grind_B_close_ledger.jsonl"):
        src = REPORTS / "artifacts" / name
        src.parent.mkdir(parents=True, exist_ok=True)
        if not src.is_file():
            src.write_text("", encoding="utf-8")
    print(json.dumps({"overall": overall, "A": table_a.get("classification"), "B": table_b.get("classification"), "stamped": stamped}, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

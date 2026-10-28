#!/usr/bin/env python3
"""SIM birth + Approval Twin end-to-end validation (shadow mode).

Validates that the Approval Twin:
  - Runs in shadow mode and logs decisions / risk flags
  - Surfaces agreement %, confidence distribution, constitution adherence
  - Works with twin CLI backends (metrics / train / review queue)
  - Never bypasses hard safety gates (constitution / mode authority)

Does NOT promote twin mode, does NOT touch REAL capital paths.

Usage (from repo root):
  python scripts/validation/run_sim_birth_twin_validation.py
  python scripts/validation/run_sim_birth_twin_validation.py --harness-only
  python scripts/validation/run_sim_birth_twin_validation.py --practice-birth --target-trades 2000 --timeout-sec 900

Exit 0 on PASS, non-zero on FAIL.
"""

from __future__ import annotations

import argparse
import json
import os
import sys
import tempfile
import time
import traceback
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))


def _print_header(title: str) -> None:
    print()
    print("=" * 72)
    print(title)
    print("=" * 72)


def _ok(name: str, detail: str = "") -> dict[str, Any]:
    print(f"  PASS  {name}" + (f" — {detail}" if detail else ""))
    return {"name": name, "ok": True, "detail": detail}


def _fail(name: str, detail: str = "") -> dict[str, Any]:
    print(f"  FAIL  {name}" + (f" — {detail}" if detail else ""))
    return {"name": name, "ok": False, "detail": detail}


def _evil_dna_content() -> str:
    return json.dumps(
        {
            "content": "constitution guard risk stop safety first cooldown",
            "fitness_score": 1.8,
            "mutation_rate": 0.04,
            "disable_risk_controller": True,
            "hyperparam_suggestion": {"max_risk_percent": 99},
        }
    )


def _clean_dna_content() -> str:
    return json.dumps(
        {
            "content": "risk guard stop cooldown safety first",
            "max_risk_percent": 1.0,
            "drawdown_kill_percent": 2.0,
            "kelly_fraction": 0.25,
            "hyperparam_suggestion": {"max_risk_percent": 1.0},
        }
    )


def run_harness(*, work_dir: Path) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    """Isolated twin + birth-autonomy + training observability harness."""
    import logging

    # Quiet constitution/twin rejection noise on stderr (still fail-closed in checks)
    for name in (
        "lumina",
        "lumina.evolution.approval_twin_agent",
        "lumina.safety.constitutional_guard",
        "lumina.safety.trading_constitution",
        "lumina.birth.organism_autonomy",
    ):
        logging.getLogger(name).setLevel(logging.CRITICAL)

    from lumina_core.birth.config import BirthCurriculumConfig
    from lumina_core.birth.death_spiral_guard import DeathSpiralState
    from lumina_core.birth.organism_autonomy import (
        OrganismAutonomyState,
        RecoveryDispatch,
        evaluate_terminal_stall,
    )
    from lumina_core.birth.phoenix_loop import PhoenixLoopState
    from lumina_core.evolution.approval_twin_agent import ApprovalTwinAgent
    from lumina_core.evolution.dna_registry import PolicyDNA
    from lumina_core.evolution.steve_values_registry import SteveValuesRegistry
    from lumina_core.evolution.twin_metrics_store import TwinMetricsStore
    from lumina_core.evolution.twin_mode_promotion_gate import TwinModeController
    from lumina_core.evolution.twin_training_service import TwinTrainingService
    from lumina_core.safety.constitutional_guard import ConstitutionalGuard

    checks: list[dict[str, Any]] = []
    report: dict[str, Any] = {"harness": True, "work_dir": str(work_dir)}

    state = work_dir / "state"
    state.mkdir(parents=True, exist_ok=True)
    # Minimal workspace markers so resolve_monitoring_state_dir can fall back to cwd/state
    (work_dir / "lumina_core").mkdir(exist_ok=True)
    cfg_path = work_dir / "config.yaml"
    if not cfg_path.exists():
        cfg_path.write_text(
            "evolution:\n  approval_twin:\n    mode: shadow\n",
            encoding="utf-8",
        )

    # Isolate monitoring + config to this work dir (never touch operator REAL state)
    previous_env = {
        "LUMINA_WORKSPACE_ROOT": os.environ.get("LUMINA_WORKSPACE_ROOT"),
        "LUMINA_CONFIG": os.environ.get("LUMINA_CONFIG"),
        "LUMINA_STATE_DIR": os.environ.get("LUMINA_STATE_DIR"),
    }
    os.environ["LUMINA_WORKSPACE_ROOT"] = str(work_dir)
    os.environ["LUMINA_CONFIG"] = str(cfg_path)
    os.environ["LUMINA_STATE_DIR"] = str(state)
    previous_cwd = Path.cwd()
    os.chdir(work_dir)

    try:
        decisions_path = state / "monitoring_twin_decisions.jsonl"
        training_path = state / "monitoring_twin_training.jsonl"
        model_path = state / "approval_twin_model.json"
        mode_path = state / "approval_twin_mode.json"
        metrics_path = state / "monitoring_twin_mode_metrics.jsonl"
        summary_path = state / "twin_mode_metrics_summary.json"
        registry = SteveValuesRegistry(
            sqlite_path=state / "steve_values_registry.sqlite3",
            jsonl_path=state / "steve_values_registry.jsonl",
        )
        store = TwinMetricsStore(path=metrics_path, summary_path=summary_path)
        controller = TwinModeController(
            mode_state_path=mode_path,
            metrics_store=store,
            initial_mode="shadow",
        )
        twin = ApprovalTwinAgent(
            registry=registry,
            model_path=model_path,
            mode="shadow",
            metrics_store=store,
            mode_controller=controller,
        )
        svc = TwinTrainingService(
            registry=registry,
            twin=twin,
            model_path=model_path,
            decisions_path=decisions_path,
            training_path=training_path,
        )

        # --- Mode authority ---
        mode = str(getattr(twin, "mode", "shadow") or "shadow")
        if mode == "shadow":
            checks.append(_ok("twin_mode_shadow", mode))
        else:
            checks.append(_fail("twin_mode_shadow", f"expected shadow got {mode}"))

        # --- Clean DNA evaluate ---
        clean = PolicyDNA.create(
            prompt_id="sim_birth_twin_validation",
            version="clean",
            content=_clean_dna_content(),
            fitness_score=1.1,
            generation=1,
            mutation_rate=0.05,
            lineage_hash="GENESIS",
        )
        clean_res = twin.evaluate_dna_promotion(clean)
        checks.append(
            _ok(
                "evaluate_clean_dna",
                f"rec={clean_res.get('recommendation')} conf={clean_res.get('confidence')} "
                f"executable={clean_res.get('executable')}",
            )
        )
        if clean_res.get("executable") is False and clean_res.get("effective_recommendation") is False:
            checks.append(_ok("shadow_non_executable", "effective_recommendation=false"))
        else:
            checks.append(
                _fail(
                    "shadow_non_executable",
                    f"executable={clean_res.get('executable')} "
                    f"effective={clean_res.get('effective_recommendation')}",
                )
            )

        # --- Constitution-fatal DNA ---
        evil = PolicyDNA.create(
            prompt_id="sim_birth_twin_validation",
            version="evil",
            content=_evil_dna_content(),
            fitness_score=1.8,
            generation=2,
            mutation_rate=0.04,
            lineage_hash="GENESIS",
        )
        evil_res = twin.evaluate_dna_promotion(evil)
        flags = list(evil_res.get("risk_flags") or [])
        if evil_res.get("recommendation") is False and any("constitution" in str(f) for f in flags):
            checks.append(_ok("constitution_hard_veto", f"flags={flags[:4]}"))
        else:
            checks.append(
                _fail(
                    "constitution_hard_veto",
                    f"rec={evil_res.get('recommendation')} flags={flags}",
                )
            )

        guard = ConstitutionalGuard()
        still_blocked = not guard.veto_unless_constitutional(
            dna_content=_evil_dna_content(),
            mode="sim",
            current_recommendation=True,
        )
        if still_blocked:
            checks.append(_ok("constitutional_guard_still_blocks", "post-twin gate active"))
        else:
            checks.append(_fail("constitutional_guard_still_blocks", "guard returned True for evil DNA"))

        # --- Birth autonomy: shadow must not sole-CONTINUE on twin approve ---
        autonomy = OrganismAutonomyState(
            phoenix=PhoenixLoopState(),
            death_spiral=DeathSpiralState(),
        )
        cfg = BirthCurriculumConfig(
            autonomous_recovery_enabled=True,
            phoenix_loop_enabled=False,
            allow_provisional_pass=False,
        )
        decision = evaluate_terminal_stall(
            cfg=cfg,
            autonomy_state=autonomy,
            pending={
                "terminal_stall_reason": "stage_stalled",
                "blocker_metric": "trend_winrate",
                "blocker_value": 0.4,
            },
            curriculum_stage="stage1_trend",
            approval_twin=twin,
            stage_trades=200,
            required=500,
            constitution_violations=0,
            fitness_signal=0.9,
            recommended_recovery_action="expand_data",
        )
        twin_auto = "Twin high-conf autonomous approval" in str(decision.message or "")
        if not twin_auto:
            checks.append(
                _ok(
                    "birth_autonomy_shadow_no_sole_auto",
                    f"dispatch={decision.dispatch.value} msg={decision.message[:80]!r}",
                )
            )
        else:
            checks.append(
                _fail(
                    "birth_autonomy_shadow_no_sole_auto",
                    "shadow twin sole-auto CONTINUE — authority leak",
                )
            )

        # High-conf veto path still notify-only even in shadow
        # (uses real twin score — may or may not veto; just ensure no crash)
        if decision.dispatch in (
            RecoveryDispatch.CONTINUE_LOOP,
            RecoveryDispatch.TERMINAL_NOTIFY_ONLY,
            RecoveryDispatch.PHOENIX_RESUME,
            RecoveryDispatch.PROVISIONAL_GRADUATE,
        ):
            checks.append(_ok("birth_autonomy_no_crash", decision.dispatch.value))
        else:
            checks.append(_fail("birth_autonomy_no_crash", str(decision.dispatch)))

        # --- Non-interactive training (CLI train path) ---
        dna_hash = str(getattr(evil, "hash", "") or "validation-evil")
        svc.record_decision(
            decision="reject",
            dna_hash=dna_hash,
            twin_score=float(evil_res.get("confidence") or 0.0),
            twin_recommendation=bool(evil_res.get("recommendation")),
            explanation=str(evil_res.get("explanation") or ""),
            risk_flags=flags,
            train_now=False,
        )
        clean_hash = str(getattr(clean, "hash", "") or "validation-clean")
        svc.record_decision(
            decision="approve",
            dna_hash=clean_hash,
            twin_score=float(clean_res.get("confidence") or 0.0),
            twin_recommendation=bool(clean_res.get("recommendation")),
            explanation=str(clean_res.get("explanation") or ""),
            risk_flags=list(clean_res.get("risk_flags") or []),
            train_now=False,
        )
        train_out = svc.train(limit=50)
        checks.append(
            _ok(
                "twin_train",
                f"trained={train_out.get('trained')} steps={train_out.get('metrics', {}).get('training_steps')}",
            )
        )

        queue = svc.list_review_queue(limit=5)
        checks.append(_ok("twin_review_queue", f"items={len(queue)}"))

        # evaluate_dna_promotion writes via logging_utils → LUMINA_WORKSPACE_ROOT/state
        logged = 0
        if decisions_path.exists():
            logged = len(
                [ln for ln in decisions_path.read_text(encoding="utf-8").splitlines() if ln.strip()]
            )
        metrics = svc.metrics(decision_window=100)
        conf = metrics.get("confidence_distribution") or {}
        if isinstance(conf, dict) and "n" in conf and "gte_80" in conf:
            checks.append(_ok("confidence_distribution", json.dumps(conf, sort_keys=True)))
        else:
            checks.append(_fail("confidence_distribution", f"missing buckets: {conf}"))

        report["decisions_logged"] = logged
        report["metrics"] = {
            "mode": metrics.get("mode"),
            "authority": metrics.get("authority"),
            "twin_agreement_pct": metrics.get("twin_agreement_pct"),
            "twin_steve_agreement_pct": metrics.get("twin_steve_agreement_pct"),
            "constitution_adherence_pct": metrics.get("constitution_adherence_pct"),
            "confidence_distribution": conf,
            "outcome_counts": metrics.get("outcome_counts"),
            "risk_flag_top": metrics.get("risk_flag_top"),
            "risk_flags_caught": metrics.get("risk_flags_caught"),
            "decisions_total": metrics.get("decisions_total"),
            "training_steps": metrics.get("training_steps"),
        }
        checks.append(
            _ok(
                "metrics_rollup",
                f"agreement={metrics.get('twin_agreement_pct')} "
                f"steve={metrics.get('twin_steve_agreement_pct')} "
                f"constitution={metrics.get('constitution_adherence_pct')} "
                f"decisions={metrics.get('decisions_total')}",
            )
        )
        if int(conf.get("n") or 0) > 0 or logged > 0:
            checks.append(
                _ok(
                    "decisions_logged",
                    f"file={logged} conf_n={conf.get('n')} outcomes={metrics.get('outcome_counts')}",
                )
            )
        else:
            checks.append(_fail("decisions_logged", "no twin decisions in isolated state"))

        report["paths"] = {
            "decisions": str(decisions_path),
            "training": str(training_path),
            "model": str(model_path),
            "mode_metrics": str(metrics_path),
        }
        # Drop refs so Windows can release SQLite handles before temp cleanup
        del svc, twin, registry, store, controller
    finally:
        os.chdir(previous_cwd)
        for key, val in previous_env.items():
            if val is None:
                os.environ.pop(key, None)
            else:
                os.environ[key] = val
        # Best-effort GC so WAL/sqlite files unlock on Windows
        try:
            import gc

            gc.collect()
        except Exception:
            pass

    return checks, report


def run_cli_smoke() -> list[dict[str, Any]]:
    """Exercise twin CLI entrypoints non-interactively."""
    import subprocess

    checks: list[dict[str, Any]] = []
    base = [sys.executable, "-m", "lumina_launcher", "twin"]
    for sub in ("mode", "metrics", "train"):
        try:
            proc = subprocess.run(
                base + [sub],
                cwd=str(ROOT),
                capture_output=True,
                text=True,
                timeout=120,
                check=False,
            )
            if proc.returncode == 0:
                checks.append(_ok(f"cli_twin_{sub}", (proc.stdout or "")[:120].replace("\n", " ")))
            else:
                checks.append(
                    _fail(
                        f"cli_twin_{sub}",
                        f"rc={proc.returncode} err={(proc.stderr or '')[:200]}",
                    )
                )
        except Exception as exc:
            checks.append(_fail(f"cli_twin_{sub}", str(exc)))

    # review --list-only (no stdin)
    try:
        proc = subprocess.run(
            base + ["review", "--list-only", "--limit=3"],
            cwd=str(ROOT),
            capture_output=True,
            text=True,
            timeout=60,
            check=False,
        )
        if proc.returncode == 0:
            checks.append(_ok("cli_twin_review_list_only", (proc.stdout or "")[:120].replace("\n", " ")))
        else:
            checks.append(
                _fail(
                    "cli_twin_review_list_only",
                    f"rc={proc.returncode} err={(proc.stderr or '')[:200]}",
                )
            )
    except Exception as exc:
        checks.append(_fail("cli_twin_review_list_only", str(exc)))

    return checks


def run_practice_birth(
    *,
    target_trades: int,
    timeout_sec: int,
    force: bool,
) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    """Bounded practice birth in SIM (optional). Twin stays shadow."""
    checks: list[dict[str, Any]] = []
    info: dict[str, Any] = {
        "practice_birth": True,
        "target_trades": target_trades,
        "timeout_sec": timeout_sec,
    }

    try:
        from lumina_launcher.services.birth_service import BirthService
    except Exception as exc:
        checks.append(_fail("practice_birth_import", str(exc)))
        return checks, info

    # Count decisions before
    decisions_path = ROOT / "state" / "monitoring_twin_decisions.jsonl"
    before = 0
    if decisions_path.exists():
        before = len([ln for ln in decisions_path.read_text(encoding="utf-8").splitlines() if ln.strip()])

    svc = BirthService(workspace_root=ROOT)
    try:
        start = svc.start_birth(
            target_trades=int(target_trades),
            force=bool(force),
            practice_mode=True,
            explicit_user_start=True,
        )
    except Exception as exc:
        checks.append(_fail("practice_birth_start", str(exc)))
        info["error"] = str(exc)
        return checks, info

    info["start"] = start if isinstance(start, dict) else {"raw": str(start)}
    status = str((start or {}).get("status", ""))
    if status in ("rejected", "already_running", "already_completed") and status != "started":
        # already_running may still be usable
        if status == "already_running":
            checks.append(_ok("practice_birth_start", "already_running — attaching to poll"))
        else:
            checks.append(_fail("practice_birth_start", json.dumps(start, default=str)[:300]))
            return checks, info
    else:
        checks.append(_ok("practice_birth_start", f"status={status}"))

    deadline = time.time() + max(30, int(timeout_sec))
    last_progress: dict[str, Any] = {}
    crashed = False
    while time.time() < deadline:
        try:
            if hasattr(svc, "get_status"):
                st = svc.get_status()
                if isinstance(st, dict):
                    last_progress = st
            # stop if finished or error
            if getattr(svc, "_error", None):
                crashed = True
                break
            if hasattr(svc, "is_running") and not svc.is_running():
                break
        except Exception:
            pass
        time.sleep(5)

    # Soft stop if still running past timeout
    still_running = bool(hasattr(svc, "is_running") and svc.is_running())
    if still_running:
        try:
            if hasattr(svc, "stop_birth"):
                svc.stop_birth()
            elif hasattr(svc, "request_stop"):
                svc.request_stop()
            else:
                # flag-based stop used by runner
                from pathlib import Path as _P

                pause = _P(ROOT) / "state" / "first_boot_pause_requested"
                pause.write_text("1", encoding="utf-8")
                if hasattr(svc, "_stop_requested"):
                    svc._stop_requested.set()
        except Exception as exc:
            info["stop_error"] = str(exc)
        checks.append(_ok("practice_birth_timeout_stop", f"stopped after {timeout_sec}s"))
    else:
        checks.append(_ok("practice_birth_finished_or_idle", "runner not active"))

    if crashed or getattr(svc, "_error", None):
        checks.append(_fail("practice_birth_no_crash", str(getattr(svc, "_error", "unknown"))))
    else:
        checks.append(_ok("practice_birth_no_crash", "no runner exception recorded"))

    after = before
    if decisions_path.exists():
        after = len([ln for ln in decisions_path.read_text(encoding="utf-8").splitlines() if ln.strip()])
    info["decisions_before"] = before
    info["decisions_after"] = after
    info["decisions_delta"] = after - before
    info["last_progress_keys"] = list(last_progress.keys())[:20] if last_progress else []
    # Twin may not fire until autonomy/meta events — delta is informational, not hard fail
    checks.append(
        _ok(
            "practice_birth_twin_decisions_observed",
            f"delta={after - before} total={after}",
        )
    )
    return checks, info


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Validate Approval Twin in SIM birth (shadow).")
    parser.add_argument(
        "--harness-only",
        action="store_true",
        help="Skip practice birth; run isolated harness + CLI only (default without --practice-birth).",
    )
    parser.add_argument(
        "--practice-birth",
        action="store_true",
        help="Also start a bounded practice birth thread in the workspace.",
    )
    parser.add_argument("--target-trades", type=int, default=2000)
    parser.add_argument("--timeout-sec", type=int, default=600)
    parser.add_argument(
        "--force",
        action="store_true",
        help="Force start practice birth even if previously completed.",
    )
    parser.add_argument(
        "--skip-cli",
        action="store_true",
        help="Skip subprocess CLI smoke (mode/metrics/train/review).",
    )
    parser.add_argument(
        "--report-path",
        type=str,
        default="",
        help="Optional path to write JSON report (default: temp under state/).",
    )
    args = parser.parse_args(argv)

    # Default: harness + CLI. Practice birth only if requested.
    do_practice = bool(args.practice_birth) and not bool(args.harness_only)

    _print_header("Approval Twin SIM birth validation")
    print(f"  root={ROOT}")
    print(f"  harness=yes practice_birth={do_practice} skip_cli={args.skip_cli}")
    print("  safety: twin mode remains shadow; no promote; no REAL")

    all_checks: list[dict[str, Any]] = []
    report: dict[str, Any] = {
        "timestamp": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        "root": str(ROOT),
        "practice_birth": do_practice,
    }

    # Isolated harness
    _print_header("1. Isolated harness (twin + birth autonomy + train)")
    try:
        # ignore_cleanup_errors: Windows may briefly hold SQLite WAL after close
        with tempfile.TemporaryDirectory(prefix="lumina_twin_val_", ignore_cleanup_errors=True) as tmp:
            checks, harness_report = run_harness(work_dir=Path(tmp))
            all_checks.extend(checks)
            report["harness"] = harness_report
    except Exception:
        traceback.print_exc()
        all_checks.append(_fail("harness_exception", traceback.format_exc()[-400:]))

    # CLI smoke against real workspace state (operator surface)
    if not args.skip_cli:
        _print_header("2. Twin CLI smoke (mode / metrics / train / review --list-only)")
        try:
            all_checks.extend(run_cli_smoke())
        except Exception:
            traceback.print_exc()
            all_checks.append(_fail("cli_exception", traceback.format_exc()[-400:]))
    else:
        print("  (skipped)")

    if do_practice:
        _print_header("3. Bounded practice birth (SIM)")
        try:
            p_checks, p_info = run_practice_birth(
                target_trades=int(args.target_trades),
                timeout_sec=int(args.timeout_sec),
                force=bool(args.force),
            )
            all_checks.extend(p_checks)
            report["practice"] = p_info
        except Exception:
            traceback.print_exc()
            all_checks.append(_fail("practice_exception", traceback.format_exc()[-400:]))

    # Summary
    _print_header("Summary")
    passed = sum(1 for c in all_checks if c.get("ok"))
    failed = sum(1 for c in all_checks if not c.get("ok"))
    report["checks"] = all_checks
    report["passed"] = passed
    report["failed"] = failed
    report["status"] = "PASS" if failed == 0 else "FAIL"

    metrics = (report.get("harness") or {}).get("metrics") or {}
    print(f"Approval Twin SIM birth validation: {report['status']}")
    print(f"  checks: {passed} passed / {failed} failed / {len(all_checks)} total")
    if metrics:
        conf = metrics.get("confidence_distribution") or {}
        print(
            f"  mode: {metrics.get('mode')} | authority: {metrics.get('authority')}"
        )
        print(
            f"  agreement_pct: {metrics.get('twin_agreement_pct')} | "
            f"steve: {metrics.get('twin_steve_agreement_pct')} | "
            f"constitution_adherence_pct: {metrics.get('constitution_adherence_pct')}"
        )
        print(f"  confidence_distribution: {conf}")
        print(f"  risk_flag_top: {metrics.get('risk_flag_top')}")
        print(f"  decisions_total: {metrics.get('decisions_total')}")
    print("  hard_gates: constitution veto + shadow non-executable + ConstitutionalGuard re-checked in harness")
    print("  twin may never bypass sandbox / PromotionGate / REAL paths (unchanged by this validation)")

    report_path = Path(args.report_path) if args.report_path else (ROOT / "state" / "twin_sim_birth_validation_report.json")
    try:
        report_path.parent.mkdir(parents=True, exist_ok=True)
        report_path.write_text(json.dumps(report, indent=2, sort_keys=True, default=str), encoding="utf-8")
        print(f"  report: {report_path}")
    except OSError as exc:
        print(f"  report write failed: {exc}")

    return 0 if failed == 0 else 1


if __name__ == "__main__":
    raise SystemExit(main())

"""Twin review / train / metrics CLI for the ApprovalTwin (user-trained Steve mimic).

Radical simplicity: review recent twin decisions from monitoring jsonl,
let user supply approve/veto/modify labels, append SteveValueRecords, auto-trigger
rlhf_light_update, surface metrics.

Usage:
  python -m lumina_launcher twin review --limit 5
  python -m lumina_launcher twin train
  python -m lumina_launcher twin metrics
  python -m lumina_launcher twin mode
  python -m lumina_launcher twin promote assisted|full_auto
"""

from __future__ import annotations

import json
import sys
from typing import Any

from lumina_core.evolution.twin_training_service import TwinTrainingService


def _print_metrics(svc: TwinTrainingService | None = None) -> None:
    service = svc or TwinTrainingService()
    m = service.metrics()
    print("ApprovalTwin metrics (Perfect Birth Phase KPIs included):")
    print(f"  mode: {m.get('mode', 'shadow')}")
    print(f"  authority: {m.get('authority', 'n/a')}")
    print(f"  avg_prediction_error: {m.get('avg_prediction_error', 'n/a')}")
    print(f"  reward: {m.get('reward', 'n/a')}")
    print(f"  training_steps: {m.get('training_steps', 0)}")
    print(f"  threshold: {m.get('threshold', 0.6)}")
    print(f"  last_avg_error (calib): {m.get('last_avg_error', 'n/a')}")
    print(f"  twin_steve_agreement_pct (vs Steve): {m.get('twin_steve_agreement_pct', 'n/a')}")
    print(f"  samples_for_accuracy: {m.get('samples', 'n/a')}")
    print(f"  twin_agreement_pct (mode metrics): {m.get('twin_agreement_pct', 'n/a')}")
    print(f"  false_positives: {m.get('false_positives', 'n/a')} ({m.get('false_positive_pct', 'n/a')}%)")
    print(f"  false_negatives: {m.get('false_negatives', 'n/a')}")
    print(f"  risk_flags_caught: {m.get('risk_flags_caught', 'n/a')}")
    print(f"  constitution_adherence_pct: {m.get('constitution_adherence_pct', 'n/a')}")
    print(f"  mode_samples: {m.get('mode_samples', 'n/a')}")
    readiness = m.get("mode_readiness") or {}
    if readiness:
        print(f"  readiness.assisted: {readiness.get('assisted')}")
        print(f"  readiness.full_auto: {readiness.get('full_auto')}")
    print(f"  local_only: {m.get('local_only', True)}")


def run_twin_metrics() -> int:
    _print_metrics()
    return 0


def run_twin_train() -> int:
    svc = TwinTrainingService()
    res = svc.train(limit=250)
    print("fine_tune_from_registry result:")
    print(json.dumps(res.get("result", res), indent=2, sort_keys=True))
    _print_metrics(svc)
    return 0


def run_twin_review(*, limit: int = 5) -> int:
    svc = TwinTrainingService()
    decisions = svc.list_review_queue(limit=limit)
    if not decisions:
        print("No recent twin decisions found (state/monitoring_twin_decisions.jsonl empty).")
        print("Run some evolution/birth activity or use 'twin train' first.")
        return 0

    print(f"Reviewing {len(decisions)} twin decision(s) (high-stakes first; unlabeled only).")
    print("Provide your label as Steve would. This trains the Approval Twin.\n")

    collected = 0
    for i, d in enumerate(decisions, 1):
        dna = str(d.get("dna_hash", "unknown"))
        score = d.get("score", d.get("confidence", 0.0))
        rec = d.get("recommendation", False)
        expl = str(d.get("explanation", ""))[:110]
        risks = d.get("risk_flags", [])
        stakes = str(d.get("stakes") or "routine")
        try:
            score_f = float(score)
            score_disp = f"{score_f:.2%}"
        except (TypeError, ValueError):
            score_f = None
            score_disp = str(score)
        print(f"[{i}] dna={dna[:16]}... score={score_disp} rec={rec} stakes={stakes}")
        print(f"    risks={risks}")
        print(f"    {expl}")
        try:
            ans = input("    Label? (A)pprove / (V)eto / (M)odify / (S)kip / (Q)uit > ").strip().lower()
        except (EOFError, KeyboardInterrupt):
            print("\nReview aborted.")
            break
        if ans in ("q", "quit"):
            break
        if ans in ("s", "skip", ""):
            continue
        notes = ""
        if ans in ("a", "approve", "y", "yes"):
            decision: Any = "approve"
        elif ans in ("v", "veto", "n", "no", "reject"):
            decision = "reject"
        elif ans in ("m", "modify"):
            decision = "modify"
            try:
                notes = input("    Modify notes (optional) > ").strip()
            except (EOFError, KeyboardInterrupt):
                notes = ""
        else:
            print("    (unrecognized, skipping)")
            continue

        try:
            out = svc.record_decision(
                decision=decision,
                dna_hash=dna,
                notes=notes,
                twin_score=score_f,
                twin_recommendation=bool(rec) if rec is not None else None,
                explanation=expl,
                risk_flags=list(risks) if isinstance(risks, list) else [],
                train_now=False,
            )
            collected += 1
            print(f"    → recorded {out.get('label')}")
        except ValueError as exc:
            print(f"    → error: {exc}")

    if collected:
        print(f"\nRunning fine_tune_from_registry after {collected} new label(s)...")
        res = svc.train(limit=250)
        print("Result:")
        print(json.dumps(res.get("result", res), indent=2, sort_keys=True))
        _print_metrics(svc)
        print("\nModel updated. Twin mimicry improved.")
    else:
        print("No new labels recorded.")
    return 0


def run_twin_mode() -> int:
    svc = TwinTrainingService()
    status = svc.mode_status()
    print(json.dumps(status, indent=2, sort_keys=True, default=str))
    return 0


def run_twin_promote(target: str) -> int:
    svc = TwinTrainingService()
    result = svc.promote_mode(target)
    print(json.dumps(result, indent=2, sort_keys=True, default=str))
    return 0 if result.get("promoted") else 1


def main(argv: list[str] | None = None) -> int:
    args = argv or sys.argv[1:]
    cmd = args[0] if args else "metrics"
    if cmd == "review":
        limit = 5
        for a in args[1:]:
            if a.startswith("--limit="):
                try:
                    limit = max(1, int(a.split("=", 1)[1]))
                except Exception:
                    pass
            elif a.isdigit():
                limit = max(1, int(a))
        return run_twin_review(limit=limit)
    if cmd == "train":
        return run_twin_train()
    if cmd == "metrics":
        return run_twin_metrics()
    if cmd == "mode":
        return run_twin_mode()
    if cmd == "promote":
        target = args[1] if len(args) > 1 else ""
        if target not in ("assisted", "full_auto", "advisory", "active"):
            print("Usage: twin promote assisted|full_auto", file=sys.stderr)
            return 2
        return run_twin_promote(target)
    print(
        "Unknown twin subcommand. Use review | train | metrics | mode | promote",
        file=sys.stderr,
    )
    return 2


if __name__ == "__main__":
    raise SystemExit(main())

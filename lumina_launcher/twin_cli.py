"""Twin review / train / metrics CLI for the ApprovalTwin (user-trained Steve mimic).

Radical simplicity: review recent twin decisions from monitoring jsonl,
let user supply approve/veto labels, append SteveValueRecords, auto-trigger
rlhf_light_update, surface metrics.

Usage:
  python -m lumina_launcher twin review --limit 5
  python -m lumina_launcher twin train
  python -m lumina_launcher twin metrics
"""

from __future__ import annotations

import json
import sys
from pathlib import Path
from typing import Any

from lumina_core.evolution.approval_twin_agent import ApprovalTwinAgent
from lumina_core.evolution.steve_values_registry import SteveValueRecord, SteveValuesRegistry


STATE_DIR = Path("state")
TWIN_DECISIONS = STATE_DIR / "monitoring_twin_decisions.jsonl"
TWIN_TRAINING = STATE_DIR / "monitoring_twin_training.jsonl"
MODEL_PATH = STATE_DIR / "approval_twin_model.json"


def _tail_jsonl(path: Path, limit: int = 5) -> list[dict[str, Any]]:
    if not path.exists():
        return []
    try:
        lines = path.read_text(encoding="utf-8").strip().splitlines()
        items: list[dict[str, Any]] = []
        for line in lines[-max(1, int(limit)) :]:
            line = line.strip()
            if line:
                try:
                    items.append(json.loads(line))
                except Exception:
                    pass
        return items
    except Exception:
        return []


def _print_metrics() -> None:
    latest = {}
    items = _tail_jsonl(TWIN_TRAINING, limit=1)
    if items:
        latest = items[-1]
    model = {}
    if MODEL_PATH.exists():
        try:
            model = json.loads(MODEL_PATH.read_text(encoding="utf-8"))
        except Exception:
            model = {}
    print("ApprovalTwin metrics (Perfect Birth Phase KPIs included):")
    print(f"  avg_prediction_error: {latest.get('avg_prediction_error', 'n/a')}")
    print(f"  reward: {latest.get('reward', 'n/a')}")
    print(f"  training_steps: {latest.get('training_steps', model.get('training_steps', 0))}")
    print(f"  threshold: {model.get('threshold', 0.6)}")
    print(f"  last_avg_error (calib): {model.get('last_avg_error', 'n/a')}")
    # New measurable success metrics
    print(f"  twin_steve_agreement_pct (vs Steve): {latest.get('twin_steve_agreement_pct', latest.get('agreement_pct', 'n/a'))}")
    print(f"  samples_for_accuracy: {latest.get('samples', 'n/a')}")


def run_twin_metrics() -> int:
    _print_metrics()
    return 0


def run_twin_train() -> int:
    reg = SteveValuesRegistry()
    twin = ApprovalTwinAgent(registry=reg, model_path=MODEL_PATH)
    res = twin.fine_tune_from_registry(limit=250)
    print("fine_tune_from_registry result:")
    print(json.dumps(res, indent=2, sort_keys=True))
    _print_metrics()
    return 0


def run_twin_review(*, limit: int = 5) -> int:
    decisions = _tail_jsonl(TWIN_DECISIONS, limit=limit)
    if not decisions:
        print("No recent twin decisions found (state/monitoring_twin_decisions.jsonl empty).")
        print("Run some evolution/birth activity or use 'twin train' first.")
        return 0

    print(f"Reviewing last {len(decisions)} twin decision(s) (newest first).")
    print("Provide your label as Steve would. This trains the Approval Twin.\n")

    reg = SteveValuesRegistry()
    twin = ApprovalTwinAgent(registry=reg, model_path=MODEL_PATH)
    collected: list[SteveValueRecord] = []

    for i, d in enumerate(reversed(decisions), 1):  # show newest first but process order doesn't matter
        dna = str(d.get("dna_hash", "unknown"))[:16]
        score = d.get("score", d.get("confidence", 0.0))
        rec = d.get("recommendation", False)
        expl = str(d.get("explanation", ""))[:110]
        risks = d.get("risk_flags", [])
        print(f"[{i}] dna={dna}... score={float(score):.2%} rec={rec}")
        print(f"    risks={risks}")
        print(f"    {expl}")
        try:
            ans = input("    Label? (A)pprove / (V)eto / (S)kip / (Q)uit > ").strip().lower()
        except (EOFError, KeyboardInterrupt):
            print("\nReview aborted.")
            break
        if ans in ("q", "quit"):
            break
        if ans in ("s", "skip", ""):
            continue
        if ans in ("a", "approve", "y", "yes"):
            label = "APPROVE"
        elif ans in ("v", "veto", "n", "no"):
            label = "VETO"
        else:
            print("    (unrecognized, skipping)")
            continue

        vraag = f"Twin decision review: dna={dna} score={float(score):.2%} rec={rec} expl={expl}"
        rec_obj = SteveValueRecord.create(
            vraag=vraag,
            steve_antwoord=label,
            context_dna_hash=str(d.get("dna_hash", "review")),
            confidence_score=0.85 if label == "APPROVE" else 0.25,
        )
        reg.append(rec_obj)
        collected.append(rec_obj)
        print(f"    → recorded {label}")

    if collected:
        print(f"\nRunning rlhf_light_update on {len(collected)} new label(s)...")
        res = twin.rlhf_light_update(records=collected)
        print("Result:")
        print(json.dumps(res, indent=2, sort_keys=True))
        _print_metrics()
        print("\nModel updated. Twin mimicry improved.")
    else:
        print("No new labels recorded.")
    return 0


def main(argv: list[str] | None = None) -> int:
    args = (argv or sys.argv[1:])
    # simple sub dispatch (called from launcher dispatch)
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
    print("Unknown twin subcommand. Use review | train | metrics", file=sys.stderr)
    return 2


if __name__ == "__main__":
    raise SystemExit(main())
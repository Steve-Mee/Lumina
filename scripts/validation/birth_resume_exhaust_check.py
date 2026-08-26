#!/usr/bin/env python3
"""Pre-resume check: certified plateau exhaust + certificate readiness (read-only).

Usage:
  python scripts/validation/birth_resume_exhaust_check.py
  python scripts/validation/birth_resume_exhaust_check.py --workspace C:\\ninjatraderai_bot

Does not mutate state. Exit 0 always when diagnostics complete; prints JSON summary.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--workspace",
        type=Path,
        default=Path.cwd(),
        help="Repo root (default: cwd)",
    )
    args = parser.parse_args()
    root = args.workspace.resolve()
    sys.path.insert(0, str(root))

    from lumina_core.birth.config import load_birth_v2_config
    from lumina_core.birth.maturity_readiness import (
        certificate_path_ready,
        certificate_readiness_blockers,
        maturity_artifact_presence,
    )
    from lumina_core.birth.plateau_escalator import (
        PlateauState,
        evolution_ladder_exhausted,
        should_brake_recovery_no_lift,
        should_terminal_plateau_stall,
    )
    from lumina_core.birth.starship_swarm_gates import effective_plateau_max_evolution_steps

    progress_path = root / "state" / "lumina_birth_progress.json"
    ckpt_path = root / "state" / "lumina_birth_checkpoint.json"
    progress = {}
    if progress_path.is_file():
        progress = json.loads(progress_path.read_text(encoding="utf-8"))
    ckpt = {}
    if ckpt_path.is_file():
        ckpt = json.loads(ckpt_path.read_text(encoding="utf-8"))
    metrics = dict(ckpt.get("stage_metrics") or {})

    cfg = load_birth_v2_config(root).curriculum
    certified = str(progress.get("training_mode") or ckpt.get("training_mode") or "certified").lower() != "provisional"
    max_steps = effective_plateau_max_evolution_steps(cfg, certified=certified)

    state = PlateauState.from_metrics(metrics) if metrics else PlateauState()
    # Prefer progress top-level when metrics thin after pause
    if int(getattr(state, "evolution_step", 0) or 0) <= 0:
        state.evolution_step = int(progress.get("evolution_step", 0) or 0)
    if not state.active and (
        progress.get("plateau_active") is True
        or str(progress.get("evolution_phase") or "").startswith("step_")
        or str(progress.get("evolution_phase") or "") == "exhausted"
    ):
        state.active = True

    stage_trades = int(
        metrics.get("stage_trades")
        or progress.get("stage_trades")
        or progress.get("trades_this_stage")
        or 0
    )
    stage_wins = int(metrics.get("stage_wins") or progress.get("stage_wins") or 0)
    required = int(
        metrics.get("stage_pass_gate_trades")
        or progress.get("stage_pass_gate_trades")
        or progress.get("required_trades")
        or 300
    )
    budget_rem = int(progress.get("trade_budget_remaining") or 0)
    if budget_rem <= 0:
        cap = int(progress.get("trade_budget_cap") or progress.get("target_trades") or 25000)
        cum = int(progress.get("cumulative_trades") or 0)
        budget_rem = max(0, cap - cum)

    exhausted = evolution_ladder_exhausted(state, max_steps=max_steps)
    no_lift = should_brake_recovery_no_lift(state, max_steps=max_steps)
    terminal = should_terminal_plateau_stall(
        state,
        stage_trades=stage_trades,
        required=required,
        cfg=cfg,
        meta_self_eval_phase=str(progress.get("meta_self_eval_phase") or ""),
        remediation_exhausted=True,
        trade_budget_remaining=budget_rem,
        max_steps=max_steps,
    )

    arts = maturity_artifact_presence(root)
    stages_count = len(progress.get("stages_passed") or ckpt.get("stages_passed") or [])
    if stages_count <= 0:
        stages_count = int(progress.get("curriculum_index") or 0)

    blockers = certificate_readiness_blockers(
        stages_passed_count=stages_count,
        plateau_active=bool(state.active),
        expectancy_stall=bool(progress.get("expectancy_stall_detected")),
        needs_attention=bool(progress.get("needs_attention")),
        certificate_present=bool(arts.get("certificate_present")),
    )

    from lumina_core.maturity.birth_exit import collect_birth_exit_proofs, is_birth_exit_sufficient

    proofs, exit_detail = collect_birth_exit_proofs(root)
    report = {
        "workspace": str(root),
        "phase": progress.get("phase"),
        "message": progress.get("message"),
        "user_initiated_stop": progress.get("user_initiated_stop"),
        "curriculum_stage": progress.get("curriculum_stage") or ckpt.get("curriculum_stage"),
        "stage_trades": stage_trades,
        "stage_wins": stage_wins,
        "required": required,
        "plateau_active": bool(state.active),
        "evolution_step": int(state.evolution_step),
        "evolution_history_len": len(state.evolution_history or []),
        "best_winrate": float(state.best_winrate),
        "best_winrate_at_cycle_start": float(state.best_winrate_at_cycle_start),
        "certified": certified,
        "effective_max_steps": max_steps,
        "ladder_exhausted": exhausted,
        "no_lift_brake": no_lift,
        "terminal_stall_recommended": terminal,
        "on_resume_expect": (
            "terminal_stall_or_remediation"
            if terminal or (exhausted and no_lift)
            else "continue_training"
        ),
        "maturity": {
            **arts,
            "curriculum_stages_passed_count": stages_count,
            "certificate_path_ready": certificate_path_ready(
                stages_passed_count=stages_count,
                plateau_active=bool(state.active),
                needs_attention=bool(progress.get("needs_attention")),
            ),
            "certificate_readiness_blockers": blockers,
            "birth_exit_ok": is_birth_exit_sufficient(root),
            "birth_exit_proofs": proofs,
            "birth_exit_detail": exit_detail,
        },
        "expectancy_proxy": progress.get("expectancy_proxy"),
        "expectancy_stall_detected": progress.get("expectancy_stall_detected"),
    }
    print(json.dumps(report, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

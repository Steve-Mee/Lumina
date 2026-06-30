#!/usr/bin/env python3
"""Force a plateau evolution step on the current birth checkpoint (operator unstick)."""

from __future__ import annotations

import argparse
import json
import shutil
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from lumina_core.birth.checkpoint import read_checkpoint_payload, write_checkpoint_payload
from lumina_core.birth.config import load_birth_v2_config
from lumina_core.birth.plateau_escalator import (
    EvolutionAction,
    PlateauState,
    action_for_step,
    begin_evolution_step,
    is_valid_best_policy_snapshot,
    sanitize_plateau_best_snapshot,
)


def _default_policy_path(workspace: Path) -> Path:
    return workspace / "lumina_agents" / "ppo" / "lumina_ppo_policy.zip"


def _apply_rollback(workspace: Path, state: PlateauState, *, cfg) -> str:
    if not is_valid_best_policy_snapshot(state, cfg=cfg):
        return "rollback skipped — no valid best policy snapshot (min trades)"
    rollback_path = Path(str(state.best_policy_path))
    if not rollback_path.is_file():
        return f"rollback skipped — missing file {rollback_path}"
    target = _default_policy_path(workspace)
    target.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(rollback_path, target)
    return f"rollback to {state.best_winrate:.1%} winrate ({state.best_winrate_at_trade} trades)"


def _ensure_best_snapshot_from_current(
    workspace: Path,
    state: PlateauState,
    *,
    cfg,
    stage_trades: int,
    stage_wins: int,
    policy_path: str,
) -> None:
    """When metrics hold a stale spike, anchor best snapshot to the live policy."""
    if is_valid_best_policy_snapshot(state, cfg=cfg):
        return
    min_trades = max(1, int(getattr(cfg, "plateau_best_policy_min_trades", 200)))
    if stage_trades < min_trades:
        return
    current = Path(policy_path) if policy_path else _default_policy_path(workspace)
    if not current.is_file():
        return
    best_path = workspace / "lumina_agents" / "ppo" / "birth_best_stage1_trend.zip"
    best_path.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(current, best_path)
    state.best_policy_path = str(best_path)
    state.best_winrate = float(stage_wins) / float(max(1, stage_trades))
    state.best_winrate_at_trade = int(stage_trades)


def main() -> None:
    parser = argparse.ArgumentParser(description="Force plateau evolution step on checkpoint")
    parser.add_argument("--workspace", type=Path, default=ROOT)
    parser.add_argument("--step", type=int, default=2, help="Target evolution step (default 2=rollback)")
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()

    birth_cfg = load_birth_v2_config(args.workspace)
    cur_cfg = birth_cfg.curriculum
    payload = read_checkpoint_payload(args.workspace) or {}
    metrics = dict(payload.get("stage_metrics") or {})
    state = PlateauState.from_metrics(metrics)
    if not state.active:
        print("Plateau not active — enabling plateau state on checkpoint.")
        state.active = True

    stage_trades = int(metrics.get("stage_trades", 0) or 0)
    stage_wins = int(metrics.get("stage_wins", 0) or 0)
    target_step = max(1, int(args.step))

    sanitize_plateau_best_snapshot(
        state,
        cfg=cur_cfg,
        stage_trades=stage_trades,
        stage_wins=stage_wins,
    )
    print(
        f"Best snapshot after sanitize: {state.best_winrate:.1%} "
        f"@ {state.best_winrate_at_trade} trades path={state.best_policy_path or 'none'}"
    )
    _ensure_best_snapshot_from_current(
        args.workspace,
        state,
        cfg=cur_cfg,
        stage_trades=stage_trades,
        stage_wins=stage_wins,
        policy_path=str(payload.get("policy_path", "") or ""),
    )

    last_action: EvolutionAction | None = None
    last_detail = ""
    while state.evolution_step < target_step:
        last_action = begin_evolution_step(
            state,
            stage_trades=stage_trades,
            stage_wins=stage_wins,
        )
        print(f"Advanced to step {state.evolution_step}: {last_action.value}")
        if last_action == EvolutionAction.TERMINAL:
            break
        if last_action == EvolutionAction.POLICY_ROLLBACK:
            last_detail = _apply_rollback(args.workspace, state, cfg=cur_cfg)
            print(last_detail)
            payload["policy_path"] = str(_default_policy_path(args.workspace))

    next_action = action_for_step(state.evolution_step + 1) if state.evolution_step > 0 else action_for_step(1)
    print(f"Next action when engine resumes: {next_action.value}")

    if args.dry_run:
        print("Dry run — checkpoint not written.")
        return

    metrics.update(state.to_metrics())
    payload["stage_metrics"] = metrics
    payload["phase"] = "plateau_evolution"
    if last_detail.startswith("rollback to"):
        payload["policy_path"] = str(_default_policy_path(args.workspace))
    write_checkpoint_payload(args.workspace, payload)
    print(
        json.dumps(
            {
                "evolution_step": state.evolution_step,
                "last_action": last_action.value if last_action else None,
                "detail": last_detail,
                "policy_path": payload.get("policy_path"),
            },
            indent=2,
        )
    )


if __name__ == "__main__":
    main()

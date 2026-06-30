"""Forensic report for birth curriculum stage passes and stage-2 health."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

import yaml

from lumina_core.birth.config import load_birth_v2_config, resolve_trade_budget_cap
from lumina_core.birth.curriculum import CurriculumStage, stage_pass_trades, stage_trade_target
from lumina_core.birth.plateau_escalator import PlateauState, build_plateau_audit, remediation_is_exhausted
from lumina_core.birth.stage_pass_receipt import build_stage_pass_audit, parse_stage_pass_receipts


def _load_json(path: Path) -> dict[str, Any]:
    if not path.is_file():
        return {}
    return json.loads(path.read_text(encoding="utf-8"))


def _log_context(log_path: Path, needle: str, *, before: int = 20, after: int = 5) -> list[str]:
    if not log_path.is_file():
        return []
    lines = log_path.read_text(encoding="utf-8", errors="replace").splitlines()
    hits: list[str] = []
    for i, line in enumerate(lines):
        if needle in line and "birth.stage.passed" in line:
            hits.extend(lines[max(0, i - before) : i + after + 1])
            hits.append("---")
    return hits


def _infer_stage1_from_cumulative(progress: dict[str, Any]) -> dict[str, Any]:
    cumulative = int(progress.get("cumulative_trades", 0) or 0)
    stage2 = int(progress.get("stage_trades", 0) or 0)
    stage1_trades_est = max(0, cumulative - stage2)
    _wins = int(progress.get("stage_wins", 0) or 0)
    return {
        "estimated_stage1_trades": stage1_trades_est,
        "stage2_trades": stage2,
        "cumulative_trades": cumulative,
        "stage_wins": _wins,
        "note": "stage1 trades estimated as cumulative - stage2 when only stage1 in stages_passed",
    }


def _load_yaml_config(workspace: Path) -> dict[str, Any]:
    path = workspace / "config.yaml"
    if not path.is_file():
        return {}
    try:
        loaded = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
        return loaded if isinstance(loaded, dict) else {}
    except Exception:
        return {}


def _budget_forensics(workspace: Path, progress: dict[str, Any], cfg: Any) -> dict[str, Any]:
    raw = _load_yaml_config(workspace)
    first_boot = raw.get("first_boot") if isinstance(raw.get("first_boot"), dict) else {}
    genesis_trades = int(first_boot.get("training_trades", 0) or 0)
    engine_cap = int(cfg.trade_budget_cap)
    _, cap_source = resolve_trade_budget_cap(raw)
    cumulative = int(progress.get("cumulative_trades", 0) or progress.get("trades_done", 0) or 0)
    progress_target = int(progress.get("target_trades", 0) or 0)
    budget_remaining = max(0, engine_cap - cumulative)

    mismatch = False
    details: list[str] = []
    if genesis_trades > 0 and genesis_trades != engine_cap:
        mismatch = True
        details.append(
            f"first_boot.training_trades={genesis_trades} != birth_v2.trade_budget_cap={engine_cap}"
        )
    if progress_target > 0 and progress_target != engine_cap:
        mismatch = True
        details.append(f"progress.target_trades={progress_target} != engine_cap={engine_cap}")
    if cumulative >= engine_cap and str(progress.get("phase", "")).lower() == "stage_stalled":
        mismatch = True
        details.append(
            f"cumulative_trades={cumulative} >= cap={engine_cap} with stage_stalled (check recovery)"
        )

    return {
        "cumulative_trades": cumulative,
        "progress_target_trades": progress_target,
        "birth_v2_trade_budget_cap": engine_cap,
        "first_boot_training_trades": genesis_trades,
        "trade_budget_source": cap_source,
        "trade_budget_remaining": budget_remaining,
        "terminal_stall_reason": progress.get("terminal_stall_reason"),
        "budget_mismatch": mismatch,
        "budget_mismatch_detail": "; ".join(details) if details else None,
    }


def build_report(workspace: Path, *, log_needles: list[str] | None = None) -> dict[str, Any]:
    cfg = load_birth_v2_config(workspace)
    progress = _load_json(workspace / "state" / "lumina_birth_progress.json")
    checkpoint = _load_json(workspace / "state" / "lumina_birth_checkpoint.json")
    log_path = workspace / "logs" / "lumina_full_log.csv"

    needles = log_needles or ["2026-06-27 18:28:10", "2026-06-27 19:05:17"]
    log_sections = {needle: _log_context(log_path, needle) for needle in needles}

    gates = {}
    for stage in (
        CurriculumStage.STAGE1_TREND,
        CurriculumStage.STAGE2_RANGE,
        CurriculumStage.STAGE3_MIXED,
    ):
        budget = stage_trade_target(stage, cfg.curriculum)
        gate = stage_pass_trades(stage, cfg.curriculum)
        gates[stage.value] = {"training_budget": budget, "pass_gate": gate}

    stage = str(progress.get("curriculum_stage", "") or "")
    flat_ratio = float(progress.get("stage_range_flat_ratio", 0.0) or 0.0)
    ckpt_stages = list(checkpoint.get("stages_passed") or [])
    progress_stages = list(progress.get("stages_passed") or [])
    stages_passed = progress_stages or ckpt_stages
    receipts = parse_stage_pass_receipts(checkpoint.get("stage_pass_receipts"))
    training_mode = str(checkpoint.get("training_mode") or progress.get("training_mode") or "certified")
    stage_pass_audit = build_stage_pass_audit(
        stages_passed=stages_passed,
        stage_pass_receipts=receipts,
        progress=progress,
        cfg=cfg.curriculum,
        training_mode=training_mode,
    )
    stage_metrics = checkpoint.get("stage_metrics")
    metrics_dict = stage_metrics if isinstance(stage_metrics, dict) else {}
    plateau_state = PlateauState.from_metrics(metrics_dict)
    current_stage = str(checkpoint.get("curriculum_stage") or stage or "")
    pass_gate = gates.get(current_stage, {}).get("pass_gate", 0)
    if not pass_gate and current_stage:
        try:
            pass_gate = stage_pass_trades(CurriculumStage(current_stage), cfg.curriculum)
        except ValueError:
            pass_gate = 0
    budget_forensics = _budget_forensics(workspace, progress, cfg)
    plateau_audit = build_plateau_audit(
        plateau_state,
        stage_trades=int(progress.get("stage_trades", metrics_dict.get("stage_trades", 0)) or 0),
        required=int(pass_gate or 0),
        cfg=cfg.curriculum,
        progress=progress,
        remediation_exhausted=remediation_is_exhausted(
            remediation_active=bool(metrics_dict.get("stall_remediation_active")),
            remediation_step=int(metrics_dict.get("stall_remediation_step", 0) or 0),
            remediation_cycle=int(metrics_dict.get("stall_remediation_cycle", 0) or 0),
            cfg=cfg.curriculum,
        ),
        trade_budget_remaining=int(budget_forensics.get("trade_budget_remaining", 0) or 0),
    )
    return {
        "training_mode": training_mode,
        "gen0_provisional": progress.get("gen0_provisional"),
        "stages_passed": stages_passed,
        "stage_pass_audit": stage_pass_audit,
        "plateau_audit": plateau_audit,
        "curriculum_stage": stage,
        "pass_gates": gates,
        "stage1_estimate": _infer_stage1_from_cumulative(progress),
        "intra_stage1_easy": {
            "easy_trades": checkpoint.get("stage_metrics", {}).get("intra_stage1_easy_trades"),
            "easy_wins": checkpoint.get("stage_metrics", {}).get("intra_stage1_easy_wins"),
        },
        "stage2_health": {
            "stage_trades": progress.get("stage_trades"),
            "pass_gate": gates.get("stage2_range", {}).get("pass_gate"),
            "position_flat_ratio": round(flat_ratio, 4),
            "pass_reason": progress.get("pass_reason"),
            "strong_recovery_mode": progress.get("strong_recovery_mode"),
            "velocity_stall_attempts": progress.get("velocity_stall_attempts"),
            "meta_primary_strategy": progress.get("meta_primary_strategy"),
            "meta_review_trigger": progress.get("meta_review_trigger"),
            "last_adaptation": progress.get("last_adaptation"),
        },
        "budget_forensics": budget_forensics,
        "log_context": log_sections,
    }


def main() -> None:
    parser = argparse.ArgumentParser(description="Birth stage forensics report")
    parser.add_argument("--workspace", type=Path, default=Path.cwd())
    parser.add_argument("--json", action="store_true", help="Print JSON only")
    args = parser.parse_args()
    report = build_report(args.workspace)
    if args.json:
        print(json.dumps(report, indent=2))
        return
    print("=== Birth Stage Forensics ===")
    print(f"Mode: {report.get('training_mode')}  provisional: {report.get('gen0_provisional')}")
    print(f"Stages passed: {report.get('stages_passed')}")
    print(f"Current stage: {report.get('curriculum_stage')}")
    audit = report.get("stage_pass_audit") or {}
    print("\nStage pass audit:")
    print(json.dumps(audit, indent=2))
    print("\nPlateau audit:")
    print(json.dumps(report.get("plateau_audit"), indent=2))
    if audit.get("integrity_mismatch"):
        print(f"\n*** INTEGRITY MISMATCH: {audit.get('integrity_mismatch_detail')} ***")
    print("\nPass gates vs training budgets:")
    for name, g in report.get("pass_gates", {}).items():
        print(f"  {name}: pass_gate={g['pass_gate']}  training_budget={g['training_budget']}")
    print("\nStage 1 estimate:", report.get("stage1_estimate"))
    print("\nStage 2 health:", json.dumps(report.get("stage2_health"), indent=2))
    budget = report.get("budget_forensics") or {}
    print("\nBudget forensics:")
    print(json.dumps(budget, indent=2))
    if budget.get("budget_mismatch"):
        print(f"\n*** BUDGET MISMATCH: {budget.get('budget_mismatch_detail')} ***")
    for needle, lines in report.get("log_context", {}).items():
        print(f"\n--- Log context: {needle} ({len(lines)} lines) ---")


if __name__ == "__main__":
    main()

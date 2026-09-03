"""Evaluate-only Awakening grind runner. Zero PPO steps. Envelope stays on."""

from __future__ import annotations

import json
from pathlib import Path
from types import SimpleNamespace
from typing import Any, Callable

from lumina_core.birth.awakening_grind import (
    ADR0026_MIN_TRADES,
    EvaluateOnlyPolicy,
    GRIND_A_NAME,
    GRIND_B_NAME,
    GrindLegMetrics,
    TRAIN,
    grind_table_from_rows,
)
from lumina_core.birth.birth_exit_policy_export import (
    EXPORT_SITE,
    file_sha256,
    is_gitignored_ppo_zip,
    load_frozen_policy,
    resolve_frozen_policy_path,
)
from lumina_core.birth.birth_trade_geometry import (
    calibrate_birth_stops,
    first_touch_target_hit_rate,
)
from lumina_core.birth.config_curriculum import BirthCurriculumConfig
from lumina_core.birth.curriculum_types import CurriculumStage
from lumina_core.birth.foundation_occupancy_envelope import (
    foundation_envelope_controller_spec,
    foundation_occupancy_envelope_enabled,
)
from lumina_core.birth.s5_close_ledger_archive import (
    append_archive_rows,
    archive_line_count,
    enrich_archive_row,
    resolve_archive_path,
)
from lumina_core.birth.s5_close_ledger_trace import close_ledger_row
from lumina_core.birth.s5_occupancy_continuity import (
    S5_SEED_SIGNALS,
    s4_occupancy_from_receipts,
    s4_occupancy_in_s5_exam_band,
)
from lumina_core.birth.sim_runner import run_policy_rollout
from lumina_core.birth.stage_pass_receipt_types import StagePassReceipt
from lumina_core.logging_utils import get_logger

logger = get_logger("lumina.birth.awakening_grind_run")

LEG_A_SEED = 20260902
LEG_B_SEED = 20260903
EXPECTED_TICKS_SHA16 = "7e86c2bb1c71d514"
EXPECTED_BARS_SHA16 = "2466d3f41d60657b"
S5_STAGE = CurriculumStage.STAGE5_PROBE_HANDOFF
START_CHOICE = "full_holdout_replay_frozen"
START_BAR_INDEX = 0


def grind_ledger_path(workspace_root: Path | str, *, leg: str) -> Path:
    name = GRIND_A_NAME if str(leg).upper() == "A" else GRIND_B_NAME
    root = Path(workspace_root)
    if root.name == "workspace" and root.parent.name == "birth_cloud_run":
        return root.parent / "artifacts" / name
    return root / "reports" / "birth_cloud_run" / "artifacts" / name


def write_grind_closes(
    path: Path,
    trajectories: list[dict[str, Any]],
    *,
    ledger_source: str = "awakening_grind",
) -> int:
    """New file per leg. Never the Birth s5 archive path."""
    if path.name == "s5_close_ledger.jsonl":
        raise RuntimeError("grind must not write the Birth s5 archive")
    rows: list[dict[str, Any]] = []
    for tr in trajectories:
        if not isinstance(tr, dict) or tr.get("pnl") is None:
            continue
        row = close_ledger_row(tr)
        rows.append(enrich_archive_row(row, stage=S5_STAGE.value, tr=tr, source=str(ledger_source)))
    if path.is_file():
        path.unlink()
    sha = path.with_suffix(".sha256")
    if sha.is_file():
        sha.unlink()
    return append_archive_rows(path, rows)


def _s4_receipts(reports_dir: Path) -> list[Any]:
    candidates = [
        reports_dir / "s4_receipt.json",
        reports_dir / "artifacts" / "s4_receipt.json",
    ]
    if reports_dir.name == "artifacts":
        candidates.insert(0, reports_dir / "s4_receipt.json")
    for path in candidates:
        if not path.is_file():
            continue
        raw = json.loads(path.read_text(encoding="utf-8"))
        rec = StagePassReceipt.from_dict(raw)
        if rec is not None:
            return [rec]
        return [SimpleNamespace(stage=str(raw.get("stage") or ""), occupancy=raw.get("occupancy"))]
    return []


def occupancy_seed_kwargs(reports_dir: Path) -> dict[str, Any]:
    occ = s4_occupancy_from_receipts(_s4_receipts(reports_dir))
    if not s4_occupancy_in_s5_exam_band(occ):
        return {
            "stage_range_flat_bars": 0,
            "stage_range_total_signals": 0,
            "occupancy_in_band_seen": False,
        }
    n = int(S5_SEED_SIGNALS)
    return {
        "stage_range_flat_bars": int(round(float(occ) * float(n))),
        "stage_range_total_signals": n,
        "occupancy_in_band_seen": True,
    }


def s5_envelope_kwargs(cfg: BirthCurriculumConfig, geometry: Any) -> dict[str, Any]:
    spec = foundation_envelope_controller_spec(S5_STAGE, cfg)
    return {
        "participation_envelope_enabled": foundation_occupancy_envelope_enabled(S5_STAGE, cfg),
        "range_patience_active": True,
        "participation_min_signals": int(getattr(cfg, spec.min_signals_attr, 50) or 50),
        "participation_min_dwell_bars": int(getattr(cfg, spec.min_dwell_attr, 8) or 8),
        "participation_band_lo": float(spec.band_lo),
        "participation_band_hi": float(spec.band_hi),
        "participation_hysteresis": float(spec.hysteresis),
        "participation_under_band_release_hysteresis": float(spec.release_hysteresis),
        "occupancy_control_window_bars": int(getattr(cfg, spec.window_attr, 500) or 500),
        "participation_stop_pct": float(geometry.stop_pct),
        "participation_target_pct": float(geometry.target_pct),
        "curriculum_regime": S5_STAGE.value,
        "soft_prior_stops": True,
        "trade_geometry": geometry,
        "exploration_steps": 0,
        "expectancy_gap": 0.0,
    }


def inconclusive_leg(*, frozen_path: str = "", reason: str = "frozen_weights_missing") -> GrindLegMetrics:
    _ = reason
    metrics = GrindLegMetrics(frozen_loaded=False, frozen_path=frozen_path, train=TRAIN)
    metrics.classification = "INCONCLUSIVE"
    metrics.start_choice = START_CHOICE
    metrics.start_bar_index = START_BAR_INDEX
    return metrics


def run_evaluate_only(
    *,
    runtime: Any,
    holdout: list[dict[str, Any]],
    workspace_root: Path | str,
    reports_dir: Path,
    ledger_path: Path,
    policy: Any | None = None,
    policy_path: Path | str | None = None,
    rollout_fn: Callable[..., Any] | None = None,
    ledger_source: str = "awakening_grind",
    path_exit_k3_shadow: bool = False,
) -> GrindLegMetrics:
    """Single-pass holdout eval. No train, no 172-stop, no env loop farm.

    Bars exhaust via ``max_steps`` / ``rollout_step_budget`` = len(holdout).
    ``target_trades`` is ADR-0026 min (500) only as a *floor to keep going*,
    not a Birth pass. sim_runner stops at step budget when the tape ends.
    Default load path is Birth-exit π* via ``resolve_frozen_policy_path``.
    Awakening-select Gate 2 may pass an explicit child ``policy_path``.
    """
    if TRAIN:
        raise RuntimeError("awakening grind TRAIN must stay False")
    root = Path(workspace_root)
    if policy_path is not None:
        frozen_path = Path(policy_path)
    else:
        frozen_path = resolve_frozen_policy_path(root)
    if frozen_path is not None and is_gitignored_ppo_zip(frozen_path):
        logger.error("awakening.grind.refused_post_polish_ppo path=%s", frozen_path)
        return inconclusive_leg(frozen_path=str(frozen_path), reason="refused_post_polish_ppo")
    loaded = policy
    sha = ""
    if loaded is None:
        if frozen_path is None:
            logger.warning("awakening.grind.frozen_missing export_site=%s", EXPORT_SITE)
            return inconclusive_leg()
        loaded = load_frozen_policy(frozen_path)
        if loaded is None:
            return inconclusive_leg(frozen_path=str(frozen_path))
    if frozen_path is not None and frozen_path.is_file():
        sha = file_sha256(frozen_path)
    wrapped = EvaluateOnlyPolicy(loaded)
    geometry = calibrate_birth_stops(holdout)
    p_ft = first_touch_target_hit_rate(
        holdout, stop_pct=float(geometry.stop_pct), target_pct=float(geometry.target_pct)
    )
    cfg = BirthCurriculumConfig()
    n_bars = len(holdout)
    kwargs = s5_envelope_kwargs(cfg, geometry)
    kwargs.update(occupancy_seed_kwargs(reports_dir))
    fn = rollout_fn or run_policy_rollout
    from lumina_core.birth.awakening_path_exit_k3 import PATH_EXIT_K3_SHADOW

    token = PATH_EXIT_K3_SHADOW.set(bool(path_exit_k3_shadow))
    try:
        rollout = fn(
            runtime=runtime,
            data=list(holdout),
            policy=wrapped,
            target_trades=max(ADR0026_MIN_TRADES, n_bars),
            workspace_root=root,
            max_steps=n_bars,
            rollout_step_budget=n_bars,
            stall_probe_steps=max(n_bars, 1),
            **kwargs,
        )
    finally:
        PATH_EXIT_K3_SHADOW.reset(token)
    if wrapped.optimizer_steps != 0:
        raise RuntimeError("awakening grind recorded optimizer steps")
    trajectories = list(getattr(rollout, "trajectories", None) or [])
    write_grind_closes(ledger_path, trajectories, ledger_source=str(ledger_source))
    steps = int(getattr(rollout, "rollout_steps", 0) or 0)
    exhausted = steps >= max(0, n_bars - 1)
    rows: list[dict[str, Any]] = []
    if ledger_path.is_file():
        for line in ledger_path.read_text(encoding="utf-8").splitlines():
            if line.strip():
                rows.append(json.loads(line))
    metrics = grind_table_from_rows(
        rows,
        rollout=rollout,
        p_ft=float(p_ft),
        net_rr=float(getattr(geometry, "net_rr_after_cost", 0.0) or 0.0),
        holdout_exhausted=bool(exhausted),
        frozen_loaded=True,
        frozen_path=str(frozen_path or ""),
        frozen_sha256=sha,
    )
    metrics.start_bar_index = START_BAR_INDEX
    metrics.start_choice = START_CHOICE
    metrics.optimizer_steps = 0
    metrics.train = TRAIN
    logger.info(
        "awakening.grind.leg n=%s wr=%.3f sharpe=%.3f dd=%.3f mean=%.2f class=%s archive_s5=%s",
        metrics.n,
        metrics.wr,
        metrics.oos_sharpe,
        metrics.oos_dd_pct,
        metrics.mean_usd,
        metrics.classification,
        archive_line_count(resolve_archive_path(root)),
    )
    return metrics


__all__ = [
    "EXPECTED_BARS_SHA16",
    "EXPECTED_TICKS_SHA16",
    "LEG_A_SEED",
    "LEG_B_SEED",
    "START_BAR_INDEX",
    "START_CHOICE",
    "grind_ledger_path",
    "inconclusive_leg",
    "run_evaluate_only",
    "write_grind_closes",
]

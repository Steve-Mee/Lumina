"""Prefer-better incumbent. A worse child never replaces frozen π*."""
from __future__ import annotations

import json
import shutil
from pathlib import Path
from typing import Any

from lumina_core.birth.foundation_metrics import S3_OCCUPANCY_MAX, S3_OCCUPANCY_MIN

INCUMBENT_ZIP_NAME = "awakening_incumbent_pi_star.zip"
STUDENT_ZIP_NAME = "awakening_student_pi_star.zip"


def incumbent_zip(workspace_root: Path) -> Path:
    from lumina_core.maturity.phase_runners.awakening_shot import artifacts_dir

    return artifacts_dir(Path(workspace_root)) / INCUMBENT_ZIP_NAME


def student_zip(workspace_root: Path) -> Path:
    """Train continuation. The exam incumbent is a different file."""
    from lumina_core.maturity.phase_runners.awakening_shot import artifacts_dir

    return artifacts_dir(Path(workspace_root)) / STUDENT_ZIP_NAME


def occupancy_in_exam_band(occupancy: float | None) -> bool:
    if occupancy is None:
        return False
    return S3_OCCUPANCY_MIN - 1e-12 <= float(occupancy) <= S3_OCCUPANCY_MAX + 1e-12


def incumbent_from_shot(shot: dict[str, Any]) -> dict[str, Any]:
    return {
        "incumbent_n_b": int(shot.get("policy_trades") or shot.get("n_b") or 0),
        "incumbent_wr": shot.get("polish_oos_winrate", shot.get("wr")),
        "incumbent_mean_r": shot.get("mean_r"),
        "incumbent_sha": str(shot.get("child_sha256") or shot.get("incumbent_sha") or ""),
        "incumbent_weight_sha": str(shot.get("child_weight_sha") or ""),
        "incumbent_init_weight_sha": str(shot.get("init_weight_sha") or ""),
        "incumbent_occupancy": shot.get("occupancy"),
        "incumbent_occupancy_full_tape": shot.get("occupancy_full_tape", shot.get("occupancy")),
        "incumbent_edge": shot.get("edge"),
        "incumbent_sharpe": shot.get("oos_sharpe", shot.get("sharpe")),
        "incumbent_dd_pct": shot.get("oos_dd_pct", shot.get("dd_pct")),
        "incumbent_median_loss_r": shot.get("median_loss_r"),
        "incumbent_n_plant": int(shot.get("n_plant") or 0),
        "incumbent_occupancy_at_nb": shot.get("occupancy_at_nb"),
        "incumbent_paired_delta": shot.get("paired_delta"),
        "incumbent_paired_ci_low": shot.get("paired_ci_low"),
        "incumbent_parent_replay_present": bool(shot.get("parent_replay_present")),
        "incumbent_child_median_win_r": shot.get("child_median_win_r"),
        "incumbent_parent_median_win_r": shot.get("parent_median_win_r"),
    }


def progress_from_incumbent(incumbent: dict[str, Any]) -> dict[str, Any]:
    """HUD/law fields follow the kept organism, not a discarded shot."""
    from lumina_core.maturity.awakening.clock import classify_stable

    n_b = int(incumbent.get("incumbent_n_b") or 0)
    sharpe = _f(incumbent.get("incumbent_sharpe"))
    dd_pct = _f(incumbent.get("incumbent_dd_pct"))
    return {
        "n_b": n_b,
        "wr": incumbent.get("incumbent_wr"),
        "mean_r": incumbent.get("incumbent_mean_r"),
        "child_sha": str(incumbent.get("incumbent_sha") or ""),
        "child_weight_sha": str(incumbent.get("incumbent_weight_sha") or ""),
        "init_weight_sha": str(incumbent.get("incumbent_init_weight_sha") or ""),
        "occupancy": incumbent.get("incumbent_occupancy"),
        "occupancy_full_tape": incumbent.get(
            "incumbent_occupancy_full_tape", incumbent.get("incumbent_occupancy")
        ),
        "occupancy_at_nb": incumbent.get("incumbent_occupancy_at_nb"),
        "edge": incumbent.get("incumbent_edge"),
        "sharpe": sharpe,
        "dd_pct": dd_pct,
        "median_loss_r": incumbent.get("incumbent_median_loss_r"),
        "n_plant": int(incumbent.get("incumbent_n_plant") or 0),
        "stable_class": classify_stable(n_b=n_b, sharpe=sharpe, dd_pct=dd_pct),
        "paired_delta": _f(incumbent.get("incumbent_paired_delta")),
        "paired_ci_low": _f(incumbent.get("incumbent_paired_ci_low")),
        "parent_replay_present": bool(incumbent.get("incumbent_parent_replay_present")),
        "child_median_win_r": _f(incumbent.get("incumbent_child_median_win_r")),
        "parent_median_win_r": _f(incumbent.get("incumbent_parent_median_win_r")),
    }


def last_shot_card(shot: dict[str, Any]) -> dict[str, Any]:
    """Exam card of the attempt. Stays on the shot even when the incumbent is restored."""
    from lumina_core.maturity.awakening.clock import classify_stable

    n_b = int(shot.get("policy_trades") or shot.get("n_b") or 0)
    sharpe = _f(shot.get("oos_sharpe", shot.get("sharpe")))
    dd_pct = _f(shot.get("oos_dd_pct", shot.get("dd_pct")))
    return {
        "last_shot_n_b": n_b,
        "last_shot_wr": shot.get("polish_oos_winrate", shot.get("wr")),
        "last_shot_mean_r": shot.get("mean_r"),
        "last_shot_occupancy": shot.get("occupancy"),
        "last_shot_occupancy_at_nb": shot.get("occupancy_at_nb"),
        "last_shot_sharpe": sharpe,
        "last_shot_dd_pct": dd_pct,
        "last_shot_stable_class": classify_stable(n_b=n_b, sharpe=sharpe, dd_pct=dd_pct),
        "last_shot_sha": str(shot.get("child_sha256") or shot.get("last_shot_sha") or ""),
    }


def skill_regressed(child: dict[str, Any], incumbent: dict[str, Any]) -> bool:
    """WR and mean_r both worse. Same predicates the keep gate uses later.

    Occupancy is not part of this check. A child can miss the band and still
    have regressed skill; the student zip resets on that pair, not on the
    first keep-block string.
    """
    wr = _f(child.get("polish_oos_winrate", child.get("wr")))
    mean_r = _f(child.get("mean_r"))
    inc_wr = _f(incumbent.get("incumbent_wr"))
    inc_mean = _f(incumbent.get("incumbent_mean_r"))
    wr_worse = wr is not None and inc_wr is not None and float(wr) + 1e-12 < float(inc_wr)
    mean_worse = (
        mean_r is not None and inc_mean is not None and float(mean_r) + 1e-12 < float(inc_mean)
    )
    if wr_worse and mean_worse:
        return True
    if wr_worse and mean_r is None:
        return True
    if mean_worse and wr is None:
        return True
    return False


def _policy_exam_passed(
    card: dict[str, Any],
    *,
    incumbent: bool,
    birth_mean: float | None,
    birth_wr: float | None,
) -> bool:
    """Same ADR-0049 policy gates as the phase exit.

    Freeze, twin-watch, recovery, and regime are run-level and identical for
    both cards, so they are not what decides which policy is kept. Policy-only
    is the shot pipeline. A missing weight hash or a collapsed median win
    still fails this card.
    """
    from lumina_core.maturity.awakening.clock import classify_stable
    from lumina_core.maturity.awakening.law import AwakeningSnapshot, evaluate_awakening_pass

    if incumbent:
        n_b = int(card.get("incumbent_n_b") or 0)
        wr = _f(card.get("incumbent_wr"))
        mean_r = _f(card.get("incumbent_mean_r"))
        sharpe = _f(card.get("incumbent_sharpe"))
        dd_pct = _f(card.get("incumbent_dd_pct"))
        child_w = str(card.get("incumbent_weight_sha") or "")
        init_w = str(card.get("incumbent_init_weight_sha") or "")
        child_med = _f(card.get("incumbent_child_median_win_r"))
        parent_med = _f(card.get("incumbent_parent_median_win_r"))
        at_nb = _f(card.get("incumbent_occupancy_at_nb"))
        full = _f(card.get("incumbent_occupancy_full_tape"))
        if full is None:
            full = _f(card.get("incumbent_occupancy"))
        edge = _f(card.get("incumbent_edge"))
        loss = _f(card.get("incumbent_median_loss_r"))
        ci = _f(card.get("incumbent_paired_ci_low"))
        replay = bool(card.get("incumbent_parent_replay_present"))
        n_plant = int(card.get("incumbent_n_plant") or 0)
    else:
        n_b = int(card.get("policy_trades") or card.get("n_b") or 0)
        wr = _f(card.get("polish_oos_winrate", card.get("wr")))
        mean_r = _f(card.get("mean_r"))
        sharpe = _f(card.get("oos_sharpe", card.get("sharpe")))
        dd_pct = _f(card.get("oos_dd_pct", card.get("dd_pct")))
        child_w = str(card.get("child_weight_sha") or "")
        init_w = str(card.get("init_weight_sha") or "")
        child_med = _f(card.get("child_median_win_r"))
        parent_med = _f(card.get("parent_median_win_r"))
        at_nb = _f(card.get("occupancy_at_nb"))
        full = _f(card.get("occupancy_full_tape"))
        if full is None:
            full = _f(card.get("occupancy"))
        edge = _f(card.get("edge"))
        loss = _f(card.get("median_loss_r"))
        ci = _f(card.get("paired_ci_low"))
        replay = bool(card.get("parent_replay_present"))
        n_plant = int(card.get("n_plant") or 0)
    snap = AwakeningSnapshot(
        n_b=n_b,
        n_plant=n_plant,
        occupancy=full,
        occupancy_at_nb=at_nb,
        occupancy_full_tape=full,
        wr=wr,
        birth_oos_wr=birth_wr,
        mean_r=mean_r,
        birth_mean_r=birth_mean,
        edge=edge,
        median_loss_r=loss,
        sharpe=sharpe,
        dd_pct=dd_pct,
        stable_class=classify_stable(n_b=n_b, sharpe=sharpe, dd_pct=dd_pct),
        freeze_ok=True,
        policy_only=True,
        child_weight_sha=child_w,
        init_weight_sha=init_w,
        twin_watch_n=1,
        recovery_ok=True,
        regime_observed=("trend",),
        parent_replay_present=replay,
        paired_ci_low=ci,
        child_median_win_r=child_med,
        parent_median_win_r=parent_med,
    )
    return evaluate_awakening_pass(snap).passed


def _exam_passer_replaces_failing_incumbent(
    child: dict[str, Any],
    incumbent: dict[str, Any],
) -> bool:
    """A child that clears the exam replaces an incumbent that does not.

    Paired-delta rank and skill-regression stay in force when both cards pass
    or both fail. They must not preserve a median-win collapse over a card
    that already clears every policy gate.
    """
    birth_mean = _f(child.get("birth_mean_r"))
    birth_wr = _f(child.get("birth_exit_winrate", child.get("birth_oos_wr")))
    if birth_mean is None or birth_wr is None:
        return False
    return _policy_exam_passed(
        child, incumbent=False, birth_mean=birth_mean, birth_wr=birth_wr
    ) and not _policy_exam_passed(
        incumbent, incumbent=True, birth_mean=birth_mean, birth_wr=birth_wr
    )


def keep_block_reason(child: dict[str, Any], incumbent: dict[str, Any]) -> str | None:
    """First failing keep branch. None means the child replaces the incumbent.

    Same predicates as the keep decision. A second, looser rule is a cheat.
    """
    from lumina_core.maturity.awakening.clock import classify_stable
    from lumina_core.maturity.awakening.law import (
        CLASS_INCONCLUSIVE,
        CLASS_REGRESS,
        N_B_MIN,
        STABLE,
        exam_occupancy,
    )

    n_b = int(child.get("policy_trades") or child.get("n_b") or 0)
    full_tape = _f(child.get("occupancy_full_tape"))
    if full_tape is None:
        full_tape = _f(child.get("occupancy"))
    exam = exam_occupancy(
        n_b=n_b,
        occupancy_at_nb=_f(child.get("occupancy_at_nb")),
        occupancy_full_tape=full_tape,
    )
    if not occupancy_in_exam_band(exam):
        return "occupancy_out_of_band"
    if _exam_passer_replaces_failing_incumbent(child, incumbent):
        return None
    inc_n = int(incumbent.get("incumbent_n_b") or 0)
    wr = _f(child.get("polish_oos_winrate", child.get("wr")))
    mean_r = _f(child.get("mean_r"))
    inc_wr = _f(incumbent.get("incumbent_wr"))
    inc_mean = _f(incumbent.get("incumbent_mean_r"))
    mean_hold = _f(child.get("mean_hold_bars"))
    geo_hold = _f(child.get("geometry_hold_bars"))
    if (
        mean_hold is not None
        and geo_hold is not None
        and n_b < N_B_MIN
        and float(mean_hold) > float(geo_hold) + 1e-12
        and inc_n > n_b
    ):
        return "overhold_volume_down"
    if skill_regressed(child, incumbent) and not _paired_delta_higher(child, incumbent):
        return "skill_regression"
    if max(n_b, inc_n) >= N_B_MIN:
        child_ci = _f(child.get("paired_ci_low"))
        inc_ci = _f(incumbent.get("incumbent_paired_ci_low"))
        if _cleared_evolution_wall(inc_ci, inc_wr) and not _cleared_evolution_wall(child_ci, wr):
            return "evolution_wall_lost"
        rank = {STABLE: 2, CLASS_INCONCLUSIVE: 1, CLASS_REGRESS: 0}
        child_cls = classify_stable(
            n_b=n_b,
            sharpe=_f(child.get("oos_sharpe", child.get("sharpe"))),
            dd_pct=_f(child.get("oos_dd_pct", child.get("dd_pct"))),
        )
        inc_cls = classify_stable(
            n_b=inc_n,
            sharpe=_f(incumbent.get("incumbent_sharpe")),
            dd_pct=_f(incumbent.get("incumbent_dd_pct")),
        )
        if rank.get(child_cls, 0) < rank.get(inc_cls, 0):
            return "stable_rank_drop"
        child_delta = _f(child.get("paired_delta"))
        inc_delta = _f(incumbent.get("incumbent_paired_delta"))
        if child_delta is not None and inc_delta is not None:
            if float(child_delta) > float(inc_delta) + 1e-12:
                return None
            if float(child_delta) + 1e-12 < float(inc_delta):
                return "paired_delta_not_higher"
    wr_better = wr is not None and inc_wr is not None and float(wr) > float(inc_wr) + 1e-12
    mean_better = (
        mean_r is not None and inc_mean is not None and float(mean_r) > float(inc_mean) + 1e-12
    )
    n_better = n_b > inc_n and max(n_b, inc_n) < N_B_MIN
    if wr_better or mean_better or n_better:
        return None
    return "no_prefer_better"


def child_beats_incumbent(child: dict[str, Any], incumbent: dict[str, Any]) -> bool:
    """Keep a child that is not a skill regression.

    Live freeze: n_B 131 < 150 discarded a WR *gain* (33.6% vs 32%) so every
    cycle restored π* and the HUD never moved. Volume-down + skill-up is
    prefer-better. Volume-up + WR and mean_r both down is taxi, discard.
    After n_B≥500, more closes are not a win. Occupancy OOB never keeps.
    """
    return keep_block_reason(child, incumbent) is None


def _paired_delta_higher(child: dict[str, Any], incumbent: dict[str, Any]) -> bool:
    child_delta = _f(child.get("paired_delta"))
    inc_delta = _f(incumbent.get("incumbent_paired_delta"))
    if child_delta is None or inc_delta is None:
        return False
    return float(child_delta) > float(inc_delta) + 1e-12


def _cleared_evolution_wall(ci_low: float | None, wr: float | None) -> bool:
    """Wall is paired CI ≥ +0.05R or OOS ≥ 45%. Winrate lift does not clear it."""
    from lumina_core.birth.evolution_proof_gate import PAIRED_REGRET_MIN_R
    from lumina_core.maturity.post_birth_skill_gates import EVOLUTION_PROOF_OOS_WR_MIN

    if wr is not None and float(wr) + 1e-12 >= float(EVOLUTION_PROOF_OOS_WR_MIN):
        return True
    if ci_low is not None and float(ci_low) + 1e-12 >= float(PAIRED_REGRET_MIN_R):
        return True
    return False


def freeze_incumbent_ledgers(workspace_root: Path) -> bool:
    """Copy the kept child's holdout and the frozen parent replay beside the incumbent zip.

    Returns False when either live ledger is missing. Callers must not invent one.
    """
    from lumina_core.maturity.phase_runners.awakening_shot import (
        INCUMBENT_LEDGER_NAME,
        INCUMBENT_PARENT_LEDGER_NAME,
        LEDGER_NAME,
        artifacts_dir,
    )

    art = artifacts_dir(Path(workspace_root))
    child = art / LEDGER_NAME
    parent = art / "awakening_parent_holdout.jsonl"
    if not child.is_file() or child.stat().st_size <= 0:
        return False
    if not parent.is_file() or parent.stat().st_size <= 0:
        return False
    (art / INCUMBENT_LEDGER_NAME).write_bytes(child.read_bytes())
    (art / INCUMBENT_PARENT_LEDGER_NAME).write_bytes(parent.read_bytes())
    return True


def parent_replay_card(workspace_root: Path) -> dict[str, Any]:
    """Holdout stats of the frozen parent replay. Never a copy of the child shot."""
    from lumina_core.birth.birth_exit_policy_export import resolve_pi_star_path
    from lumina_core.birth.foundation_metrics import mean_r
    from lumina_core.maturity.awakening.weight_sha import PolicyWeightShaError, policy_weight_sha256
    from lumina_core.maturity.phase_runners.awakening_shot import (
        INCUMBENT_PARENT_LEDGER_NAME,
        artifacts_dir,
    )

    root = Path(workspace_root)
    sha = ""
    frozen = resolve_pi_star_path(root)
    if frozen.is_file() and frozen.stat().st_size > 0:
        try:
            sha = policy_weight_sha256(frozen)
        except PolicyWeightShaError:
            sha = ""
    rows = _policy_rows(artifacts_dir(root) / INCUMBENT_PARENT_LEDGER_NAME)
    if rows is None:
        return {
            "parent_holdout_n_b": None,
            "parent_holdout_wr": None,
            "parent_holdout_mean_r": None,
            "parent_holdout_sha": sha,
        }
    pnl = [_row_float(row, "pnl") for row in rows if row.get("pnl") is not None]
    rs = [_row_float(row, "trade_r") for row in rows if row.get("trade_r") is not None]
    wins = sum(1 for value in pnl if value > 0.0)
    return {
        "parent_holdout_n_b": len(rows),
        "parent_holdout_wr": (float(wins) / float(len(pnl))) if pnl else None,
        "parent_holdout_mean_r": mean_r(rs) if rs else None,
        "parent_holdout_sha": sha,
    }


def _policy_rows(path: Path) -> list[dict[str, Any]] | None:
    if not path.is_file() or path.stat().st_size <= 0:
        return None
    rows: list[dict[str, Any]] = []
    try:
        for line in path.read_text(encoding="utf-8").splitlines():
            raw = line.strip()
            if not raw:
                continue
            row = json.loads(raw)
            if isinstance(row, dict) and not _is_plant_row(row):
                rows.append(row)
    except (OSError, ValueError, TypeError):
        return None
    return rows


def _is_plant_row(row: dict[str, Any]) -> bool:
    if bool(row.get("plant")):
        return True
    return str(row.get("skill_grade") or "").strip().lower() == "plant"


def _row_float(row: dict[str, Any], key: str) -> float:
    try:
        return float(row.get(key) or 0.0)
    except (TypeError, ValueError):
        return 0.0


def persist_incumbent_proof(workspace_root: Path, incumbent: dict[str, Any]) -> None:
    """Evolution-proof disk SSOT follows the kept organism, not a discarded shot."""
    from lumina_core.birth.birth_exit_policy_export import file_sha256
    from lumina_core.birth.evolution_proof_gate import record_and_evaluate_at_certificate
    from lumina_core.birth.fitness_vector import load_fitness_vector
    from lumina_core.maturity.phase_runners.awakening_shot import (
        CHILD_META_NAME,
        CHILD_SCHEMA,
        artifacts_dir,
        live_child_zip,
    )

    root = Path(workspace_root)
    wr = _f(incumbent.get("incumbent_wr"))
    n_b = int(incumbent.get("incumbent_n_b") or 0)
    vector = load_fitness_vector(root)
    birth = float(vector.oos_wr) if vector is not None else 0.0
    child = live_child_zip(root)
    sha = file_sha256(child) if child.is_file() else str(incumbent.get("incumbent_sha") or "")
    init_sha = str(incumbent.get("init_sha") or incumbent.get("incumbent_init_sha") or "")
    if not init_sha:
        from lumina_core.maturity.awakening.progress import load_awakening_progress

        init_sha = str(load_awakening_progress(root).get("init_sha") or "")
    record_and_evaluate_at_certificate(
        root,
        eval_result={
            "oos_winrate": float(wr or 0.0),
            "holdout_trades": n_b,
            "paired_ci_low": _f(incumbent.get("incumbent_paired_ci_low")),
            "paired_delta": _f(incumbent.get("incumbent_paired_delta")),
            "parent_replay_present": bool(incumbent.get("incumbent_parent_replay_present")),
            "child_median_win_r": _f(incumbent.get("incumbent_child_median_win_r")),
            "parent_median_win_r": _f(incumbent.get("incumbent_parent_median_win_r")),
        },
        birth_exit_winrate=birth,
        child_sha256=sha,
        init_sha256=init_sha,
    )
    reports = artifacts_dir(root)
    reports.mkdir(parents=True, exist_ok=True)
    sidecar = {
        "schema": CHILD_SCHEMA,
        "path": str(child),
        "sha256": sha,
        "init_sha256": init_sha,
        "oos_winrate": float(wr or 0.0),
        "holdout_trades": n_b,
        "birth_exit_winrate": birth,
        "incumbent": True,
    }
    (reports / CHILD_META_NAME).write_text(json.dumps(sidecar, indent=2) + "\n", encoding="utf-8")


def sync_student_zip(
    workspace_root: Path,
    *,
    child: Path,
    incumbent: Path,
    reset: bool,
) -> None:
    """Keep the student weights, or copy the exam incumbent back over them.

    ``reset`` is skill regression only. Occupancy misses do not call this
    with reset=True. The exam zip is updated by the caller.
    """
    dest = student_zip(workspace_root)
    if reset:
        copy_zip(incumbent, dest)
        return
    copy_zip(child, dest)


def copy_zip(src: Path, dest: Path) -> None:
    from lumina_core.maturity.awakening.freeze_pin import refuse_birth_pi_star_write

    if not src.is_file() or src.stat().st_size <= 0:
        return
    refuse_birth_pi_star_write(dest)
    dest.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(src, dest)


def _f(value: Any) -> float | None:
    if value is None or value == "":
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


__all__ = [
    "INCUMBENT_ZIP_NAME",
    "STUDENT_ZIP_NAME",
    "child_beats_incumbent",
    "copy_zip",
    "incumbent_from_shot",
    "incumbent_zip",
    "keep_block_reason",
    "last_shot_card",
    "progress_from_incumbent",
    "skill_regressed",
    "student_zip",
    "sync_student_zip",
    "occupancy_in_exam_band",
    "persist_incumbent_proof",
    "freeze_incumbent_ledgers",
    "parent_replay_card",
]

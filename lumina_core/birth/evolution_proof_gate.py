"""Post-birth Evolution Proof gate before REAL promotion (ADR-0026 / ADR-0049).

n_B >= 500 is hard. ``effective_min_trades`` was a cheat and is gone.
The 5pp winrate point estimate is a diagnosis. The wall is a day-blocked
paired-regret lower bound, or OOS >= 45%.
"""

from __future__ import annotations

import json
import random
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from lumina_core.logging_utils import get_logger

logger = get_logger("lumina.birth.evolution_proof")


N_B_MIN = 500
PAIRED_REGRET_MIN_R = 0.05
_BOOT_DRAWS = 2000
_BOOT_SEED = 20260924


@dataclass(slots=True)
class EvolutionProofConfig:
    min_trades: int = N_B_MIN
    min_winrate_lift: float = 0.05
    polish_oos_winrate_min: float = 0.45


@dataclass(slots=True)
class EvolutionProofResult:
    passed: bool
    reasons: list[str]
    birth_exit_winrate: float | None
    polish_oos_winrate: float | None
    winrate_lift: float | None
    holdout_trades: int = 0
    paired_ci_low: float | None = None
    paired_delta: float | None = None
    parent_replay_present: bool = False
    child_median_win_r: float | None = None
    parent_median_win_r: float | None = None


def evolution_proof_state_path(workspace_root: Path | str) -> Path:
    return Path(workspace_root) / "state" / "lumina_evolution_proof.json"


def load_evolution_proof_record(workspace_root: Path | str) -> dict[str, Any]:
    path = evolution_proof_state_path(workspace_root)
    if not path.is_file():
        return {}
    try:
        loaded = json.loads(path.read_text(encoding="utf-8"))
        return loaded if isinstance(loaded, dict) else {}
    except Exception:
        return {}


def save_evolution_proof_record(workspace_root: Path | str, payload: dict[str, Any]) -> None:
    path = evolution_proof_state_path(workspace_root)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=True, indent=2), encoding="utf-8")


def median_win_collapsed(child: float | None, parent: float | None) -> bool:
    """True when the child's median win is below half the parent's. No parent win: no block."""
    if child is None or parent is None:
        return False
    return float(child) + 1e-12 < 0.5 * float(parent)


def attach_session_days(
    rows: list[dict[str, Any]],
    tape: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    """Copy the holdout bar timestamp onto a close. Never invent a day."""
    stamped: list[dict[str, Any]] = []
    for row in rows:
        copied = dict(row)
        if copied.get("ts_iso") or copied.get("day"):
            stamped.append(copied)
            continue
        idx = copied.get("entry_bar_index")
        if isinstance(idx, bool) or not isinstance(idx, int):
            stamped.append(copied)
            continue
        if idx < 0 or idx >= len(tape) or not isinstance(tape[idx], dict):
            stamped.append(copied)
            continue
        ts = tape[idx].get("timestamp")
        if isinstance(ts, str) and ts:
            copied["ts_iso"] = ts
        stamped.append(copied)
    return stamped


def require_policy_session_days(rows: list[dict[str, Any]]) -> None:
    """Refuse a policy close that still has no session day. Plant rows are not the exam."""
    for row in rows:
        if not isinstance(row, dict):
            continue
        if row.get("plant") is True or row.get("plant_entry") is True:
            continue
        if row.get("pnl") is None and _f(row.get("trade_r")) is None:
            continue
        if _day_key(row) is None:
            raise RuntimeError("policy close has no session day")


def paired_book_from_rows(
    child_rows: list[dict[str, Any]],
    parent_rows: list[dict[str, Any]],
) -> dict[str, Any]:
    """Day-blocked child minus frozen parent. One undated non-plant row fails closed."""
    child_days = _day_means(child_rows)
    parent_days = _day_means(parent_rows)
    child_med = _median_win(child_rows)
    parent_med = _median_win(parent_rows)
    if child_days is None or parent_days is None:
        return _absent(child_med, parent_med)
    shared = sorted(set(child_days) & set(parent_days))
    if not shared:
        return _absent(child_med, parent_med)
    deltas = [child_days[day] - parent_days[day] for day in shared]
    return {
        "parent_replay_present": True,
        "paired_delta": sum(deltas) / len(deltas),
        "paired_ci_low": _bootstrap_low(deltas),
        "child_median_win_r": child_med,
        "parent_median_win_r": parent_med,
    }


def evaluate_evolution_proof(
    *,
    birth_exit_winrate: float,
    polish_oos_winrate: float,
    holdout_trades: int,
    cfg: EvolutionProofConfig | None = None,
    child_closes: list[dict[str, Any]] | None = None,
    parent_closes: list[dict[str, Any]] | None = None,
    paired_ci_low: float | None = None,
    paired_delta: float | None = None,
    parent_replay_present: bool = False,
    child_median_win_r: float | None = None,
    parent_median_win_r: float | None = None,
) -> EvolutionProofResult:
    proof_cfg = cfg or EvolutionProofConfig()
    if child_closes is not None or parent_closes is not None:
        book = paired_book_from_rows(list(child_closes or []), list(parent_closes or []))
        paired_ci_low = book["paired_ci_low"]
        paired_delta = book["paired_delta"]
        parent_replay_present = bool(book["parent_replay_present"])
        child_median_win_r = book["child_median_win_r"]
        parent_median_win_r = book["parent_median_win_r"]
    reasons: list[str] = []
    lift = float(polish_oos_winrate) - float(birth_exit_winrate)
    min_trades = int(proof_cfg.min_trades)
    n_ok = int(holdout_trades) >= min_trades
    if not n_ok:
        reasons.append(f"holdout_trades {holdout_trades} < min {min_trades}")
    scalp = median_win_collapsed(child_median_win_r, parent_median_win_r)
    if scalp:
        reasons.append("median_win_r_collapsed")
    oos_ok = float(polish_oos_winrate) + 1e-12 >= float(proof_cfg.polish_oos_winrate_min)
    ci_ok = (
        parent_replay_present
        and paired_ci_low is not None
        and float(paired_ci_low) + 1e-12 >= PAIRED_REGRET_MIN_R
    )
    if oos_ok:
        reasons.append(
            f"polish_oos_winrate {polish_oos_winrate:.1%} >= {proof_cfg.polish_oos_winrate_min:.1%}"
        )
    elif ci_ok:
        reasons.append(f"paired regret CI {float(paired_ci_low):.4f}R >= {PAIRED_REGRET_MIN_R:.2f}R")
    elif not parent_replay_present:
        reasons.append("parent_replay_missing")
    else:
        shown = "missing" if paired_ci_low is None else f"{float(paired_ci_low):.4f}R"
        reasons.append(f"paired regret CI {shown} < {PAIRED_REGRET_MIN_R:.2f}R")
    reasons.append(
        f"winrate_lift {lift:.1%} (diagnostic, birth {float(birth_exit_winrate):.1%} "
        f"→ OOS {float(polish_oos_winrate):.1%})"
    )
    return EvolutionProofResult(
        passed=n_ok and not scalp and (oos_ok or ci_ok),
        reasons=reasons,
        birth_exit_winrate=float(birth_exit_winrate),
        polish_oos_winrate=float(polish_oos_winrate),
        winrate_lift=lift,
        holdout_trades=int(holdout_trades),
        paired_ci_low=paired_ci_low,
        paired_delta=paired_delta,
        parent_replay_present=bool(parent_replay_present),
        child_median_win_r=child_median_win_r,
        parent_median_win_r=parent_median_win_r,
    )


def record_and_evaluate_at_certificate(
    workspace_root: Path | str,
    *,
    eval_result: dict[str, Any],
    birth_exit_winrate: float,
    cfg: EvolutionProofConfig | None = None,
    child_sha256: str | None = None,
    init_sha256: str | None = None,
) -> EvolutionProofResult:
    oos_wr = float(eval_result.get("oos_winrate", eval_result.get("winrate", 0.0)) or 0.0)
    holdout_trades = int(eval_result.get("holdout_trades", 0) or 0)
    result = evaluate_evolution_proof(
        birth_exit_winrate=float(birth_exit_winrate),
        polish_oos_winrate=oos_wr,
        holdout_trades=holdout_trades,
        cfg=cfg,
        child_closes=eval_result.get("child_closes"),
        parent_closes=eval_result.get("parent_closes"),
        paired_ci_low=_f(eval_result.get("paired_ci_low")),
        paired_delta=_f(eval_result.get("paired_delta")),
        parent_replay_present=bool(eval_result.get("parent_replay_present")),
        child_median_win_r=_f(eval_result.get("child_median_win_r")),
        parent_median_win_r=_f(eval_result.get("parent_median_win_r")),
    )
    payload = {
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "passed": result.passed,
        "reasons": list(result.reasons),
        "birth_exit_winrate": result.birth_exit_winrate,
        "polish_oos_winrate": result.polish_oos_winrate,
        "oos_winrate": result.polish_oos_winrate,
        "winrate_lift": result.winrate_lift,
        "holdout_trades": result.holdout_trades,
        "paired_delta": result.paired_delta,
        "paired_ci_low": result.paired_ci_low,
        "child_median_win_r": result.child_median_win_r,
        "parent_median_win_r": result.parent_median_win_r,
        "parent_replay_present": result.parent_replay_present,
        "child_sha256": str(child_sha256 or ""),
        "init_sha256": str(init_sha256 or ""),
    }
    save_evolution_proof_record(workspace_root, payload)
    logger.info(
        "birth.evolution_proof evaluated passed=%s birth_exit=%.2f%% oos=%.2f%%",
        result.passed,
        float(birth_exit_winrate) * 100.0,
        oos_wr * 100.0,
    )
    return result


def evolution_proof_passed(
    workspace_root: Path | str,
    *,
    allow_legacy_grandfather: bool | None = None,
) -> bool:
    """True only when a persisted record exists and still passes ADR-0049.

    Missing file is fail-closed (False). Grandfather is gone.
    A disk ``passed: true`` with n_B < 500 re-evaluates to False.
    """
    del allow_legacy_grandfather
    record = load_evolution_proof_record(workspace_root)
    if not record:
        return False
    if not record.get("passed"):
        return False
    try:
        result = evaluate_evolution_proof(
            birth_exit_winrate=float(record.get("birth_exit_winrate") or 0.0),
            polish_oos_winrate=float(
                record.get("polish_oos_winrate") or record.get("oos_winrate") or 0.0
            ),
            holdout_trades=int(record.get("holdout_trades") or 0),
            paired_ci_low=_f(record.get("paired_ci_low")),
            paired_delta=_f(record.get("paired_delta")),
            parent_replay_present=bool(record.get("parent_replay_present")),
            child_median_win_r=_f(record.get("child_median_win_r")),
            parent_median_win_r=_f(record.get("parent_median_win_r")),
        )
        return bool(result.passed)
    except Exception:
        return False


def _day_means(rows: list[dict[str, Any]]) -> dict[str, float] | None:
    buckets: dict[str, list[float]] = {}
    for row in rows:
        if not isinstance(row, dict) or row.get("plant") is True:
            continue
        day = _day_key(row)
        trade_r = _f(row.get("trade_r"))
        if day is None or trade_r is None:
            return None
        buckets.setdefault(day, []).append(trade_r)
    if not buckets:
        return {}
    return {day: sum(values) / len(values) for day, values in buckets.items()}


def _day_key(row: dict[str, Any]) -> str | None:
    day = row.get("day")
    if isinstance(day, str) and day.strip():
        return day.strip()[:10]
    ts = row.get("ts_iso")
    if isinstance(ts, str) and len(ts.strip()) >= 10:
        return ts.strip()[:10]
    return None


def _median_win(rows: list[dict[str, Any]]) -> float | None:
    wins: list[float] = []
    for row in rows:
        if not isinstance(row, dict) or row.get("plant") is True:
            continue
        trade_r = _f(row.get("trade_r"))
        if trade_r is not None and trade_r > 0:
            wins.append(trade_r)
    if not wins:
        return None
    wins.sort()
    mid = len(wins) // 2
    if len(wins) % 2:
        return wins[mid]
    return (wins[mid - 1] + wins[mid]) / 2.0


def _bootstrap_low(deltas: list[float]) -> float:
    n = len(deltas)
    rng = random.Random(_BOOT_SEED)
    draws: list[float] = []
    for _ in range(_BOOT_DRAWS):
        total = 0.0
        for _day in range(n):
            total += deltas[rng.randrange(n)]
        draws.append(total / n)
    draws.sort()
    return draws[int(0.05 * (_BOOT_DRAWS - 1))]


def _absent(child_med: float | None, parent_med: float | None) -> dict[str, Any]:
    return {
        "parent_replay_present": False,
        "paired_delta": None,
        "paired_ci_low": None,
        "child_median_win_r": child_med,
        "parent_median_win_r": parent_med,
    }


def _f(value: Any) -> float | None:
    if value is None or value == "":
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        return None

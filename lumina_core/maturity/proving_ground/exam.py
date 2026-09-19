"""Eval-only cert exam metrics. Birth certificate JSON and holdout-B-only are not pass."""
from __future__ import annotations

from pathlib import Path
from typing import Any

from lumina_core.birth.foundation_metrics import S5_DD_EQUITY_USD
from lumina_core.birth.notional_cap import clip_birth_exam_pnl
from lumina_core.maturity.post_birth_skill_gates import certificate_oos_walls
from lumina_core.maturity.proving_ground.progress import load_proving_ground_progress
from lumina_core.maturity.proving_ground.tape import load_tape_rows

ALLOWED_SOURCES = frozenset({"proving_exam", "proving_tape"})
FORBIDDEN_SOURCES = frozenset({"birth_certificate", "awakening_holdout_b", "holdout_b"})
MIN_FOLDS = 5


def exam_metrics(workspace_root: Path | str) -> dict[str, Any]:
    """Honest exam snapshot. Missing folds = INCONCLUSIVE, never Birth JSON."""
    root = Path(workspace_root)
    prog = load_proving_ground_progress(root)
    source = str(prog.get("exam_source") or "").strip().lower()
    folds = _int(prog.get("exam_folds"))
    eval_only = bool(prog.get("exam_eval_only"))
    holdout_b_only = bool(prog.get("holdout_b_only"))
    oos_wr = _f(prog.get("oos_wr"))
    oos_sharpe = _f(prog.get("oos_sharpe"))
    dd_pct = _f(prog.get("dd_pct"))
    if dd_pct is None:
        dd_pct = tape_dd_pct(root)
    walls = certificate_oos_walls(oos_wr=oos_wr, oos_sharpe=oos_sharpe, max_dd_pct=dd_pct)
    return {
        "exam_source": source,
        "exam_folds": folds,
        "exam_eval_only": eval_only,
        "holdout_b_only": holdout_b_only,
        "oos_wr": oos_wr,
        "oos_sharpe": oos_sharpe,
        "dd_pct": dd_pct,
        "source_ok": source in ALLOWED_SOURCES,
        "source_forbidden": source in FORBIDDEN_SOURCES or source == "",
        "folds_ok": folds >= MIN_FOLDS,
        "certificate_oos_walls": walls.to_dict(),
    }


def tape_dd_pct(workspace_root: Path | str) -> float | None:
    pnls: list[float] = []
    for row in load_tape_rows(workspace_root):
        if str(row.get("kind") or "") != "close" or not bool(row.get("policy")):
            continue
        pnl = _clip_pnl(row)
        if pnl is None:
            continue
        pnls.append(pnl)
    if not pnls:
        return None
    equity = float(S5_DD_EQUITY_USD)
    peak = equity
    eq = equity
    worst = 0.0
    for pnl in pnls:
        eq += pnl
        if eq > peak:
            peak = eq
        dd = (peak - eq) / equity * 100.0
        if dd > worst:
            worst = dd
    return worst


def _clip_pnl(row: dict[str, Any]) -> float | None:
    raw = row.get("pnl")
    if raw is None or raw == "":
        return None
    try:
        pnl = float(raw)
    except (TypeError, ValueError):
        return None
    px = row.get("fill_px") or row.get("entry_px")
    try:
        entry = float(px) if px not in (None, "") else 0.0
    except (TypeError, ValueError):
        entry = 0.0
    qty = int(row.get("qty") or 1)
    if entry > 0.0:
        return clip_birth_exam_pnl(pnl, entry_price=entry, qty=max(1, qty), equity=S5_DD_EQUITY_USD)
    return pnl


def _f(value: Any) -> float | None:
    if value is None or value == "":
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def _int(value: Any) -> int:
    try:
        return int(value or 0)
    except (TypeError, ValueError):
        return 0

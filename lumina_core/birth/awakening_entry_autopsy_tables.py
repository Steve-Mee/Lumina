"""ENTRY autopsy tables T0–T4 + close-only contrast reader. Measure-only."""

from __future__ import annotations

from pathlib import Path
from statistics import median
from typing import Any

from lumina_core.birth.awakening_edge import policy_only_rows
from lumina_core.birth.awakening_mech import bucket_stats, load_close_jsonl, split_close_rows
from lumina_core.birth.awakening_select import reports_dir

HOLE_REASON = "stop"
HOLE_REGIME = "NEUTRAL"
TREND_LABELS = frozenset({"TREND_UP", "TREND_DOWN"})
FIRST_TOUCH_BARS = 3

CONTRAST_BOOKS = (
    ("grind_A", "grind_A_close_ledger.jsonl"),
    ("grind_B", "grind_B_close_ledger.jsonl"),
    ("select_A", "select_A_close_ledger.jsonl"),
    ("select_B", "select_B_close_ledger.jsonl"),
    ("hole_tax_A", "hole_tax_A_close_ledger.jsonl"),
    ("hole_tax_B", "hole_tax_B_close_ledger.jsonl"),
)


def hole_rows(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    return [
        r
        for r in rows
        if str(r.get("close_reason") or "") == HOLE_REASON
        and str(r.get("regime") or "").upper() == HOLE_REGIME
    ]


def target_rows(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    return [r for r in rows if str(r.get("close_reason") or "") == "target"]


def entry_label(row: dict[str, Any]) -> str | None:
    if "entry_regime" not in row or row.get("entry_regime") is None:
        return None
    label = str(row.get("entry_regime") or "").upper()
    if label in {"", "UNKNOWN"}:
        return "UNKNOWN"
    return label


def missing_entry(row: dict[str, Any]) -> bool:
    label = entry_label(row)
    return label is None or label == "UNKNOWN"


def optional_float(row: dict[str, Any], key: str) -> float | None:
    if key not in row or row.get(key) is None:
        return None
    try:
        return float(row.get(key))
    except (TypeError, ValueError):
        return None


def percentile(xs: list[float], p: float) -> float | None:
    if not xs:
        return None
    ordered = sorted(xs)
    if len(ordered) == 1:
        return float(ordered[0])
    k = (len(ordered) - 1) * float(p)
    lo = int(k)
    hi = min(lo + 1, len(ordered) - 1)
    w = k - lo
    return float(ordered[lo] * (1.0 - w) + ordered[hi] * w)


def share(n_hit: int, n: int) -> float:
    if n <= 0:
        return 0.0
    return float(n_hit) / float(n)


def cell_entry_stats(rows: list[dict[str, Any]]) -> dict[str, Any]:
    stats = bucket_stats(rows)
    n = len(rows)
    n_neu = sum(1 for r in rows if entry_label(r) == "NEUTRAL")
    n_tr = sum(1 for r in rows if (entry_label(r) or "") in TREND_LABELS)
    n_unk = sum(1 for r in rows if missing_entry(r))
    n_flip = sum(1 for r in rows if bool(r.get("regime_flip")))
    held = [int(r["bars_held"]) for r in rows if r.get("bars_held") is not None]
    mae = [float(v) for r in rows if (v := optional_float(r, "mae_r")) is not None]
    mfe = [float(v) for r in rows if (v := optional_float(r, "mfe_r")) is not None]
    return {
        "n": int(stats["n"]),
        "wr": float(stats["wr"]),
        "mean_r": float(stats["mean_r"]),
        "mean_usd": float(stats["mean_usd"]),
        "n_entry_neutral": n_neu,
        "n_entry_trend": n_tr,
        "n_entry_unknown": n_unk,
        "frac_entry_neutral": share(n_neu, n),
        "frac_entry_trend": share(n_tr, n),
        "frac_regime_flip": share(n_flip, n),
        "median_bars_held": (float(median(held)) if held else None),
        "p25_bars_held": percentile([float(x) for x in held], 0.25),
        "p75_bars_held": percentile([float(x) for x in held], 0.75),
        "median_mae_r": (float(median(mae)) if mae else None),
        "median_mfe_r": (float(median(mfe)) if mfe else None),
        "bars_held_missing": len(held) == 0 and n > 0,
        "mae_r_missing": len(mae) == 0 and n > 0,
    }


def table_t0(
    rows: list[dict[str, Any]],
    *,
    zip_sha256: str,
    ticks_sha16: str,
    price_sha16_value: str,
    optimizer_steps: int,
) -> dict[str, Any]:
    parts = split_close_rows(rows)
    all_stats = bucket_stats(parts["all"])
    pol_stats = bucket_stats(parts["policy"])
    return {
        "n_all": int(all_stats["n"]),
        "n_policy": int(len(parts["policy"])),
        "n_plant": int(len(parts["plant"])),
        "wr_policy": float(pol_stats["wr"]),
        "mean_r_policy": float(pol_stats["mean_r"]),
        "zip_sha256": str(zip_sha256),
        "ticks_sha16": str(ticks_sha16),
        "price_sha16": str(price_sha16_value),
        "optimizer_steps": int(optimizer_steps),
    }


def table_t1(policy: list[dict[str, Any]]) -> dict[str, Any]:
    return {
        "hole": cell_entry_stats(hole_rows(policy)),
        "target": cell_entry_stats(target_rows(policy)),
    }


def table_t2(policy: list[dict[str, Any]], *, min_n: int = 8) -> dict[str, Any]:
    cells: dict[str, list[dict[str, Any]]] = {}
    for row in policy:
        entry = entry_label(row) or "UNKNOWN"
        reason = str(row.get("close_reason") or "UNKNOWN")
        cells.setdefault(f"{entry}|{reason}", []).append(row)
    trigger = {k: bucket_stats(v) for k, v in sorted(cells.items()) if len(v) >= int(min_n)}
    small = {k: float(len(v)) for k, v in sorted(cells.items()) if len(v) < int(min_n)}
    return {"min_n": float(min_n), "trigger": trigger, "small": small}


def table_t3(policy: list[dict[str, Any]]) -> dict[str, Any]:
    hole = hole_rows(policy)
    n = len(hole)
    if n == 0:
        return {"n_hole": 0, "n_first_touch": 0, "share": 0.0, "bars_held_missing": False}
    missing = sum(1 for r in hole if r.get("bars_held") is None)
    if missing == n:
        return {"n_hole": n, "n_first_touch": None, "share": None, "bars_held_missing": True}
    n_ft = sum(
        1
        for r in hole
        if r.get("bars_held") is not None and int(r.get("bars_held") or 0) <= FIRST_TOUCH_BARS
    )
    return {
        "n_hole": n,
        "n_first_touch": n_ft,
        "share": share(n_ft, n),
        "bars_held_missing": False,
    }


def read_existing_hole_contrast(path: Path | str) -> dict[str, Any]:
    """Read-only close-side hole n / mean_r. Missing file → absent, not n=0."""
    target = Path(path)
    if not target.is_file():
        return {"absent": True, "path": str(target)}
    rows = load_close_jsonl(target)
    policy = policy_only_rows(rows)
    hole = hole_rows(policy)
    stats = bucket_stats(hole)
    return {
        "absent": False,
        "path": str(target),
        "n": int(stats["n"]),
        "mean_r": float(stats["mean_r"]),
    }


def table_t4(artifacts_dir: Path | str | None = None) -> dict[str, Any]:
    base = Path(artifacts_dir) if artifacts_dir is not None else reports_dir() / "artifacts"
    out: dict[str, Any] = {}
    for key, name in CONTRAST_BOOKS:
        out[key] = read_existing_hole_contrast(base / name)
    return out


__all__ = [
    "FIRST_TOUCH_BARS",
    "TREND_LABELS",
    "cell_entry_stats",
    "entry_label",
    "hole_rows",
    "missing_entry",
    "optional_float",
    "policy_only_rows",
    "read_existing_hole_contrast",
    "share",
    "table_t0",
    "table_t1",
    "table_t2",
    "table_t3",
    "table_t4",
    "target_rows",
]

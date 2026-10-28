"""Blind paired exam of one named rule against the First Watch baseline.

The pass flag in the file is ignored. The rows are scored again on read.
"""
from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from lumina_core.birth.evolution_proof_gate import (
    N_B_MIN,
    PAIRED_REGRET_MIN_R,
    median_win_collapsed,
    paired_book_from_rows,
)
from lumina_core.market.minute_bars import MinuteBar, load_minutes
from lumina_core.market.nt_fees import round_turn_fee_usd, spec_for
from lumina_core.maturity.playground.learning_book import read_header

SCHEMA = "playground_rule_exam_v1"


def exam_dir(workspace_root: Path | str) -> Path:
    return Path(workspace_root) / "reports" / "playground_rule_exams"


def exam_from_rows(
    rule_rows: list[dict[str, Any]],
    baseline_rows: list[dict[str, Any]],
) -> dict[str, Any]:
    book = paired_book_from_rows(rule_rows, baseline_rows)
    n_b = sum(
        1
        for row in rule_rows
        if isinstance(row, dict)
        and row.get("plant") is not True
        and row.get("flat_day") is not True
        and row.get("trade_r") is not None
    )
    reasons: list[str] = []
    if n_b < N_B_MIN:
        reasons.append(f"n_B={n_b} < {N_B_MIN}")
    if not book.get("parent_replay_present"):
        reasons.append("baseline_book_missing")
    else:
        if median_win_collapsed(book.get("child_median_win_r"), book.get("parent_median_win_r")):
            reasons.append("median_win_r_collapsed")
        ci = book.get("paired_ci_low")
        if ci is None or float(ci) + 1e-12 < PAIRED_REGRET_MIN_R:
            shown = "missing" if ci is None else f"{float(ci):.4f}R"
            reasons.append(f"paired regret CI {shown} < {PAIRED_REGRET_MIN_R:.2f}R")
    return {
        "schema": SCHEMA,
        "passed": not reasons,
        "reasons": reasons,
        "n_b": n_b,
        "paired_ci_low": book.get("paired_ci_low"),
        "paired_delta": book.get("paired_delta"),
        "child_median_win_r": book.get("child_median_win_r"),
        "parent_median_win_r": book.get("parent_median_win_r"),
        "rule_rows": rule_rows,
        "baseline_rows": baseline_rows,
    }


def write_rule_exam(
    workspace_root: Path | str,
    name: str,
    rule_rows: list[dict[str, Any]],
    baseline_rows: list[dict[str, Any]],
) -> dict[str, Any]:
    payload = exam_from_rows(rule_rows, baseline_rows)
    payload["name"] = str(name)
    path = exam_dir(workspace_root) / f"{name}.json"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=True) + "\n", encoding="utf-8")
    return payload


def rule_exam_passed(workspace_root: Path | str, name: str, sentence: dict[str, Any], symbol: str) -> bool:
    """Replay the sentence on the sealed plant's days. Stored rows do not count."""
    from lumina_core.maturity.awakening.baseline import seal_matches_disk
    from lumina_core.maturity.phase_runners.awakening_shot import (
        INCUMBENT_PARENT_LEDGER_NAME,
        artifacts_dir,
    )

    root = Path(workspace_root)
    if not seal_matches_disk(root):
        return False
    if not isinstance(sentence, dict) or not symbol:
        return False
    waited = _latest_name(root, name)
    if isinstance(waited, dict) and waited.get("wait_sealed") is True:
        return _sealed_tail_exam(root, name, sentence, symbol, waited)
    parent = artifacts_dir(root) / INCUMBENT_PARENT_LEDGER_NAME
    baseline = _jsonl(parent)
    if not baseline:
        return False
    days = _holdout_days(root, baseline)
    if not days:
        return False
    try:
        bars = tuple(bar for bar in load_minutes(root, symbol) if _bar_day(bar) in days)
    except (OSError, ValueError, KeyError):
        return False
    if not bars:
        return False
    rule_rows = replay_sentence_rows(sentence, bars, symbol)
    parent_rows = attach_flat_days(list(baseline), days)
    rule_rows = attach_flat_days(rule_rows, days)
    scored = exam_from_rows(rule_rows, parent_rows)
    scored["name"] = str(name)
    path = exam_dir(root) / f"{name}.json"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(scored, ensure_ascii=True) + "\n", encoding="utf-8")
    return bool(scored["passed"])


def attach_flat_days(rows: list[dict[str, Any]], days: set[str]) -> list[dict[str, Any]]:
    """A holdout day with no close is a flat 0R day. It is not an invented trade."""
    present = {_day(row) for row in rows}
    present.discard("")
    out = [row for row in rows if row.get("flat_day") is not True]
    for day in sorted(days):
        if day and day not in present:
            out.append(
                {
                    "plant": False,
                    "flat_day": True,
                    "trade_r": 0.0,
                    "ts_iso": f"{day}T00:00:00+00:00",
                }
            )
    return out


def _holdout_days(root: Path, baseline: list[dict[str, Any]]) -> set[str]:
    header = read_header(root)
    start = header.get("holdout_start_ns")
    end = header.get("tail_end_ns")
    symbol = str(header.get("symbol") or "")
    days: set[str] = set()
    if start is not None and end is not None and symbol:
        try:
            bars = load_minutes(root, symbol)
        except (OSError, ValueError):
            bars = ()
        for bar in bars:
            if int(start) <= bar.ts_ns < int(end):
                days.add(_bar_day(bar))
    if not days:
        days = {_day(row) for row in baseline}
        days.discard("")
    return days


def _jsonl(path: Path) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    if not path.is_file():
        return rows
    try:
        text = path.read_text(encoding="utf-8")
    except OSError:
        return rows
    for line in text.splitlines():
        raw = line.strip()
        if not raw:
            continue
        try:
            row = json.loads(raw)
        except ValueError:
            return []
        if isinstance(row, dict):
            rows.append(row)
    return rows


def _day(row: dict[str, Any]) -> str:
    for key in ("day", "ts_iso", "timestamp"):
        raw = row.get(key)
        if isinstance(raw, str) and len(raw.strip()) >= 10:
            return raw.strip()[:10]
    return ""


def _bar_day(bar: MinuteBar) -> str:
    return datetime.fromtimestamp(bar.ts_ns / 1_000_000_000, tz=timezone.utc).date().isoformat()


def _latest_name(root: Path, name: str) -> dict[str, Any] | None:
    from lumina_core.maturity.playground.learning_book import load_names

    found: dict[str, Any] | None = None
    for row in load_names(root):
        if str(row.get("name") or "") == str(name):
            found = row
    return found


def _sealed_tail_exam(
    root: Path,
    name: str,
    sentence: dict[str, Any],
    symbol: str,
    row: dict[str, Any],
) -> bool:
    """The hand exam for a sentence the birth tail could not hold.

    Trades come only from the sealed later span. The birth days are not paired in,
    because those days are a different season. The bar is still n_B and +0.05R
    against the plant's measured mean, plus the anti-scalp check.
    """
    from lumina_core.birth.evolution_proof_gate import N_B_MIN, PAIRED_REGRET_MIN_R, median_win_collapsed
    from lumina_core.market.archive_repair import unresolved_open_holes
    from lumina_core.maturity.phase_runners.awakening_shot import (
        INCUMBENT_PARENT_LEDGER_NAME,
        artifacts_dir,
    )
    from lumina_core.maturity.playground.research_kit import measured_plant_mean_r
    from lumina_core.maturity.playground.sentence_window import tail_can_grade

    try:
        start_ns = int(row["wait_tail_start_ns"])
        end_ns = int(row["wait_tail_end_ns"])
    except (KeyError, TypeError, ValueError):
        return False
    if end_ns <= start_ns:
        return False
    try:
        bars = tuple(bar for bar in load_minutes(root, symbol) if start_ns <= bar.ts_ns < end_ns)
    except (OSError, ValueError, KeyError):
        return False
    reasons: list[str] = []
    if unresolved_open_holes(root, bars) or not tail_can_grade(sentence, bars):
        reasons.append("tail_unmeasured")
        _write_wait_exam(root, name, False, reasons, 0, None)
        return False
    rule_rows = replay_sentence_rows(sentence, bars, symbol)
    n_b = len(rule_rows)
    if n_b < N_B_MIN:
        reasons.append(f"n_B={n_b} < {N_B_MIN}")
    plant = measured_plant_mean_r(root)
    mean = float(sum(float(item["trade_r"]) for item in rule_rows) / float(n_b)) if n_b else None
    if plant is None or mean is None:
        reasons.append("baseline_unmeasured")
    elif float(mean) - float(plant) + 1e-12 < PAIRED_REGRET_MIN_R:
        reasons.append(f"mean_minus_plant {float(mean) - float(plant):.4f}R < {PAIRED_REGRET_MIN_R:.2f}R")
    parent = artifacts_dir(root) / INCUMBENT_PARENT_LEDGER_NAME
    if median_win_collapsed(_median_win(rule_rows), _median_win(_jsonl(parent))):
        reasons.append("median_win_r_collapsed")
    passed = not reasons
    _write_wait_exam(root, name, passed, reasons, n_b, mean)
    return passed


def _median_win(rows: list[dict[str, Any]]) -> float | None:
    wins = sorted(
        float(row["trade_r"])
        for row in rows
        if isinstance(row, dict)
        and row.get("plant") is not True
        and row.get("flat_day") is not True
        and row.get("trade_r") is not None
        and float(row["trade_r"]) > 0.0
    )
    if not wins:
        return None
    mid = len(wins) // 2
    if len(wins) % 2:
        return wins[mid]
    return (wins[mid - 1] + wins[mid]) / 2.0


def _write_wait_exam(root: Path, name: str, passed: bool, reasons: list[str], n_b: int, mean: float | None) -> None:
    payload = {
        "schema": SCHEMA,
        "name": name,
        "exam_slice": "sealed_wait_tail",
        "passed": passed,
        "reasons": reasons,
        "n_b": n_b,
        "mean_r": mean,
    }
    path = exam_dir(root) / f"{name}.json"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=True) + "\n", encoding="utf-8")


def replay_sentence_rows(
    sentence: dict[str, Any],
    bars: tuple[MinuteBar, ...] | list[MinuteBar],
    symbol: str,
) -> list[dict[str, Any]]:
    """Same fill as the research walk, one row per close, with the entry day."""
    from lumina_core.maturity.playground.research_kit import _trade_exit, signal_true
    from lumina_core.maturity.playground.sentence_window import bar_minutes_of

    if "window" not in sentence:
        return []
    spec = spec_for(symbol)
    try:
        count = int(sentence["window"])
    except (TypeError, ValueError):
        return []
    size = bar_minutes_of(sentence)
    need = size * count
    if size == 0 or count < 1 or need < 1:
        return []
    rows: list[dict[str, Any]] = []
    series = tuple(bars)
    for index in range(need, len(series) - 1):
        history = series[index - need : index]
        if not signal_true(sentence, history, tick_size=spec.tick_size):
            continue
        closed = _trade_exit(sentence, series, index, spec.tick_size)
        if closed is None:
            continue
        exit_px, _reason = closed
        entry = series[index].close_ticks * spec.tick_size
        side = int(sentence["side"])
        gross = (exit_px - entry) * float(side) * float(spec.point_value_usd)
        risk = entry * float(sentence["stop_pct"]) * float(spec.point_value_usd)
        if risk <= 0.0:
            continue
        day = datetime.fromtimestamp(series[index].ts_ns / 1_000_000_000, tz=timezone.utc).date().isoformat()
        rows.append(
            {
                "plant": False,
                "trade_r": (gross - round_turn_fee_usd(symbol, 1)) / risk,
                "ts_iso": f"{day}T00:00:00+00:00",
            }
        )
    return rows

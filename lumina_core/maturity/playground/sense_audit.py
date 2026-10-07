"""One eye audit. Reads tails only. Does not rewrite equity and does not trade.

Holdout ledger rows are closes, not 43-vectors. The reference for trend slots
is the Birth tick cache tail. Bible slots are compared to the exam writer,
which is a label, not a 240-minute candle. A blind verdict does not authorize
copying that label into the live vector.
"""
from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from lumina_core.maturity.playground.journal import append_experiment_entry
from lumina_core.maturity.playground.sense_lab import HYPOTHESIS_TEXT, load_sense, save_sense
from lumina_core.maturity.playground.sense_slots import (
    OBSERVATION_DIM,
    classify_eyes,
    describe_vector,
)

BARS_REL = Path("state") / "lumina_playground_bars.jsonl"
TICKS_REL = Path("state") / "lumina_birth_ticks_cache.jsonl"
TAIL_BYTES = 256_000


def ensure_sense_audit(workspace_root: Path | str) -> str:
    """Append the pre-registration and the verdict once per sense file."""
    root = Path(workspace_root)
    state = load_sense(root)
    existing = str(state.get("audit_verdict") or "")
    if existing:
        return existing
    live = sample_live_vectors(root / BARS_REL)
    reference = sample_holdout_trends(root / TICKS_REL)
    session, mtf = exam_bible_pair()
    verdict = classify_eyes(
        live=live,
        reference_closes=[float(row["close"]) for row in reference],
        reference_slopes=[float(row["trend_slope_60"]) for row in reference],
        exam_bible_session=session,
        exam_bible_mtf=mtf,
    )
    described = describe_vector(live[-1]) if live else {"dim": "0", "price": None, "equity": None, "zeros": ""}
    lines = [
        "Eye audit. No order. No equity rewrite. No action flip.",
        HYPOTHESIS_TEXT,
        f"verdict={verdict}",
        f"live_rows={len(live)} reference_ticks={len(reference)}",
        f"last_price={described.get('price')} last_equity={described.get('equity')} dim={described.get('dim')}",
        f"zero_slots={described.get('zeros')}",
        f"exam_bible_session={session} exam_bible_mtf={mtf}",
        "bible_mtf_bias is the string dominant_tf, not a closed 240-minute candle.",
        "Do not copy that label into the live vector. Do not call a shadow a fill.",
        "matched is the only verdict that says the flat is the policy on recognizable input.",
        "blind means an exam slot is empty live. reference_missing is not matched.",
    ]
    append_experiment_entry(root, title="sense eye audit", lines=lines)
    state["audit_verdict"] = verdict
    save_sense(root, state)
    return verdict


def sample_live_vectors(path: Path, *, take: int = 40) -> list[list[float]]:
    rows: list[list[float]] = []
    for raw in _tail_json(path, take=take):
        obs = raw.get("observation")
        if not isinstance(obs, list) or len(obs) != OBSERVATION_DIM:
            continue
        try:
            rows.append([float(value) for value in obs])
        except (TypeError, ValueError):
            continue
    return rows[-take:]


def sample_holdout_trends(path: Path, *, take: int = 40) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for raw in _tail_json(path, take=take * 2, start_frac=0.85):
        if "trend_slope_60" not in raw or "close" not in raw:
            continue
        try:
            close = float(raw["close"])
            slope = float(raw["trend_slope_60"])
        except (TypeError, ValueError):
            continue
        if close <= 0.0:
            continue
        rows.append({"close": close, "trend_slope_60": slope})
        if len(rows) >= take:
            break
    return rows


def exam_bible_pair() -> tuple[float, float]:
    """What the Birth rollout writer would stamp on a late TREND_DOWN tick."""
    try:
        from lumina_core.birth.bible_observation import bible_features_for_tick
    except Exception:
        return 0.0, 0.0
    try:
        _c, _n, session, mtf = bible_features_for_tick(
            {"regime": "TREND_DOWN", "bar_index": 500, "imbalance": 1.0},
            workspace_root=None,
        )
    except Exception:
        return 0.0, 0.0
    return float(session), float(mtf)


def _tail_json(path: Path, *, take: int, start_frac: float | None = None) -> list[dict[str, Any]]:
    if not path.is_file():
        return []
    try:
        size = path.stat().st_size
    except OSError:
        return []
    if size <= 0:
        return []
    start = 0 if start_frac is None else min(size - 1, int(size * float(start_frac)))
    if start_frac is None:
        start = max(0, size - TAIL_BYTES)
    try:
        with path.open("rb") as handle:
            handle.seek(start)
            raw = handle.read(TAIL_BYTES)
    except OSError:
        return []
    text = raw.decode("utf-8", errors="replace")
    parsed: list[dict[str, Any]] = []
    for line in text.splitlines()[1:]:
        try:
            row = json.loads(line)
        except ValueError:
            continue
        if isinstance(row, dict):
            parsed.append(row)
    return parsed[-take:] if start_frac is None else parsed




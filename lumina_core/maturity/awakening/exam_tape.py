"""Awakening exam tape — Birth holdout B, plus later OOS if B cannot carry n_B≥500.

Train A never enters this list. Birth tick/split caches are never overwritten.
REAL: no. Source stays synthetic_cloud_fixture.
"""

from __future__ import annotations

import json
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any
from zoneinfo import ZoneInfo

from lumina_core.birth.synthetic_cloud_fixture import (
    SOURCE_LABEL,
    CloudFixtureSpec,
    generate_cloud_fixture_ticks,
)
from lumina_core.birth.tick_cache_persist import compute_ticks_fingerprint
from lumina_core.birth.tick_cache_split_codec import ticks_jsonl
from lumina_core.birth.tick_enricher import enrich_ticks_for_sim
from lumina_core.io.atomic_fs import atomic_write_text
from lumina_core.logging_utils import get_logger
from lumina_core.maturity.awakening.law import N_B_MIN

logger = get_logger("lumina.maturity.awakening.exam_tape")

ET = ZoneInfo("America/New_York")
EXAM_EXT_REL = Path("state") / "lumina_awakening_exam_ext.jsonl"
EXAM_MANIFEST_REL = Path("state") / "lumina_awakening_exam_manifest.json"
EXAM_SCHEMA = "awakening_exam_v1"
# SELECT-like frequency on Birth B is ~1 policy close / 280 ticks (~150 / 43k).
# n_B≥500 at that honest frequency needs ~140k OOS ticks — not a floor cut.
MIN_EXAM_TICKS = 150_000
AWAKENING_EXAM_SEED = 20260920
CONTINUATION_CALENDAR_DAYS = 60


def exam_ext_path(workspace_root: Path | str) -> Path:
    return Path(workspace_root) / EXAM_EXT_REL


def exam_manifest_path(workspace_root: Path | str) -> Path:
    return Path(workspace_root) / EXAM_MANIFEST_REL


def load_awakening_exam_split(
    workspace_root: Path,
    *,
    min_ticks: int = MIN_EXAM_TICKS,
) -> tuple[list[dict[str, Any]], list[dict[str, Any]], dict[str, Any]]:
    # Circular: awakening_shot's default split loader is this module.
    from lumina_core.maturity.phase_runners.awakening_shot import load_live_split

    train, holdout_b, meta = load_live_split(workspace_root)
    exam, extra = extend_exam_if_thin(
        workspace_root,
        train=train,
        holdout_b=holdout_b,
        min_ticks=int(min_ticks),
    )
    out_meta = dict(meta)
    out_meta.update(extra)
    out_meta["exam_n"] = len(exam)
    out_meta["holdout_b_n"] = len(holdout_b)
    return list(train), list(exam), out_meta


def extend_exam_if_thin(
    workspace_root: Path | str,
    *,
    train: list[dict[str, Any]],
    holdout_b: list[dict[str, Any]],
    min_ticks: int = MIN_EXAM_TICKS,
) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    if not holdout_b:
        raise RuntimeError("awakening_exam_holdout_b_empty")
    _assert_no_train_leak(train, holdout_b)
    if len(holdout_b) >= int(min_ticks):
        return list(holdout_b), {
            "exam_kind": "holdout_B",
            "exam_extended": False,
            "REAL": "no",
        }
    ext = _load_or_build_continuation(workspace_root, holdout_b=holdout_b, min_ticks=int(min_ticks))
    _assert_after(holdout_b, ext)
    _assert_no_train_leak(train, ext)
    exam = list(holdout_b) + list(ext)
    if len(exam) < int(min_ticks):
        raise RuntimeError(f"awakening_exam_too_thin n={len(exam)} min={int(min_ticks)}")
    return exam, {
        "exam_kind": "holdout_B_plus_continuation",
        "exam_extended": True,
        "continuation_n": len(ext),
        "min_exam_ticks": int(min_ticks),
        "n_b_min": int(N_B_MIN),
        "REAL": "no",
        "source": "synthetic_cloud_fixture",
    }


def _load_or_build_continuation(
    workspace_root: Path | str,
    *,
    holdout_b: list[dict[str, Any]],
    min_ticks: int,
) -> list[dict[str, Any]]:
    root = Path(workspace_root)
    cached = _load_cached_ext(root, holdout_b, min_ticks=int(min_ticks))
    if cached:
        return cached
    ext = _generate_continuation(holdout_b, min_ticks=int(min_ticks))
    _persist_ext(root, ext, holdout_b=holdout_b)
    return ext


def _load_cached_ext(
    root: Path,
    holdout_b: list[dict[str, Any]],
    *,
    min_ticks: int,
) -> list[dict[str, Any]] | None:
    path = exam_ext_path(root)
    man_path = exam_manifest_path(root)
    if not path.is_file() or not man_path.is_file():
        return None
    try:
        man = json.loads(man_path.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return None
    if not isinstance(man, dict) or str(man.get("schema") or "") != EXAM_SCHEMA:
        return None
    if str(man.get("anchor_ts") or "") != _ts(holdout_b[-1]):
        return None
    rows = _read_jsonl(path)
    if not rows:
        return None
    if len(holdout_b) + len(rows) < int(min_ticks):
        return None
    try:
        _assert_after(holdout_b, rows)
    except RuntimeError:
        return None
    return rows


def _calendar_days_for(holdout_n: int, min_ticks: int) -> int:
    needed = max(0, int(min_ticks) - int(holdout_n))
    # Birth 90d tape ≈ 2.4k ticks / calendar day at 10s RTH / 60s ETH.
    return max(CONTINUATION_CALENDAR_DAYS, int(needed / 1800) + 7)


def _generate_continuation(
    holdout_b: list[dict[str, Any]],
    *,
    min_ticks: int,
) -> list[dict[str, Any]]:
    last = holdout_b[-1]
    start_et = _next_et(_ts(last))
    start_px = float(last.get("last") or last.get("close") or 0.0)
    spec = CloudFixtureSpec(
        seed=AWAKENING_EXAM_SEED,
        calendar_days=_calendar_days_for(len(holdout_b), int(min_ticks)),
        start_et=start_et,
        start_price=start_px if start_px > 0 else 21_150.0,
    )
    raw = generate_cloud_fixture_ticks(spec)
    for row in raw:
        row["source"] = SOURCE_LABEL
        row["awakening_exam"] = True
        row["REAL"] = "no"
    raw_hash = compute_ticks_fingerprint(raw)
    enriched = enrich_ticks_for_sim(
        [dict(t) for t in raw],
        workspace_root=None,
        raw_ticks_hash=raw_hash,
    )
    for row in enriched:
        row["source"] = SOURCE_LABEL
        row["awakening_exam"] = True
        row["REAL"] = "no"
    logger.info(
        "awakening.exam.continuation_built n=%s start_et=%s",
        len(enriched),
        start_et.isoformat(),
    )
    return enriched


def _persist_ext(
    root: Path,
    ext: list[dict[str, Any]],
    *,
    holdout_b: list[dict[str, Any]],
) -> None:
    path = exam_ext_path(root)
    path.parent.mkdir(parents=True, exist_ok=True)
    atomic_write_text(path, ticks_jsonl(ext))
    man = {
        "schema": EXAM_SCHEMA,
        "REAL": "no",
        "source": "synthetic_cloud_fixture",
        "seed": AWAKENING_EXAM_SEED,
        "n": len(ext),
        "fingerprint": compute_ticks_fingerprint(ext),
        "anchor_ts": _ts(holdout_b[-1]),
        "first_ts": _ts(ext[0]) if ext else "",
        "last_ts": _ts(ext[-1]) if ext else "",
        "birth_cache_untouched": True,
    }
    atomic_write_text(exam_manifest_path(root), json.dumps(man, indent=2) + "\n")


def _assert_no_train_leak(
    train: list[dict[str, Any]],
    other: list[dict[str, Any]],
) -> None:
    if not train or not other:
        return
    train_last = _ts(train[-1])
    other_first = _ts(other[0])
    if other_first and train_last and other_first <= train_last:
        raise RuntimeError(f"awakening_exam_train_leak other_first={other_first} train_last={train_last}")


def _assert_after(holdout_b: list[dict[str, Any]], ext: list[dict[str, Any]]) -> None:
    if not ext:
        raise RuntimeError("awakening_exam_continuation_empty")
    b_last = _ts(holdout_b[-1])
    if _ts(ext[0]) <= b_last:
        raise RuntimeError(f"awakening_exam_not_after_B ext_first={_ts(ext[0])} B_last={b_last}")


def _ts(row: dict[str, Any]) -> str:
    return str(row.get("timestamp") or "")


def _next_et(ts_text: str) -> datetime:
    raw = str(ts_text or "").replace("Z", "+00:00")
    if not raw.strip():
        raise RuntimeError("awakening_exam_anchor_ts_missing")
    try:
        parsed = datetime.fromisoformat(raw)
    except ValueError as exc:
        raise RuntimeError(f"awakening_exam_anchor_ts_invalid ts={ts_text!r}") from exc
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=timezone.utc)
    return parsed.astimezone(ET) + timedelta(minutes=1)


def _read_jsonl(path: Path) -> list[dict[str, Any]]:
    out: list[dict[str, Any]] = []
    try:
        for line in path.read_text(encoding="utf-8").splitlines():
            raw = line.strip()
            if not raw:
                continue
            row = json.loads(raw)
            if isinstance(row, dict):
                out.append(row)
    except (OSError, ValueError):
        return []
    return out


__all__ = [
    "MIN_EXAM_TICKS",
    "exam_ext_path",
    "exam_manifest_path",
    "extend_exam_if_thin",
    "load_awakening_exam_split",
]

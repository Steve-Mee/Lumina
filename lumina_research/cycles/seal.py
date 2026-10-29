"""Hash-seal the P2 holdout before template selection, tuning, or gate calibration."""

from __future__ import annotations

import hashlib
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Mapping

from lumina_research.agents.objects import as_object_dict
from lumina_research.cycles.data import LoadedTape
from lumina_research.cycles.holdout import (
    EVAL_PURPOSES,
    LOCKED_PURPOSES,
    P2_HOLDOUT_START_LEGACY_NS,
    P2_HOLDOUT_START_LEGACY_UTC,
    P2_HOLDOUT_START_NS,
    P2_HOLDOUT_START_UTC,
    HoldoutLocked,
    access_bars,
)
from lumina_research.validation.audit import utc_now_iso

SEAL_NAME = "phase5_p2_holdout_seal.json"
LEGACY_SEAL_NAME = "phase5_p2_holdout_seal_legacy_2026-01-29T00Z.json"
LEGACY_SEAL_SHA256 = "6e8fa88e3aad048271cb52a63f76cbf4ed8a9261b85b85f03f631b872cf2e51b"
PENDING_COUNTS_SEAL_NAME = "phase5_p2_holdout_seal_legacy_2026-01-28T23Z_pending_counts.json"
PENDING_COUNTS_SEAL_SHA256 = "51d55d770aa21fb8f10062c7aab53acebe4866e526eb3419501098bd67172a99"
LIVE_SEAL_SHA256 = "85e4588fde77159315a72bdaa722d6487f93bbad9bf24999311f893950489d40"
ZIP_SHA256: Mapping[str, str] = {
    "MES": "c5c094a199502fde9cc79f535441995ba7e326811e4e7e01bf1833a25c9c7b2e",
    "MNQ": "a1cefabd46c4109a93bb219df45d134f9e3e16ffd3abc8250242c88a3ee5d6e8",
}
CSV_SHA256: Mapping[str, str] = {
    "MES": "a9e9100c5544d59120a37a994955633e835cec8938ed20048164d0f726cf9c01",
    "MNQ": "47422de88a2f662c664425b87d79d29fa7a5854d99ed76dd0b946bee7e7a9bf1",
}


def file_sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        while True:
            chunk = handle.read(1024 * 1024)
            if not chunk:
                break
            digest.update(chunk)
    return digest.hexdigest()


def seal_holdout(
    tapes: tuple[LoadedTape, ...],
    *,
    report_dir: Path,
    require_known_files: bool = True,
) -> dict[str, object]:
    """Lock the Globex session boundary onward. Call before any simulate() or gate."""
    report_dir.mkdir(parents=True, exist_ok=True)
    instruments: dict[str, object] = {}
    for tape in tapes:
        root = tape.instrument
        pinned = P2_HOLDOUT_START_NS
        locked_tape = LoadedTape(
            instrument=tape.instrument,
            bar_size=tape.bar_size,
            path=tape.path,
            bars=tape.bars,
            holdout_start_ns=pinned,
        )
        train = access_bars(locked_tape, purpose="gate", pinned_start_ns=pinned)
        holdout = access_bars(locked_tape, purpose="evaluation", pinned_start_ns=pinned)
        source = file_sha256(tape.path) if tape.path.is_file() else ""
        expected = CSV_SHA256.get(root)
        if require_known_files and expected is not None and source != expected:
            raise HoldoutLocked(f"{root} csv sha256 mismatch; refuse to seal")
        instruments[root] = {
            "path": f"$LUMINA_RESEARCH_DATA_DIR/{root}/{tape.bar_size}/{tape.path.name}",
            "bar_size": tape.bar_size,
            "n_bars": len(tape.bars),
            "first_utc": _iso(tape.bars[0].ts_ns),
            "last_utc": _iso(tape.bars[-1].ts_ns),
            "file_sha256": source,
            "zip_sha256": ZIP_SHA256.get(root, ""),
            "n_train": len(train),
            "n_holdout": len(holdout),
            "train_last_utc": _iso(train[-1].ts_ns),
            "holdout_first_utc": _iso(holdout[0].ts_ns),
            "holdout_last_utc": _iso(holdout[-1].ts_ns),
        }
        if train[-1].ts_ns >= pinned or holdout[0].ts_ns < pinned:
            raise HoldoutLocked(f"{root} holdout split leaked across {P2_HOLDOUT_START_UTC.isoformat()}")
    _preserve_legacy_seal(report_dir)
    body: dict[str, object] = {
        "holdout_start_utc": P2_HOLDOUT_START_UTC.isoformat(),
        "holdout_start_ns": P2_HOLDOUT_START_NS,
        "previous_seals": _previous_seal_records(),
        "holdout_months": 9,
        "locked_purposes": sorted(LOCKED_PURPOSES),
        "eval_purposes": sorted(EVAL_PURPOSES),
        "sealed_at": utc_now_iso(),
        "note": (
            "Holdout resealed at the Globex session boundary 2026-01-28T23:00:00Z. "
            "Previous seals 6e8fa88e (2026-01-29T00:00:00Z) and 51d55d77 "
            "(23:00Z, bar counts pending recompute) stay recorded. The window stays unopened "
            "for selection, tuning, and gate calibration."
        ),
        "instruments": instruments,
    }
    canonical = json.dumps(body, sort_keys=True, separators=(",", ":")).encode("utf-8")
    body["seal_sha256"] = hashlib.sha256(canonical).hexdigest()
    path = report_dir / SEAL_NAME
    path.write_text(json.dumps(body, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    body["path"] = str(path)
    return body


def reuse_holdout_seal(
    tapes: tuple[LoadedTape, ...],
    *,
    report_dir: Path,
) -> dict[str, object] | None:
    """Return the current seal when pin and CSV hashes already match. Do not rewrite."""
    try:
        loaded = load_seal(report_dir)
    except HoldoutLocked:
        return None
    if loaded.get("bar_counts_pending_recompute") is True:
        return None
    instruments = as_object_dict(loaded.get("instruments"))
    if instruments is None:
        return None
    for tape in tapes:
        row = as_object_dict(instruments.get(tape.instrument))
        if row is None:
            return None
        source = file_sha256(tape.path) if tape.path.is_file() else ""
        expected = CSV_SHA256.get(tape.instrument)
        if not source or source != expected or row.get("file_sha256") != source:
            return None
        train_n = row.get("n_train")
        hold_n = row.get("n_holdout")
        if not isinstance(train_n, int) or not isinstance(hold_n, int) or train_n < 1 or hold_n < 1:
            return None
    return loaded


def load_seal(report_dir: Path) -> dict[str, object]:
    path = report_dir / SEAL_NAME
    if not path.is_file():
        raise HoldoutLocked("holdout seal missing; refuse to run the cycle")
    loaded: object = json.loads(path.read_text(encoding="utf-8"))
    typed = as_object_dict(loaded)
    if typed is None:
        raise HoldoutLocked("holdout seal is not an object")
    start: object = typed.get("holdout_start_ns")
    if start != P2_HOLDOUT_START_NS:
        raise HoldoutLocked("holdout seal drifted from 2026-01-28T23:00:00Z")
    return typed


def _previous_seal_records() -> list[dict[str, object]]:
    return [
        {
            "holdout_start_utc": P2_HOLDOUT_START_LEGACY_UTC.isoformat(),
            "holdout_start_ns": P2_HOLDOUT_START_LEGACY_NS,
            "seal_sha256": LEGACY_SEAL_SHA256,
            "file": LEGACY_SEAL_NAME,
            "note": "P2 first cycle 2026-10-29; holdout never opened for ranking or calibration",
        },
        {
            "holdout_start_utc": P2_HOLDOUT_START_UTC.isoformat(),
            "holdout_start_ns": P2_HOLDOUT_START_NS,
            "seal_sha256": PENDING_COUNTS_SEAL_SHA256,
            "file": PENDING_COUNTS_SEAL_NAME,
            "note": (
                "Globex 23:00Z pin written before NT8 CSVs were mounted; "
                "bar counts were pending recompute. Holdout never opened."
            ),
        },
    ]


def _preserve_legacy_seal(report_dir: Path) -> None:
    current = report_dir / SEAL_NAME
    if not current.is_file():
        return
    payload: object = json.loads(current.read_text(encoding="utf-8"))
    typed = as_object_dict(payload)
    if typed is None:
        return
    text = current.read_text(encoding="utf-8")
    legacy = report_dir / LEGACY_SEAL_NAME
    if not legacy.is_file() and typed.get("holdout_start_ns") == P2_HOLDOUT_START_LEGACY_NS:
        legacy.write_text(text, encoding="utf-8")
    pending = report_dir / PENDING_COUNTS_SEAL_NAME
    if not pending.is_file() and typed.get("seal_sha256") == PENDING_COUNTS_SEAL_SHA256:
        pending.write_text(text, encoding="utf-8")


def _iso(ts_ns: int) -> str:
    return datetime.fromtimestamp(ts_ns / 1_000_000_000, tz=timezone.utc).isoformat()

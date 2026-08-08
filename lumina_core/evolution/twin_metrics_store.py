"""Twin metrics store I/O (M5 extract). Types in twin_metrics_types."""
from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from lumina_core.evolution.twin_metrics_reports import TwinMetricsReportsMixin
from lumina_core.evolution.twin_metrics_types import (
    HIGH_CONF_THRESHOLD,
    ComparisonSource,
    TwinComparisonEvent,
    TwinModeMetricsSnapshot,
    _clamp01,
    _resolve_audit_path,
    _resolve_paths,
    _tail_text_lines,
    _utcnow,
    recompute_row_derived,
)

class TwinMetricsStore(TwinMetricsReportsMixin):
    """Append-only store for twin mode promotion evidence + observability rollups."""

    def __init__(
        self,
        *,
        path: Path | str | None = None,
        summary_path: Path | str | None = None,
        audit_path: Path | str | None = None,
    ) -> None:
        default_path, default_summary = _resolve_paths()
        self.path = Path(path) if path is not None else default_path
        self.summary_path = Path(summary_path) if summary_path is not None else default_summary
        self.audit_path = Path(audit_path) if audit_path is not None else _resolve_audit_path()

    def record(self, event: TwinComparisonEvent) -> TwinComparisonEvent:
        payload = event.to_dict()
        self.path.parent.mkdir(parents=True, exist_ok=True)
        with self.path.open("a", encoding="utf-8") as fh:
            fh.write(json.dumps(payload, sort_keys=True) + "\n")
        try:
            # O(1) incremental rollup — never rescan multi-10MB JSONL per event.
            self._apply_event_to_summary(payload)
        except Exception:
            try:
                self._refresh_summary()
            except Exception:
                pass
        return event

    def record_comparison(
        self,
        *,
        twin_recommendation: bool,
        ground_truth_approve: bool,
        source: ComparisonSource,
        risk_flags: list[str] | None = None,
        dna_hash: str = "",
        mode: str = "shadow",
        constitution_fatal: bool = False,
        twin_confidence: float | None = None,
        steve_label: str = "",
    ) -> TwinComparisonEvent:
        event = TwinComparisonEvent(
            twin_recommendation=bool(twin_recommendation),
            ground_truth_approve=bool(ground_truth_approve),
            source=source,
            risk_flags=list(risk_flags or []),
            dna_hash=str(dna_hash or "")[:64],
            mode=str(mode or "shadow"),
            constitution_fatal=bool(constitution_fatal),
            twin_confidence=_clamp01(twin_confidence),
            steve_label=str(steve_label or "")[:64],
        )
        return self.record(event)

    def load_events(self, *, limit: int | None = None) -> list[dict[str, Any]]:
        if not self.path.exists():
            return []
        # Bounded reads: never materialize multi-10MB JSONL just for a short window.
        if limit is not None and int(limit) > 0:
            lines = _tail_text_lines(self.path, int(limit))
        else:
            try:
                lines = self.path.read_text(encoding="utf-8").splitlines()
            except OSError:
                return []
        out: list[dict[str, Any]] = []
        for raw in lines:
            raw = raw.strip()
            if not raw:
                continue
            try:
                row = json.loads(raw)
            except json.JSONDecodeError:
                continue
            if isinstance(row, dict):
                out.append(recompute_row_derived(row))
        return out

    def _snapshot_from_summary(self) -> TwinModeMetricsSnapshot | None:
        """Load durable rollup counters when present (O(1) vs full JSONL scan)."""
        if not self.summary_path.is_file():
            return None
        try:
            raw = json.loads(self.summary_path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError, TypeError, ValueError):
            return None
        if not isinstance(raw, dict):
            return None
        samples = int(raw.get("samples", 0) or 0)
        if samples <= 0:
            return None
        try:
            return TwinModeMetricsSnapshot(
                samples=samples,
                agreements=int(raw.get("agreements", 0) or 0),
                disagreements=int(raw.get("disagreements", 0) or 0),
                false_positives=int(raw.get("false_positives", 0) or 0),
                false_negatives=int(raw.get("false_negatives", 0) or 0),
                risk_flags_caught=int(raw.get("risk_flags_caught", 0) or 0),
                risk_flags_missed=int(raw.get("risk_flags_missed", 0) or 0),
                constitution_violations=int(raw.get("constitution_violations", 0) or 0),
                steve_label_samples=int(raw.get("steve_label_samples", 0) or 0),
                steve_label_agreements=int(raw.get("steve_label_agreements", 0) or 0),
                path_samples=int(raw.get("path_samples", 0) or 0),
            )
        except (TypeError, ValueError):
            return None

    def snapshot(
        self,
        *,
        limit: int | None = None,
        prefer_summary: bool = True,
    ) -> TwinModeMetricsSnapshot:
        # Prefer durable summary for read-only full-history rollups (birth status).
        # Writers (_refresh_summary) must pass prefer_summary=False to avoid stale loops.
        if limit is None and prefer_summary:
            from_summary = self._snapshot_from_summary()
            if from_summary is not None:
                return from_summary
        events = self.load_events(limit=limit)
        snap = TwinModeMetricsSnapshot()
        for row in events:
            snap.samples += 1
            agreed = bool(row.get("agreed", False))
            if agreed:
                snap.agreements += 1
            else:
                snap.disagreements += 1
            if bool(row.get("false_positive", False)):
                snap.false_positives += 1
            if bool(row.get("false_negative", False)):
                snap.false_negatives += 1
            if bool(row.get("risk_flag_caught", False)):
                snap.risk_flags_caught += 1
            if bool(row.get("risk_flag_missed", False)):
                snap.risk_flags_missed += 1
            if bool(row.get("constitution_violation", False)):
                snap.constitution_violations += 1
            src = str(row.get("source", "") or "")
            if src == "steve_label":
                snap.steve_label_samples += 1
                if agreed:
                    snap.steve_label_agreements += 1
            elif src in ("shadow_path", "promotion_path", "constitution"):
                snap.path_samples += 1
        return snap

    def metrics_dict(self, *, limit: int | None = None) -> dict[str, Any]:
        snap = self.snapshot(limit=limit)
        d = snap.to_dict()
        d["metrics_path"] = str(self.path)
        d["summary_path"] = str(self.summary_path)
        return d

    def promotion_audit_tail(self, *, limit: int = 20) -> list[dict[str, Any]]:
        path = self.audit_path
        if not path.exists():
            return []
        try:
            lines = path.read_text(encoding="utf-8").strip().splitlines()
        except OSError:
            return []
        if limit > 0:
            lines = lines[-int(limit) :]
        out: list[dict[str, Any]] = []
        for raw in lines:
            raw = raw.strip()
            if not raw:
                continue
            try:
                row = json.loads(raw)
            except json.JSONDecodeError:
                continue
            if isinstance(row, dict):
                out.append(row)
        return out

    def _write_summary_snapshot(self, snap: TwinModeMetricsSnapshot) -> None:
        payload = {
            "timestamp": _utcnow(),
            **snap.to_dict(),
        }
        self.summary_path.parent.mkdir(parents=True, exist_ok=True)
        self.summary_path.write_text(
            json.dumps(payload, indent=2, sort_keys=True),
            encoding="utf-8",
        )

    def _apply_event_to_summary(self, event_row: dict[str, Any]) -> None:
        """Increment durable summary counters from one append event (O(1))."""
        row = recompute_row_derived(event_row)
        snap = self._snapshot_from_summary() or TwinModeMetricsSnapshot()
        snap.samples += 1
        agreed = bool(row.get("agreed", False))
        if agreed:
            snap.agreements += 1
        else:
            snap.disagreements += 1
        if bool(row.get("false_positive", False)):
            snap.false_positives += 1
        if bool(row.get("false_negative", False)):
            snap.false_negatives += 1
        if bool(row.get("risk_flag_caught", False)):
            snap.risk_flags_caught += 1
        if bool(row.get("risk_flag_missed", False)):
            snap.risk_flags_missed += 1
        if bool(row.get("constitution_violation", False)):
            snap.constitution_violations += 1
        src = str(row.get("source", "") or "")
        if src == "steve_label":
            snap.steve_label_samples += 1
            if agreed:
                snap.steve_label_agreements += 1
        elif src in ("shadow_path", "promotion_path", "constitution"):
            snap.path_samples += 1
        self._write_summary_snapshot(snap)

    def _refresh_summary(self) -> None:
        # Full recompute from JSONL — only as fallback when incremental apply fails.
        # Never prefer an older summary (would freeze counters).
        snap = self.snapshot(prefer_summary=False)
        self._write_summary_snapshot(snap)


# Public re-export not already imported at top
from lumina_core.evolution.twin_metrics_types import compute_risk_flag_missed  # noqa: E402,F401

__all__ = [
    "HIGH_CONF_THRESHOLD",
    "TwinComparisonEvent",
    "TwinMetricsStore",
    "TwinModeMetricsSnapshot",
    "compute_risk_flag_missed",
    "recompute_row_derived",
]

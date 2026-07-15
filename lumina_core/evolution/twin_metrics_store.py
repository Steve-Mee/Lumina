"""Durable Approval Twin mode metrics: agreement, false positives, risk flags caught.

Fail-closed, append-only JSONL. Used by TwinModePromotionGate and CLI/API surfaces.
Never influences capital paths directly — observability + promotion evidence only.
"""

from __future__ import annotations

import json
import time
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any, Literal

from lumina_core.config_loader import ConfigLoader

ComparisonSource = Literal["steve_label", "shadow_path", "promotion_path", "constitution"]

_DEFAULT_PATH = Path("state/monitoring_twin_mode_metrics.jsonl")
_DEFAULT_SUMMARY_PATH = Path("state/twin_mode_metrics_summary.json")


def _utcnow() -> str:
    return time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())


def _resolve_paths() -> tuple[Path, Path]:
    cfg = ConfigLoader.section("evolution", "approval_twin", default={}) or {}
    if not isinstance(cfg, dict):
        cfg = {}
    promo = cfg.get("mode_promotion") if isinstance(cfg.get("mode_promotion"), dict) else {}
    metrics_path = Path(
        str(promo.get("metrics_path") or cfg.get("metrics_path") or _DEFAULT_PATH)
    )
    summary_path = Path(
        str(promo.get("metrics_summary_path") or cfg.get("metrics_summary_path") or _DEFAULT_SUMMARY_PATH)
    )
    return metrics_path, summary_path


@dataclass(slots=True)
class TwinComparisonEvent:
    """One twin vs ground-truth comparison for agreement / FP / FN accounting."""

    twin_recommendation: bool
    ground_truth_approve: bool
    source: ComparisonSource
    risk_flags: list[str] = field(default_factory=list)
    dna_hash: str = ""
    mode: str = "shadow"
    constitution_fatal: bool = False
    timestamp: str = ""

    def __post_init__(self) -> None:
        if not self.timestamp:
            self.timestamp = _utcnow()

    @property
    def agreed(self) -> bool:
        return bool(self.twin_recommendation) == bool(self.ground_truth_approve)

    @property
    def false_positive(self) -> bool:
        """Dangerous: twin APPROVE while ground truth is VETO/reject."""
        return bool(self.twin_recommendation) and not bool(self.ground_truth_approve)

    @property
    def false_negative(self) -> bool:
        """Conservative: twin VETO while ground truth is APPROVE."""
        return (not bool(self.twin_recommendation)) and bool(self.ground_truth_approve)

    @property
    def risk_flag_caught(self) -> bool:
        """Twin raised risk flags and ground truth also rejected."""
        return bool(self.risk_flags) and not bool(self.ground_truth_approve)

    @property
    def constitution_violation(self) -> bool:
        """Twin approved while constitution was fatal (must stay 0)."""
        return bool(self.constitution_fatal) and bool(self.twin_recommendation)

    def to_dict(self) -> dict[str, Any]:
        d = asdict(self)
        d["agreed"] = self.agreed
        d["false_positive"] = self.false_positive
        d["false_negative"] = self.false_negative
        d["risk_flag_caught"] = self.risk_flag_caught
        d["constitution_violation"] = self.constitution_violation
        return d


@dataclass(slots=True)
class TwinModeMetricsSnapshot:
    samples: int = 0
    agreements: int = 0
    disagreements: int = 0
    false_positives: int = 0
    false_negatives: int = 0
    risk_flags_caught: int = 0
    constitution_violations: int = 0
    steve_label_samples: int = 0
    path_samples: int = 0

    @property
    def agreement_pct(self) -> float:
        if self.samples <= 0:
            return 0.0
        return round((self.agreements / self.samples) * 100.0, 2)

    @property
    def false_positive_pct(self) -> float:
        if self.samples <= 0:
            return 100.0  # fail-closed: unknown → treat as worst
        return round((self.false_positives / self.samples) * 100.0, 2)

    @property
    def false_negative_pct(self) -> float:
        if self.samples <= 0:
            return 0.0
        return round((self.false_negatives / self.samples) * 100.0, 2)

    @property
    def risk_flags_caught_pct(self) -> float:
        # Among path rejects (or all samples with risk flags + reject)
        if self.samples <= 0:
            return 0.0
        return round((self.risk_flags_caught / self.samples) * 100.0, 2)

    @property
    def constitution_adherence_pct(self) -> float:
        """100% if zero twin-approve-on-fatal; else lower."""
        if self.constitution_violations > 0:
            # Any violation breaks adherence for promotion purposes.
            return 0.0
        return 100.0 if self.samples > 0 else 0.0

    def to_dict(self) -> dict[str, Any]:
        return {
            "samples": int(self.samples),
            "agreements": int(self.agreements),
            "disagreements": int(self.disagreements),
            "false_positives": int(self.false_positives),
            "false_negatives": int(self.false_negatives),
            "risk_flags_caught": int(self.risk_flags_caught),
            "constitution_violations": int(self.constitution_violations),
            "steve_label_samples": int(self.steve_label_samples),
            "path_samples": int(self.path_samples),
            "agreement_pct": self.agreement_pct,
            "false_positive_pct": self.false_positive_pct,
            "false_negative_pct": self.false_negative_pct,
            "risk_flags_caught_pct": self.risk_flags_caught_pct,
            "constitution_adherence_pct": self.constitution_adherence_pct,
        }


class TwinMetricsStore:
    """Append-only store for twin mode promotion evidence."""

    def __init__(
        self,
        *,
        path: Path | str | None = None,
        summary_path: Path | str | None = None,
    ) -> None:
        default_path, default_summary = _resolve_paths()
        self.path = Path(path) if path is not None else default_path
        self.summary_path = Path(summary_path) if summary_path is not None else default_summary

    def record(self, event: TwinComparisonEvent) -> TwinComparisonEvent:
        payload = event.to_dict()
        self.path.parent.mkdir(parents=True, exist_ok=True)
        with self.path.open("a", encoding="utf-8") as fh:
            fh.write(json.dumps(payload, sort_keys=True) + "\n")
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
    ) -> TwinComparisonEvent:
        event = TwinComparisonEvent(
            twin_recommendation=bool(twin_recommendation),
            ground_truth_approve=bool(ground_truth_approve),
            source=source,
            risk_flags=list(risk_flags or []),
            dna_hash=str(dna_hash or "")[:64],
            mode=str(mode or "shadow"),
            constitution_fatal=bool(constitution_fatal),
        )
        return self.record(event)

    def load_events(self, *, limit: int | None = None) -> list[dict[str, Any]]:
        if not self.path.exists():
            return []
        try:
            lines = self.path.read_text(encoding="utf-8").strip().splitlines()
        except OSError:
            return []
        if limit is not None and limit > 0:
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

    def snapshot(self, *, limit: int | None = None) -> TwinModeMetricsSnapshot:
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
            if bool(row.get("constitution_violation", False)):
                snap.constitution_violations += 1
            src = str(row.get("source", "") or "")
            if src == "steve_label":
                snap.steve_label_samples += 1
            elif src in ("shadow_path", "promotion_path", "constitution"):
                snap.path_samples += 1
        return snap

    def metrics_dict(self, *, limit: int | None = None) -> dict[str, Any]:
        snap = self.snapshot(limit=limit)
        d = snap.to_dict()
        d["metrics_path"] = str(self.path)
        d["summary_path"] = str(self.summary_path)
        return d

    def _refresh_summary(self) -> None:
        snap = self.snapshot()
        payload = {
            "timestamp": _utcnow(),
            **snap.to_dict(),
        }
        self.summary_path.parent.mkdir(parents=True, exist_ok=True)
        self.summary_path.write_text(
            json.dumps(payload, indent=2, sort_keys=True),
            encoding="utf-8",
        )

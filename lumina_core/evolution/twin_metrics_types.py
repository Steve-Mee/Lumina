"""Durable Approval Twin mode metrics: agreement, false positives, risk flags caught/missed.

Fail-closed, append-only JSONL. Used by TwinModePromotionGate and CLI/API surfaces.
Never influences capital paths directly — observability + promotion evidence only.

Rollups (agreement over time, confidence calibration, mode promotion progress) live in
``twin_metrics_reports`` (rollups) + ``twin_metrics_store`` (I/O).
"""

from __future__ import annotations

import time
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any, Literal

from lumina_core.config_loader import ConfigLoader

ComparisonSource = Literal["steve_label", "shadow_path", "promotion_path", "constitution"]

_DEFAULT_PATH = Path("state/monitoring_twin_mode_metrics.jsonl")
_DEFAULT_SUMMARY_PATH = Path("state/twin_mode_metrics_summary.json")
_DEFAULT_AUDIT_PATH = Path("state/twin_mode_promotion_audit.jsonl")

# Align with birth/autonomy high-conf band (organism_autonomy: conf >= 0.80).
HIGH_CONF_THRESHOLD = 0.80


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


def _resolve_audit_path() -> Path:
    cfg = ConfigLoader.section("evolution", "approval_twin", default={}) or {}
    if not isinstance(cfg, dict):
        cfg = {}
    promo = cfg.get("mode_promotion") if isinstance(cfg.get("mode_promotion"), dict) else {}
    return Path(str(promo.get("audit_path") or _DEFAULT_AUDIT_PATH))


def _clamp01(value: float | None) -> float | None:
    if value is None:
        return None
    try:
        v = float(value)
    except (TypeError, ValueError):
        return None
    if v != v:  # NaN
        return None
    return max(0.0, min(1.0, v))


def compute_risk_flag_missed(
    *,
    twin_recommendation: bool,
    ground_truth_approve: bool,
    risk_flags: list[str],
    constitution_fatal: bool = False,
) -> bool:
    """True when twin failed to surface risk that ground truth rejected.

    Cases:
    - Ground truth rejects (or constitution fatal) and twin raised no risk flags
    - Ground truth rejects and twin still recommended approve (missed veto opportunity)
    """
    gt_reject = (not bool(ground_truth_approve)) or bool(constitution_fatal)
    if not gt_reject:
        return False
    flags = list(risk_flags or [])
    if not flags:
        return True
    # Twin approved despite risk flags / reject ground truth
    if bool(twin_recommendation) and not bool(ground_truth_approve):
        return True
    return False


def _tail_text_lines(path: Path, max_lines: int, *, max_bytes: int = 16_000_000) -> list[str]:
    """Return the last ``max_lines`` text lines without loading the whole file.

    Used for large append-only JSONL observability files (tens of MB). Prefer this
    over ``read_text().splitlines()`` whenever a row limit is known.
    """
    if max_lines <= 0:
        return []
    try:
        size = path.stat().st_size
    except OSError:
        return []
    if size <= 0:
        return []
    try:
        with path.open("rb") as fh:
            block = 64 * 1024
            data = b""
            pos = size
            # Need max_lines full lines → at least max_lines newlines (plus possible partial first).
            need_newlines = max_lines + 1
            while pos > 0 and data.count(b"\n") < need_newlines:
                read_size = min(block, pos)
                pos -= read_size
                fh.seek(pos)
                data = fh.read(read_size) + data
                if len(data) >= max_bytes:
                    break
        text = data.decode("utf-8", errors="replace")
        lines = text.splitlines()
        # If we did not start at byte 0, the first element may be a partial line.
        if pos > 0 and lines:
            lines = lines[1:]
        if len(lines) > max_lines:
            lines = lines[-max_lines:]
        return lines
    except OSError:
        return []


def recompute_row_derived(row: dict[str, Any]) -> dict[str, Any]:
    """Fill derived fields for legacy rows missing risk_flag_missed / agreed, etc."""
    out = dict(row)
    twin_rec = bool(out.get("twin_recommendation", False))
    gt = bool(out.get("ground_truth_approve", False))
    flags_raw = out.get("risk_flags") or []
    flags = [str(f) for f in flags_raw] if isinstance(flags_raw, list) else []
    constitution_fatal = bool(out.get("constitution_fatal", False))

    if "agreed" not in out:
        out["agreed"] = twin_rec == gt
    if "false_positive" not in out:
        out["false_positive"] = twin_rec and not gt
    if "false_negative" not in out:
        out["false_negative"] = (not twin_rec) and gt
    if "risk_flag_caught" not in out:
        out["risk_flag_caught"] = bool(flags) and not gt
    if "risk_flag_missed" not in out:
        out["risk_flag_missed"] = compute_risk_flag_missed(
            twin_recommendation=twin_rec,
            ground_truth_approve=gt,
            risk_flags=flags,
            constitution_fatal=constitution_fatal,
        )
    if "constitution_violation" not in out:
        out["constitution_violation"] = constitution_fatal and twin_rec
    return out


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
    twin_confidence: float | None = None
    steve_label: str = ""
    timestamp: str = ""

    def __post_init__(self) -> None:
        if not self.timestamp:
            self.timestamp = _utcnow()
        conf = _clamp01(self.twin_confidence)
        object.__setattr__(self, "twin_confidence", conf)

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
    def risk_flag_missed(self) -> bool:
        return compute_risk_flag_missed(
            twin_recommendation=bool(self.twin_recommendation),
            ground_truth_approve=bool(self.ground_truth_approve),
            risk_flags=list(self.risk_flags or []),
            constitution_fatal=bool(self.constitution_fatal),
        )

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
        d["risk_flag_missed"] = self.risk_flag_missed
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
    risk_flags_missed: int = 0
    constitution_violations: int = 0
    steve_label_samples: int = 0
    steve_label_agreements: int = 0
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
        if self.samples <= 0:
            return 0.0
        return round((self.risk_flags_caught / self.samples) * 100.0, 2)

    @property
    def risk_flags_missed_pct(self) -> float:
        if self.samples <= 0:
            return 0.0
        return round((self.risk_flags_missed / self.samples) * 100.0, 2)

    @property
    def risk_flags_catch_rate_pct(self) -> float:
        """caught / (caught + missed); 0 when no risk opportunities observed."""
        denom = int(self.risk_flags_caught) + int(self.risk_flags_missed)
        if denom <= 0:
            return 0.0
        return round((self.risk_flags_caught / denom) * 100.0, 2)

    @property
    def steve_label_agreement_pct(self) -> float:
        if self.steve_label_samples <= 0:
            return 0.0
        return round((self.steve_label_agreements / self.steve_label_samples) * 100.0, 2)

    @property
    def constitution_adherence_pct(self) -> float:
        """100% if zero twin-approve-on-fatal; else lower."""
        if self.constitution_violations > 0:
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
            "risk_flags_missed": int(self.risk_flags_missed),
            "constitution_violations": int(self.constitution_violations),
            "steve_label_samples": int(self.steve_label_samples),
            "steve_label_agreements": int(self.steve_label_agreements),
            "path_samples": int(self.path_samples),
            "agreement_pct": self.agreement_pct,
            "false_positive_pct": self.false_positive_pct,
            "false_negative_pct": self.false_negative_pct,
            "risk_flags_caught_pct": self.risk_flags_caught_pct,
            "risk_flags_missed_pct": self.risk_flags_missed_pct,
            "risk_flags_catch_rate_pct": self.risk_flags_catch_rate_pct,
            "steve_label_agreement_pct": self.steve_label_agreement_pct,
            "constitution_adherence_pct": self.constitution_adherence_pct,
        }


# Import mixin after shared types/helpers so reports can import them without cycle.



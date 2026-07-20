"""Durable Approval Twin mode metrics: agreement, false positives, risk flags caught/missed.

Fail-closed, append-only JSONL. Used by TwinModePromotionGate and CLI/API surfaces.
Never influences capital paths directly — observability + promotion evidence only.

Rollups (agreement over time, confidence calibration, mode promotion progress) are
derived from the same append-only evidence so Twin remains auditable as a first-class citizen.
"""

from __future__ import annotations

import json
import time
from collections import defaultdict
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

_CALIB_BUCKET_KEYS = ("lt_50", "b50_60", "b60_80", "gte_80")


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


def _period_key(timestamp: str, *, bucket: str) -> str:
    """Extract period key from ISO-ish timestamp. Fail-soft → 'unknown'."""
    ts = str(timestamp or "").strip()
    if not ts:
        return "unknown"
    # Accept YYYY-MM-DDTHH:MM:SSZ or with offsets; take prefix.
    if bucket == "hour":
        # YYYY-MM-DDTHH
        if len(ts) >= 13 and ts[10] in ("T", " "):
            return ts[:13]
        return ts[:10] if len(ts) >= 10 else "unknown"
    # day default
    return ts[:10] if len(ts) >= 10 else "unknown"


def _calib_bucket_key(conf: float) -> str:
    if conf < 0.50:
        return "lt_50"
    if conf < 0.60:
        return "b50_60"
    if conf < HIGH_CONF_THRESHOLD:
        return "b60_80"
    return "gte_80"


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


class TwinMetricsStore:
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
                out.append(recompute_row_derived(row))
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

    def rolling_agreement(
        self,
        *,
        window_sizes: tuple[int, ...] = (20, 50, 100),
        limit: int = 500,
    ) -> dict[str, Any]:
        """Latest rolling agreement percentages for common windows."""
        events = self.load_events(limit=max(1, int(limit)))
        out: dict[str, Any] = {}
        for w in window_sizes:
            w_int = max(1, int(w))
            key = f"w{w_int}"
            window = events[-w_int:] if events else []
            if not window:
                out[key] = None
                continue
            agrees = sum(1 for r in window if bool(r.get("agreed", False)))
            out[key] = round((agrees / len(window)) * 100.0, 2)
            out[f"{key}_n"] = len(window)
        return out

    def agreement_over_time(
        self,
        *,
        bucket: Literal["day", "hour"] = "day",
        limit: int = 30,
        event_limit: int = 2000,
    ) -> list[dict[str, Any]]:
        """Bucketed agreement rate over time (oldest → newest, capped)."""
        events = self.load_events(limit=max(1, int(event_limit)))
        buckets: dict[str, dict[str, int]] = defaultdict(
            lambda: {"samples": 0, "agreements": 0, "false_positives": 0}
        )
        order: list[str] = []
        for row in events:
            key = _period_key(str(row.get("timestamp") or ""), bucket=bucket)
            if key not in buckets or buckets[key]["samples"] == 0:
                if key not in order:
                    order.append(key)
            b = buckets[key]
            b["samples"] += 1
            if bool(row.get("agreed", False)):
                b["agreements"] += 1
            if bool(row.get("false_positive", False)):
                b["false_positives"] += 1

        series: list[dict[str, Any]] = []
        for period in order:
            b = buckets[period]
            n = max(0, int(b["samples"]))
            if n <= 0:
                continue
            series.append(
                {
                    "period": period,
                    "samples": n,
                    "agreement_pct": round((b["agreements"] / n) * 100.0, 2),
                    "false_positive_pct": round((b["false_positives"] / n) * 100.0, 2),
                }
            )
        if limit > 0 and len(series) > int(limit):
            series = series[-int(limit) :]
        return series

    def calibration_report(self, *, limit: int | None = 500) -> dict[str, Any]:
        """Confidence reliability by bucket for rows with twin_confidence.

        Buckets align with confidence_distribution in TwinTrainingService.
        high_conf_agreement_pct uses conf >= 0.80 vs ground truth.
        """
        events = self.load_events(limit=limit)
        bucket_stats: dict[str, dict[str, float]] = {
            k: {"n": 0, "agreements": 0, "twin_approves": 0, "gt_approves": 0, "sum_conf": 0.0}
            for k in _CALIB_BUCKET_KEYS
        }
        high_n = 0
        high_agree = 0
        scored_n = 0

        for row in events:
            conf = _clamp01(row.get("twin_confidence"))
            if conf is None:
                # Fallback: if missing, skip for calibration (honest).
                continue
            scored_n += 1
            key = _calib_bucket_key(conf)
            st = bucket_stats[key]
            st["n"] += 1
            st["sum_conf"] += conf
            twin_rec = bool(row.get("twin_recommendation", False))
            gt = bool(row.get("ground_truth_approve", False))
            if twin_rec:
                st["twin_approves"] += 1
            if gt:
                st["gt_approves"] += 1
            if bool(row.get("agreed", twin_rec == gt)):
                st["agreements"] += 1
            if conf >= HIGH_CONF_THRESHOLD:
                high_n += 1
                if bool(row.get("agreed", twin_rec == gt)):
                    high_agree += 1

        buckets_out: dict[str, Any] = {}
        total_n = 0
        weighted_err = 0.0
        for key in _CALIB_BUCKET_KEYS:
            st = bucket_stats[key]
            n = int(st["n"])
            total_n += n
            if n <= 0:
                buckets_out[key] = {
                    "n": 0,
                    "mean_conf": None,
                    "agreement_rate": None,
                    "twin_approve_rate": None,
                    "gt_approve_rate": None,
                }
                continue
            mean_conf = st["sum_conf"] / n
            agreement_rate = st["agreements"] / n
            twin_approve_rate = st["twin_approves"] / n
            gt_approve_rate = st["gt_approves"] / n
            # Calibration error: |mean confidence − empirical agreement|
            weighted_err += n * abs(mean_conf - agreement_rate)
            buckets_out[key] = {
                "n": n,
                "mean_conf": round(mean_conf, 4),
                "agreement_rate": round(agreement_rate, 4),
                "twin_approve_rate": round(twin_approve_rate, 4),
                "gt_approve_rate": round(gt_approve_rate, 4),
            }

        mean_abs_error = round(weighted_err / total_n, 4) if total_n > 0 else None
        high_conf_agreement_pct = (
            round((high_agree / high_n) * 100.0, 2) if high_n > 0 else None
        )

        return {
            "scored_samples": scored_n,
            "buckets": buckets_out,
            "high_conf_threshold": HIGH_CONF_THRESHOLD,
            "high_conf_samples": high_n,
            "high_conf_agreement_pct": high_conf_agreement_pct,
            "mean_abs_calibration_error": mean_abs_error,
        }

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

    def mode_promotion_progress(
        self,
        *,
        current_mode: str = "shadow",
        snap: TwinModeMetricsSnapshot | None = None,
    ) -> dict[str, Any]:
        """Progress toward assisted / full_auto gate thresholds (read-only).

        Does not call TwinModePromotionGate.evaluate (no audit writes) — pure observability.
        """
        from lumina_core.evolution.twin_mode_promotion_gate import (
            TwinModePromotionGate,
            authority_for_mode,
            canonicalize_twin_mode,
        )

        mode = canonicalize_twin_mode(current_mode)
        snapshot = snap or self.snapshot()
        # Thresholds only — construct gate for config snapshot, never evaluate.
        gate = TwinModePromotionGate()
        cfg = gate._config_snapshot()  # noqa: SLF001 — intentional read of thresholds
        require_constitution_100 = bool(cfg.get("require_constitution_adherence_100", True))
        mode_rank = {"shadow": 0, "assisted": 1, "full_auto": 2}

        def _target_progress(target: str) -> dict[str, Any]:
            min_samples = int(
                cfg["min_samples_full_auto"]
                if target == "full_auto"
                else cfg["min_samples_assisted"]
            )
            min_agree = float(
                cfg["min_agreement_pct_full_auto"]
                if target == "full_auto"
                else cfg["min_agreement_pct_assisted"]
            )
            max_fp = float(
                cfg["max_false_positive_pct_full_auto"]
                if target == "full_auto"
                else cfg["max_false_positive_pct_assisted"]
            )
            min_caught = int(
                cfg["min_risk_flags_caught_full_auto"]
                if target == "full_auto"
                else cfg["min_risk_flags_caught_assisted"]
            )
            samples = int(snapshot.samples)
            agreement = float(snapshot.agreement_pct)
            fp = float(snapshot.false_positive_pct if snapshot.samples > 0 else 100.0)
            caught = int(snapshot.risk_flags_caught)
            constitution_pct = float(snapshot.constitution_adherence_pct)
            constitution_violations = int(snapshot.constitution_violations)

            fail_reasons: list[str] = []
            cur_r = mode_rank.get(mode, 0)
            tgt_r = mode_rank.get(target, 0)
            # Allow demotion/same; one-step upgrade only (mirrors gate)
            if tgt_r > cur_r + 1:
                fail_reasons.append("mode_order")
            if samples < min_samples:
                fail_reasons.append("sample_size")
            if agreement < min_agree:
                fail_reasons.append("agreement")
            if fp > max_fp:
                fail_reasons.append("false_positive")
            if require_constitution_100 and (
                constitution_violations > 0 or constitution_pct < 100.0
            ):
                # No samples → adherence 0 → fail-closed until evidence exists
                if samples <= 0 or constitution_violations > 0 or constitution_pct < 100.0:
                    fail_reasons.append("constitution_adherence")
            if caught < min_caught:
                fail_reasons.append("risk_flags_caught")

            ready = len(fail_reasons) == 0
            return {
                "target": target,
                "ready": ready,
                "fail_reasons": fail_reasons,
                "reason": "ok" if ready else "criteria_failed:" + ",".join(fail_reasons),
                "samples": {
                    "current": samples,
                    "required": min_samples,
                    "ratio": round(min(1.0, samples / max(1, min_samples)), 4),
                },
                "agreement": {
                    "current": agreement,
                    "required": min_agree,
                    "ratio": round(min(1.0, agreement / max(0.01, min_agree)), 4),
                },
                "false_positive": {
                    "current": fp,
                    "max_allowed": max_fp,
                    "ratio": round(
                        max(0.0, min(1.0, 1.0 - (fp / max(0.01, max_fp)))),
                        4,
                    )
                    if snapshot.samples > 0
                    else 0.0,
                },
                "risk_flags_caught": {
                    "current": caught,
                    "required": min_caught,
                    "ratio": round(min(1.0, caught / max(1, min_caught)), 4)
                    if min_caught > 0
                    else 1.0,
                },
                "constitution_adherence_pct": constitution_pct,
            }

        return {
            "current_mode": mode,
            "authority": authority_for_mode(mode),
            "thresholds": cfg,
            "progress": {
                "assisted": _target_progress("assisted"),
                "full_auto": _target_progress("full_auto"),
            },
            "recent_promotions": self.promotion_audit_tail(limit=10),
        }

    def observability_bundle(
        self,
        *,
        current_mode: str = "shadow",
        series_limit: int = 30,
        decision_limit: int | None = 500,
    ) -> dict[str, Any]:
        """Full observability payload used by API / birth / CLI."""
        snap = self.snapshot(limit=decision_limit)
        durable = snap.to_dict()
        durable["metrics_path"] = str(self.path)
        durable["summary_path"] = str(self.summary_path)
        return {
            "durable_metrics": durable,
            "rolling_agreement": self.rolling_agreement(limit=decision_limit or 500),
            "agreement_over_time": self.agreement_over_time(
                bucket="day",
                limit=max(1, int(series_limit)),
                event_limit=decision_limit or 2000,
            ),
            "calibration": self.calibration_report(limit=decision_limit),
            "mode_promotion_progress": self.mode_promotion_progress(
                current_mode=current_mode,
                snap=snap,
            ),
            "promotion_audit_tail": self.promotion_audit_tail(limit=10),
        }

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

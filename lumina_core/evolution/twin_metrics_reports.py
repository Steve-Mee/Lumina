"""Twin metrics rollups: calibration, rolling agreement, promotion progress.

Extracted from TwinMetricsStore (Wave B2 PR-C1). Mixin methods expect a store
host with load_events / snapshot / path / summary_path / promotion_audit_tail.
"""

from __future__ import annotations

from collections import defaultdict
from typing import TYPE_CHECKING, Any, Literal

from lumina_core.evolution.twin_metrics_store import HIGH_CONF_THRESHOLD, _clamp01

if TYPE_CHECKING:
    from lumina_core.evolution.twin_metrics_store import TwinModeMetricsSnapshot

_CALIB_BUCKET_KEYS = ("lt_50", "b50_60", "b60_80", "gte_80")


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


class TwinMetricsReportsMixin:
    """Calibration / rolling / promotion-progress rollups for TwinMetricsStore."""

    def rolling_agreement(
        self,
        *,
        window_sizes: tuple[int, ...] = (20, 50, 100),
        limit: int = 500,
    ) -> dict[str, Any]:
        """Latest rolling agreement percentages for common windows."""
        events = self.load_events(limit=max(1, int(limit)))  # type: ignore[attr-defined]
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
        events = self.load_events(limit=max(1, int(event_limit)))  # type: ignore[attr-defined]
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
        events = self.load_events(limit=limit)  # type: ignore[attr-defined]
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
        snapshot = snap or self.snapshot()  # type: ignore[attr-defined]
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
            "recent_promotions": self.promotion_audit_tail(limit=10),  # type: ignore[attr-defined]
        }

    def observability_bundle(
        self,
        *,
        current_mode: str = "shadow",
        series_limit: int = 30,
        decision_limit: int | None = 500,
    ) -> dict[str, Any]:
        """Full observability payload used by API / birth / CLI."""
        snap = self.snapshot(limit=decision_limit)  # type: ignore[attr-defined]
        durable = snap.to_dict()
        durable["metrics_path"] = str(self.path)  # type: ignore[attr-defined]
        durable["summary_path"] = str(self.summary_path)  # type: ignore[attr-defined]
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
            "promotion_audit_tail": self.promotion_audit_tail(limit=10),  # type: ignore[attr-defined]
        }

"""Unit tests for TwinMetricsStore observability rollups."""

from __future__ import annotations

import json
from pathlib import Path

from lumina_core.evolution.twin_metrics_store import (
    TwinMetricsStore,
    compute_risk_flag_missed,
    recompute_row_derived,
)


def _store(tmp_path: Path) -> TwinMetricsStore:
    return TwinMetricsStore(
        path=tmp_path / "metrics.jsonl",
        summary_path=tmp_path / "summary.json",
        audit_path=tmp_path / "audit.jsonl",
    )


def test_risk_flag_missed_cases() -> None:
    # GT reject, no flags → missed
    assert compute_risk_flag_missed(
        twin_recommendation=False,
        ground_truth_approve=False,
        risk_flags=[],
    )
    # GT reject, twin flags → not missed (caught path)
    assert not compute_risk_flag_missed(
        twin_recommendation=False,
        ground_truth_approve=False,
        risk_flags=["risk_shadow_blocked"],
    )
    # GT reject, twin approve with flags → missed (approved despite risk)
    assert compute_risk_flag_missed(
        twin_recommendation=True,
        ground_truth_approve=False,
        risk_flags=["x"],
    )
    # GT approve → not missed
    assert not compute_risk_flag_missed(
        twin_recommendation=True,
        ground_truth_approve=True,
        risk_flags=[],
    )


def test_snapshot_caught_and_missed(tmp_path: Path) -> None:
    store = _store(tmp_path)
    store.record_comparison(
        twin_recommendation=False,
        ground_truth_approve=False,
        source="shadow_path",
        risk_flags=["risk_shadow_blocked"],
        twin_confidence=0.4,
    )  # caught
    store.record_comparison(
        twin_recommendation=True,
        ground_truth_approve=False,
        source="steve_label",
        risk_flags=[],
        twin_confidence=0.9,
    )  # missed + FP
    store.record_comparison(
        twin_recommendation=True,
        ground_truth_approve=True,
        source="steve_label",
        risk_flags=[],
        twin_confidence=0.85,
    )  # agree
    snap = store.snapshot()
    assert snap.samples == 3
    assert snap.risk_flags_caught == 1
    assert snap.risk_flags_missed == 1
    assert snap.false_positives == 1
    assert snap.agreements == 2
    assert snap.steve_label_samples == 2
    assert snap.steve_label_agreements == 1
    assert snap.risk_flags_catch_rate_pct == 50.0
    d = snap.to_dict()
    assert "risk_flags_missed" in d
    assert "steve_label_agreement_pct" in d


def test_snapshot_prefers_summary_over_full_jsonl(tmp_path: Path) -> None:
    """Birth status must not re-scan multi-10MB JSONL when a durable summary exists."""
    store = _store(tmp_path)
    metrics_path = tmp_path / "metrics.jsonl"
    # Large-ish synthetic history (not full 80MB — enough to prove summary short-circuit).
    with metrics_path.open("w", encoding="utf-8") as fh:
        for i in range(500):
            fh.write(
                json.dumps(
                    {
                        "twin_recommendation": True,
                        "ground_truth_approve": True,
                        "agreed": True,
                        "source": "shadow_path",
                        "risk_flags": [],
                    }
                )
                + "\n"
            )
    summary = {
        "samples": 187469,
        "agreements": 187442,
        "disagreements": 27,
        "false_positives": 0,
        "false_negatives": 27,
        "risk_flags_caught": 187430,
        "risk_flags_missed": 11,
        "constitution_violations": 0,
        "steve_label_samples": 1,
        "steve_label_agreements": 1,
        "path_samples": 187468,
    }
    (tmp_path / "summary.json").write_text(json.dumps(summary), encoding="utf-8")
    snap = store.snapshot()
    assert snap.samples == 187469
    assert snap.risk_flags_caught == 187430
    # Bounded tail still works and does not require summary.
    window = store.load_events(limit=10)
    assert len(window) == 10


def test_legacy_row_recompute_missed() -> None:
    row = recompute_row_derived(
        {
            "twin_recommendation": True,
            "ground_truth_approve": False,
            "risk_flags": [],
            "source": "steve_label",
        }
    )
    assert row["risk_flag_missed"] is True
    assert row["false_positive"] is True
    assert row["agreed"] is False


def test_rolling_agreement_and_series(tmp_path: Path) -> None:
    store = _store(tmp_path)
    for i in range(10):
        store.record_comparison(
            twin_recommendation=True,
            ground_truth_approve=True,
            source="steve_label",
            twin_confidence=0.82,
            dna_hash=f"a{i}",
        )
    for i in range(5):
        store.record_comparison(
            twin_recommendation=True,
            ground_truth_approve=False,
            source="steve_label",
            twin_confidence=0.9,
            dna_hash=f"b{i}",
        )
    rolling = store.rolling_agreement(window_sizes=(5, 20), limit=50)
    assert rolling["w5"] is not None
    # last 5 are all FPs → 0% agreement
    assert rolling["w5"] == 0.0
    assert rolling["w20_n"] == 15
    series = store.agreement_over_time(bucket="day", limit=10)
    assert len(series) >= 1
    assert "agreement_pct" in series[-1]
    assert series[-1]["samples"] == 15


def test_calibration_report(tmp_path: Path) -> None:
    store = _store(tmp_path)
    # High conf correct
    for i in range(4):
        store.record_comparison(
            twin_recommendation=True,
            ground_truth_approve=True,
            source="steve_label",
            twin_confidence=0.9,
            dna_hash=f"h{i}",
        )
    # High conf wrong
    store.record_comparison(
        twin_recommendation=True,
        ground_truth_approve=False,
        source="steve_label",
        twin_confidence=0.88,
        dna_hash="bad",
    )
    # Low conf
    store.record_comparison(
        twin_recommendation=False,
        ground_truth_approve=False,
        source="steve_label",
        twin_confidence=0.3,
        dna_hash="low",
    )
    # Legacy without confidence — ignored for calib
    store.record_comparison(
        twin_recommendation=True,
        ground_truth_approve=True,
        source="steve_label",
        twin_confidence=None,
        dna_hash="legacy",
    )
    report = store.calibration_report()
    assert report["scored_samples"] == 6
    assert report["high_conf_samples"] == 5
    assert report["high_conf_agreement_pct"] == 80.0
    assert report["mean_abs_calibration_error"] is not None
    assert report["buckets"]["gte_80"]["n"] == 5
    assert report["buckets"]["lt_50"]["n"] == 1


def test_mode_promotion_progress_read_only(tmp_path: Path) -> None:
    store = _store(tmp_path)
    for i in range(35):
        store.record_comparison(
            twin_recommendation=True,
            ground_truth_approve=True,
            source="steve_label",
            twin_confidence=0.85,
            dna_hash=f"ok{i}",
        )
    store.record_comparison(
        twin_recommendation=False,
        ground_truth_approve=False,
        source="shadow_path",
        risk_flags=["risk_shadow_blocked"],
        twin_confidence=0.4,
        dna_hash="risk1",
    )
    progress = store.mode_promotion_progress(current_mode="shadow")
    assert progress["current_mode"] == "shadow"
    assert "progress" in progress
    assisted = progress["progress"]["assisted"]
    assert "samples" in assisted
    assert assisted["samples"]["current"] == 36
    assert "ratio" in assisted["samples"]
    # Must not write audit on progress reads
    assert not store.audit_path.exists() or store.audit_path.read_text(encoding="utf-8").strip() == ""


def test_observability_bundle(tmp_path: Path) -> None:
    store = _store(tmp_path)
    store.record_comparison(
        twin_recommendation=True,
        ground_truth_approve=True,
        source="steve_label",
        twin_confidence=0.8,
    )
    bundle = store.observability_bundle(current_mode="shadow", series_limit=5)
    assert "durable_metrics" in bundle
    assert "rolling_agreement" in bundle
    assert "agreement_over_time" in bundle
    assert "calibration" in bundle
    assert "mode_promotion_progress" in bundle
    assert bundle["durable_metrics"]["samples"] == 1


def test_metrics_jsonl_persists_confidence_and_missed(tmp_path: Path) -> None:
    store = _store(tmp_path)
    store.record_comparison(
        twin_recommendation=True,
        ground_truth_approve=False,
        source="steve_label",
        risk_flags=[],
        twin_confidence=0.77,
        steve_label="VETO",
    )
    raw = store.path.read_text(encoding="utf-8").strip().splitlines()
    row = json.loads(raw[0])
    assert row["twin_confidence"] == 0.77
    assert row["risk_flag_missed"] is True
    assert row["steve_label"] == "VETO"

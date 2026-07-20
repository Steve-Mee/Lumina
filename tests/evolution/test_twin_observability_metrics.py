"""Tests for Approval Twin observability rollups (confidence distribution, etc.)."""

from __future__ import annotations

import json
from pathlib import Path

from lumina_core.evolution.approval_twin_agent import ApprovalTwinAgent
from lumina_core.evolution.steve_values_registry import SteveValuesRegistry
from lumina_core.evolution.twin_metrics_store import TwinMetricsStore
from lumina_core.evolution.twin_training_service import (
    TwinTrainingService,
    compute_confidence_distribution,
    compute_decision_outcome_counts,
    compute_risk_flag_counts,
)


def test_compute_confidence_distribution_buckets() -> None:
    rows = [
        {"score": 0.40},
        {"score": 0.55},
        {"score": 0.70},
        {"score": 0.85},
        {"score": 0.90},
        {"confidence": 0.10},  # score alias
        {"score": "bad"},  # ignored
        {},  # ignored
    ]
    dist = compute_confidence_distribution(rows)
    assert dist["n"] == 6
    assert dist["lt_50"] == 2  # 0.40 + 0.10
    assert dist["b50_60"] == 1
    assert dist["b60_80"] == 1
    assert dist["gte_80"] == 2


def test_compute_outcome_and_risk_flag_counts() -> None:
    rows = [
        {"outcome": "auto_approved", "risk_flags": []},
        {"outcome": "veto", "risk_flags": ["constitution_fatal_violation", "drawdown"]},
        {"outcome": "deferred", "risk_flags": ["constitution_fatal_violation"]},
        {"outcome": "weird", "risk_flags": []},
    ]
    outcomes = compute_decision_outcome_counts(rows)
    assert outcomes["auto_approved"] == 1
    assert outcomes["veto"] == 1
    assert outcomes["deferred"] == 1
    assert outcomes["other"] == 1
    flags = compute_risk_flag_counts(rows, top_n=5)
    assert flags["constitution_fatal_violation"] == 2
    assert flags["drawdown"] == 1


def test_metrics_includes_confidence_distribution(tmp_path: Path) -> None:
    decisions = tmp_path / "monitoring_twin_decisions.jsonl"
    training = tmp_path / "monitoring_twin_training.jsonl"
    model = tmp_path / "approval_twin_model.json"
    lines = [
        json.dumps(
            {
                "dna_hash": "a",
                "score": 0.45,
                "recommendation": False,
                "risk_flags": ["x"],
                "outcome": "veto",
            }
        ),
        json.dumps(
            {
                "dna_hash": "b",
                "score": 0.88,
                "recommendation": True,
                "risk_flags": [],
                "outcome": "deferred",
            }
        ),
    ]
    decisions.write_text("\n".join(lines) + "\n", encoding="utf-8")
    registry = SteveValuesRegistry(
        sqlite_path=tmp_path / "steve.sqlite3",
        jsonl_path=tmp_path / "steve.jsonl",
    )
    twin = ApprovalTwinAgent(registry=registry, model_path=model, mode="shadow")
    svc = TwinTrainingService(
        registry=registry,
        twin=twin,
        model_path=model,
        decisions_path=decisions,
        training_path=training,
    )
    m = svc.metrics(decision_window=50)
    assert m["decisions_total"] == 2
    conf = m["confidence_distribution"]
    assert conf["n"] == 2
    assert conf["lt_50"] == 1
    assert conf["gte_80"] == 1
    assert m["outcome_counts"]["veto"] == 1
    assert m["outcome_counts"]["deferred"] == 1
    assert m["risk_flag_top"]["x"] == 1
    assert m["mode"] == "shadow"
    # First-class observability keys present even with empty durable store
    assert "rolling_agreement" in m
    assert "agreement_over_time" in m
    assert "calibration" in m
    assert "mode_promotion_progress" in m
    assert "risk_flags_missed" in m
    assert "risk_flags_catch_rate_pct" in m


def test_metrics_includes_durable_risk_and_calibration(tmp_path: Path) -> None:
    decisions = tmp_path / "monitoring_twin_decisions.jsonl"
    training = tmp_path / "monitoring_twin_training.jsonl"
    model = tmp_path / "approval_twin_model.json"
    decisions.write_text("", encoding="utf-8")
    metrics_path = tmp_path / "mode_metrics.jsonl"
    store = TwinMetricsStore(
        path=metrics_path,
        summary_path=tmp_path / "summary.json",
        audit_path=tmp_path / "audit.jsonl",
    )
    store.record_comparison(
        twin_recommendation=True,
        ground_truth_approve=True,
        source="steve_label",
        twin_confidence=0.9,
        dna_hash="ok1",
    )
    store.record_comparison(
        twin_recommendation=True,
        ground_truth_approve=False,
        source="steve_label",
        risk_flags=[],
        twin_confidence=0.85,
        dna_hash="miss1",
    )
    registry = SteveValuesRegistry(
        sqlite_path=tmp_path / "steve.sqlite3",
        jsonl_path=tmp_path / "steve.jsonl",
    )
    twin = ApprovalTwinAgent(
        registry=registry,
        model_path=model,
        mode="shadow",
        metrics_store=store,
    )
    svc = TwinTrainingService(
        registry=registry,
        twin=twin,
        model_path=model,
        decisions_path=decisions,
        training_path=training,
    )
    m = svc.metrics(decision_window=50)
    assert m["risk_flags_missed"] == 1
    assert m["risk_flags_caught"] == 0
    assert m.get("rolling_agreement", {}).get("w20") is not None
    calib = m.get("calibration") or {}
    assert calib.get("scored_samples", 0) >= 2
    assert calib.get("high_conf_agreement_pct") is not None
    progress = m.get("mode_promotion_progress") or {}
    assert "progress" in progress

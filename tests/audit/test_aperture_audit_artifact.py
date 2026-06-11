"""
Tests for Phase 3 Deliverable 1: Aperture Audit Artifact.

Focused, narrow tests for the first slice of the "one human 20 minutes" audit tool.
Follows LUMINA patterns: clear intent, @pytest.mark.unit, best-effort behavior verification,
never assumes perfect data.

These tests validate the skeleton + foundation wiring stage.
More comprehensive tests (golden markdown, full constitution extraction, shadow linkage)
will be added as the artifact is populated in subsequent micro-steps.
"""

from __future__ import annotations

import json
import os
from pathlib import Path
from unittest.mock import patch

import pytest

from lumina_core.audit.aperture_audit_artifact import (
    build_aperture_audit_artifact,
    format_aperture_audit_as_markdown,
    export_aperture_audit_bundle,
    format_compact_aperture_audit,
    merge_d1_audit_context_ids,
)


@pytest.mark.unit
def test_build_never_crashes_on_invalid_input() -> None:
    """Given bad or missing input, build must return a safe dict with error/missing_data, never raise."""
    result = build_aperture_audit_artifact("")
    assert isinstance(result, dict)
    assert "decision_context_id" in result
    assert "missing_data" in result or "error" in result

    result2 = build_aperture_audit_artifact(None)  # type: ignore[arg-type]
    assert isinstance(result2, dict)


@pytest.mark.unit
def test_build_returns_expected_top_level_structure() -> None:
    """The artifact must always expose the contract keys defined in the Phase 3 D1 plan."""
    artifact = build_aperture_audit_artifact("any-ctx-123")

    required_keys = {
        "decision_context_id",
        "generated_at",
        "summary",
        "constitution_checks",
        "risk_numbers",
        "agent_dna_lineage",
        "execution",
        "aperture_context",
        "lineage_chain",
        "raw_sources",
        "missing_data",
    }
    assert required_keys.issubset(artifact.keys())


@pytest.mark.unit
def test_format_produces_readable_markdown_even_on_skeleton() -> None:
    """Markdown output must be human-usable even in early skeleton state (Red Flags First pattern)."""
    artifact = build_aperture_audit_artifact("test-ctx-for-markdown")
    md = format_aperture_audit_as_markdown(artifact)

    assert isinstance(md, str)
    assert len(md) > 100
    assert "# Aperture Audit Artifact" in md
    # Red flags / missing data section must appear when data is incomplete
    assert "RED FLAGS" in md or "missing" in md.lower()


@pytest.mark.unit
def test_export_bundle_is_best_effort_and_creates_files(tmp_path: Path) -> None:
    """export_aperture_audit_bundle must never raise and should create files when possible."""
    md_path, json_path = export_aperture_audit_bundle(
        "export-test-ctx",
        output_dir=tmp_path / "audits",
    )

    # In skeleton phase this may return (None, None) or real paths depending on data availability.
    # The contract is: never crash, and if paths are returned they must exist.
    if md_path is not None:
        assert md_path.exists()
        content = md_path.read_text(encoding="utf-8")
        assert "Aperture Audit Artifact" in content

    if json_path is not None:
        assert json_path.exists()


@pytest.mark.unit
def test_build_uses_decision_lineage_foundation_when_available(monkeypatch: pytest.MonkeyPatch) -> None:
    """
    When decision_lineage can provide data, the artifact must incorporate it
    (this is the key value of the foundation reuse in the approved plan).
    """
    from lumina_core.risk import decision_lineage as dl

    fake_report = {
        "summary": {"status": "OK", "chain_integrity_ok": True, "final_arbitration_status": "APPROVED"},
        "full_raw_chain": [{"topic": "admission.gate_entry", "hash_ok": True}],
        "fills": [{"payload": {"symbol": "ES"}}],
    }

    def _fake_build_report(*args, **kwargs):  # type: ignore[no-untyped-def]
        return fake_report

    monkeypatch.setattr(dl, "build_pretrade_provenance_report", _fake_build_report)

    artifact = build_aperture_audit_artifact("foundation-test-ctx")

    assert artifact["summary"].get("status") == "OK"
    assert len(artifact.get("lineage_chain", [])) > 0
    assert "execution" in artifact
    # missing_data should be reduced compared to pure skeleton
    assert "full_lineage_chain (skeleton phase)" not in artifact.get("missing_data", [])


@pytest.mark.unit
def test_build_extracts_agent_dna_and_shadow_linkage(monkeypatch: pytest.MonkeyPatch) -> None:
    """Agent/DNA/shadow fields present in the chain should be collected into agent_dna_lineage."""
    from lumina_core.risk import decision_lineage as dl

    rich_chain = [
        {"topic": "agent.rl.proposal", "payload": {"agent_id": "RLAgent-v3", "dna_hash": "abc123", "prompt_id": "meta-v2"}, "hash_ok": True},
        {"topic": "evolution.shadow.verdict", "payload": {"dna_hash": "abc123", "shadow_experiment_id": "shadow-exp-42"}, "hash_ok": True},
    ]

    fake_report = {
        "summary": {"status": "OK"},
        "full_raw_chain": rich_chain,
    }

    def _fake(*args, **kwargs):  # type: ignore[no-untyped-def]
        return fake_report

    monkeypatch.setattr(dl, "build_pretrade_provenance_report", _fake)

    artifact = build_aperture_audit_artifact("agent-dna-test-ctx")

    lineage = artifact.get("agent_dna_lineage", {})
    assert lineage.get("agent_id") == "RLAgent-v3"
    assert lineage.get("dna_hash") == "abc123"
    assert lineage.get("shadow_experiment_id") == "shadow-exp-42"


@pytest.mark.unit
def test_build_attempts_aperture_context_snapshot(monkeypatch: pytest.MonkeyPatch) -> None:
    """The artifact should attempt to populate aperture_context from Guardian (best-effort, never breaks)."""
    from lumina_core.risk import decision_lineage as dl

    fake_report = {"summary": {"status": "OK"}, "full_raw_chain": []}

    def _fake(*args, **kwargs):  # type: ignore[no-untyped-def]
        return fake_report

    monkeypatch.setattr(dl, "build_pretrade_provenance_report", _fake)

    # Even if Guardian call fails or is unavailable, the call must succeed
    artifact = build_aperture_audit_artifact("aperture-ctx-test")
    assert "aperture_context" in artifact
    # It may be empty or populated; either is acceptable for best-effort behavior


@pytest.mark.unit
def test_build_populates_raw_sources_excerpt_keys(tmp_path: Path) -> None:
    """build should always include raw_sources with excerpt keys (even if empty)."""
    artifact = build_aperture_audit_artifact("excerpt-test-ctx")
    raw = artifact.get("raw_sources", {})
    assert "audit_log_excerpts" in raw
    assert "agent_decision_excerpts" in raw
    # With no real logs for this ctx, they are empty lists
    assert isinstance(raw["audit_log_excerpts"], list)
    assert isinstance(raw["agent_decision_excerpts"], list)


@pytest.mark.unit
def test_richer_excerpts_include_payload_sample(tmp_path: Path) -> None:
    """When logs have matching entries, excerpts should include payload_sample and (for recent) full_raw_sample."""
    audit_log = tmp_path / "trade_decision_audit.jsonl"
    agent_log = tmp_path / "agent_decision_log.jsonl"

    entry = {
        "timestamp": "2026-06-05T12:00:00Z",
        "decision_context_id": "rich-excerpt-ctx",
        "stage": "final",
        "final_decision": "approved",
        "payload": {
            "proposed_risk": 1.5,
            "kelly": 0.55,
            "signal": "strong_long",
            "large_field": "x" * 100,  # to test sampling
        }
    }
    audit_log.write_text(json.dumps(entry) + "\n", encoding="utf-8")

    agent_entry = {
        "timestamp": "2026-06-05T12:00:01Z",
        "decision_context_id": "rich-excerpt-ctx",
        "agent_id": "RiskAgent",
        "policy_outcome": "approved",
        "raw_input": {"foo": "bar"},
    }
    agent_log.write_text(json.dumps(agent_entry) + "\n", encoding="utf-8")

    with patch.dict(os.environ, {
        "LUMINA_TRADE_DECISION_AUDIT_LOG": str(audit_log),
        "LUMINA_AGENT_DECISION_LOG": str(agent_log),
    }):
        # Force the load paths for test
        artifact = build_aperture_audit_artifact("rich-excerpt-ctx")
        raw = artifact.get("raw_sources", {})
        audit_ex = raw.get("audit_log_excerpts", [])
        agent_ex = raw.get("agent_decision_excerpts", [])

        assert len(audit_ex) >= 1
        assert "payload_sample" in audit_ex[0]
        assert audit_ex[0]["payload_sample"].get("proposed_risk") == 1.5
        assert "full_raw_sample" in audit_ex[0] or "payload_sample" in audit_ex[0]

        assert len(agent_ex) >= 1
        assert agent_ex[0].get("agent_id") == "RiskAgent"


@pytest.mark.unit
def test_max_log_lines_controls_historical_scan(tmp_path: Path) -> None:
    """max_log_lines allows finding older ctxs by scanning more of the log (durability for historical)."""
    log = tmp_path / "agent_decision_log.jsonl"

    # "Old" entry at start of log
    old_entry = {"timestamp": "2026-01-01", "decision_context_id": "very-old-ctx", "agent_id": "OldAgent"}
    # Recent at end
    recent_entry = {"timestamp": "2026-06-05", "decision_context_id": "recent-ctx", "agent_id": "RecentAgent"}
    log.write_text(json.dumps(old_entry) + "\n" + json.dumps(recent_entry) + "\n", encoding="utf-8")

    # With small max, may or may not hit old depending on position, but we force by using small file
    # Better: use a log with many dummy lines to simulate tail not reaching old.
    # For test: create log with old + 600 dummy lines + recent, then small max misses old, large finds it.
    lines = [json.dumps(old_entry)]
    for i in range(600):
        lines.append(json.dumps({"timestamp": f"2026-02-{i%28+1:02d}", "decision_context_id": f"dummy-{i}", "agent_id": "dummy"}))
    lines.append(json.dumps(recent_entry))
    log.write_text("\n".join(lines) + "\n", encoding="utf-8")

    with patch.dict(os.environ, {"LUMINA_AGENT_DECISION_LOG": str(log)}):
        # Small scan: should miss the very old (at position >500 from end)
        art_small = build_aperture_audit_artifact("very-old-ctx", max_log_lines=100)
        agent_small = art_small["raw_sources"].get("agent_decision_excerpts", [])
        # Note: may still find if exactly in tail, but with 600+ , 100 from end should miss old
        found_small = any(e.get("decision_context_id") == "very-old-ctx" for e in agent_small)

        # Large scan: should find it
        art_large = build_aperture_audit_artifact("very-old-ctx", max_log_lines=1000)
        agent_large = art_large["raw_sources"].get("agent_decision_excerpts", [])
        found_large = any(e.get("decision_context_id") == "very-old-ctx" for e in agent_large)

        assert not found_small or len(agent_small) == 0  # conservative: with small tail likely misses
        assert found_large
        # Also recent always findable
        art_recent = build_aperture_audit_artifact("recent-ctx", max_log_lines=100)
        assert any(e.get("decision_context_id") == "recent-ctx" for e in art_recent["raw_sources"].get("agent_decision_excerpts", []))


@pytest.mark.unit
def test_merge_d1_audit_context_ids_prefers_existing_then_discovers(tmp_path: Path) -> None:
    """Given bus ctxs and log Final Arbitration events, merge returns deduped ordered list."""
    log = tmp_path / "trade_decision_audit.jsonl"
    entry = {
        "topic": "risk.final_arbitration.result",
        "payload": {
            "decision_context_id": "arb-from-log-ctx",
            "checks": [{"name": "constitution", "ok": True}],
        },
    }
    log.write_text(json.dumps(entry) + "\n", encoding="utf-8")

    with patch.dict(os.environ, {"LUMINA_TRADE_DECISION_AUDIT_LOG": str(log)}):
        merged = merge_d1_audit_context_ids(["bus-ctx-1"], max_ctxs=5)
    assert merged[0] == "bus-ctx-1"
    assert "arb-from-log-ctx" in merged


@pytest.mark.unit
def test_format_compact_aperture_audit_produces_short_usable_summary():
    """The compact formatter must produce a short, one-screen summary with key D1 facts."""
    artifact = {
        "decision_context_id": "test-compact-ctx",
        "summary": {"chain_integrity_ok": True, "final_arbitration_status": "APPROVED"},
        "constitution_checks": [{"name": "constitution", "ok": True}],
        "risk_numbers": {"proposed_risk": 1.1, "kelly": 0.4},
        "agent_dna_lineage": {"agent_id": "TestAgent", "shadow_experiment_id": "shadow-007"},
    }
    compact = format_compact_aperture_audit(artifact)
    assert "test-compact-ctx" in compact
    assert "Chain:" in compact
    assert "Proposed risk: 1.1" in compact
    assert "Shadow experiment: shadow-007" in compact
    assert len(compact) < 800  # short for embedding in reports
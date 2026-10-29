"""Forged or unsigned PromotionCandidates never become SignalIntents."""

from __future__ import annotations

from pathlib import Path

import pytest

from lumina_core.agent_orchestration.schemas_research import PromotionCandidate
from lumina_research.agents.provenance import ProvenanceAuthority
from tests.research_bridge.helpers import make_runtime, sealed_candidate, unsigned_candidate_fields


@pytest.mark.unit
def test_forged_mac_is_refused(tmp_path: Path) -> None:
    _bus, authority, runtime, alerts, observe = make_runtime(tmp_path, healthy=True)
    good = sealed_candidate(authority)
    forged = good.model_copy(update={"quantity": 2.0})
    intent = runtime.on_candidate(forged)
    assert intent is None
    assert runtime.issued_intents() == ()
    assert runtime.issued_fills() == ()
    assert observe.calls == []
    assert any(item["code"] == "unsigned_or_forged_candidate" for item in alerts.records)


@pytest.mark.unit
def test_foreign_authority_is_refused(tmp_path: Path) -> None:
    _bus, _authority, runtime, alerts, _observe = make_runtime(tmp_path, healthy=True)
    other = ProvenanceAuthority()
    stranger = sealed_candidate(other)
    intent = runtime.on_candidate(stranger)
    assert intent is None
    assert runtime.issued_intents() == ()
    assert any(item["code"] == "unsigned_or_forged_candidate" for item in alerts.records)


@pytest.mark.unit
def test_unsigned_payload_is_refused(tmp_path: Path) -> None:
    _bus, _authority, runtime, alerts, _observe = make_runtime(tmp_path, healthy=True)
    unsigned = unsigned_candidate_fields()
    candidate = PromotionCandidate.model_validate({**unsigned, "issue_mac": "c" * 64})
    intent = runtime.on_candidate(candidate)
    assert intent is None
    assert runtime.issued_intents() == ()
    assert any(item["code"] == "unsigned_or_forged_candidate" for item in alerts.records)

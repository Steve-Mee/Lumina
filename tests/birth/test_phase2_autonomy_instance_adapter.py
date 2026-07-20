"""In-process instance adapt proposal tests."""

from __future__ import annotations

import pytest

from lumina_core.birth.phase2_autonomy.instance_adapter import (
    materialize_instance_adapt_payload,
    propose_instance_adapt,
    validate_instance_proposal,
)
from lumina_core.birth.phase2_autonomy.contracts import Phase2InstanceAdaptProposal


@pytest.mark.unit
def test_plateau_path_at_high_tier() -> None:
    prop = propose_instance_adapt(adaptation_tier=2, retries_this_stage=2, plateau_active=False)
    assert prop.action == "spawn_plateau"
    assert prop.spawn_plateau is True
    assert prop.risk_touching is False
    assert validate_instance_proposal(prop) == []


@pytest.mark.unit
def test_phoenix_path() -> None:
    prop = propose_instance_adapt(
        adaptation_tier=3,
        phoenix_eligible=True,
        learning_health="declining",
        stall_reason="plateau_evolution_exhausted",
        plateau_active=True,
    )
    assert prop.action in {"spawn_phoenix_reset", "refresh_handler_cfg", "noop", "spawn_plateau"}
    assert prop.risk_touching is False


@pytest.mark.unit
def test_noop_when_healthy() -> None:
    prop = propose_instance_adapt(adaptation_tier=0, retries_this_stage=0, learning_health="improving")
    assert prop.action == "noop"


@pytest.mark.unit
def test_materialize_never_os_spawn() -> None:
    prop = propose_instance_adapt(adaptation_tier=2)
    payload = materialize_instance_adapt_payload(prop)
    assert payload["process_restart_required"] is False
    assert payload["os_spawn"] is False


@pytest.mark.unit
def test_validate_rejects_broker_action() -> None:
    prop = Phase2InstanceAdaptProposal(action="broker_reconnect")
    violations = validate_instance_proposal(prop)
    assert violations

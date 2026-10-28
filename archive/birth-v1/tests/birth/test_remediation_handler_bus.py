"""RemediationHandler EventBus integration tests."""

from __future__ import annotations

import pytest

from lumina_core.agent_orchestration.event_bus import EventBus
from lumina_core.agent_orchestration.schemas import BirthCertificateRemediationRequested
from lumina_core.birth.birth_handler_registry import BirthHandlerRegistry
from lumina_core.birth.config import BirthCurriculumConfig, BirthRewardConfig


@pytest.mark.unit
def test_certificate_remediation_requested_via_handler() -> None:
    bus = EventBus()
    cfg = BirthCurriculumConfig()
    reward = BirthRewardConfig()
    registry = BirthHandlerRegistry(bus, cfg, reward)
    registry.attach_all()

    bus.publish(
        topic="birth.certificate.remediation.requested",
        producer="test",
        payload=BirthCertificateRemediationRequested(
            progress_snapshot={"phase": "certificate_failed", "remediation_attempt": 0},
            checkpoint_state={"phase": "certificate_failed"},
            fast_path_eligible=False,
        ).model_dump(mode="json"),
    )
    latest = bus.latest("birth.certificate.remediation.requested")
    assert latest is not None
    assert latest.producer == "birth.remediation_handler"

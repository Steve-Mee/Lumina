"""Certificate remediation fast-path eligibility (EventBus or local)."""
from __future__ import annotations

from typing import Any

from lumina_core.birth.remediation import should_fast_path_remediation_from_state


def certificate_fast_path_eligible(
    host: Any,
    progress_snapshot: dict[str, Any],
    checkpoint_state: dict[str, Any],
) -> bool:
    """Gate certificate fast-path via EventBus when available."""
    bus = getattr(host, "event_bus", None)
    if bus is None:
        return should_fast_path_remediation_from_state(progress_snapshot, checkpoint_state)
    from lumina_core.agent_orchestration.schemas import BirthCertificateRemediationRequested

    request = BirthCertificateRemediationRequested(
        progress_snapshot=dict(progress_snapshot),
        checkpoint_state=dict(checkpoint_state),
        fast_path_eligible=False,
    )
    bus.publish(
        topic="birth.certificate.remediation.requested",
        producer="birth.birth_phase_orchestrator",
        payload=request.model_dump(mode="json"),
    )
    latest = bus.latest("birth.certificate.remediation.requested")
    if latest is not None and latest.producer == "birth.remediation_handler":
        return bool(latest.payload.get("fast_path_eligible", False))
    return should_fast_path_remediation_from_state(progress_snapshot, checkpoint_state)

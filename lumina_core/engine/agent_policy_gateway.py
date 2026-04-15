from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any

from pydantic import BaseModel, Field


class DecisionLineageSchema(BaseModel):
    model_identifier: str
    prompt_version: str
    prompt_hash: str
    policy_version: str
    provider_route: list[str]
    calibration_factor: float = Field(gt=0.0)


class DecisionEnvelopeSchema(BaseModel):
    signal: str
    confidence: float = Field(ge=0.0, le=1.0)
    confluence_score: float = Field(ge=0.0, le=1.0)
    min_confluence: float = Field(ge=0.0, le=1.0)
    hold_until_ts: float
    mode: str
    session_allowed: bool
    risk_allowed: bool
    lineage: DecisionLineageSchema
    reason: str | None = None
    context: dict[str, Any] = Field(default_factory=dict)


class PolicyDecisionSchema(BaseModel):
    approved: bool
    signal: str
    reason_code: str
    confidence: float = Field(ge=0.0, le=1.0)
    policy_version: str
    lineage: DecisionLineageSchema


@dataclass(slots=True)
class AgentPolicyGateway:
    policy_version: str = "agent-policy-gateway-v1"

    def evaluate(self, envelope: dict[str, Any]) -> dict[str, Any]:
        validated = DecisionEnvelopeSchema.model_validate(envelope)
        normalized_signal = str(validated.signal).upper().strip()
        now_ts = datetime.now(timezone.utc).timestamp()

        approved = True
        reason_code = "accepted"

        if validated.mode not in {"paper", "sim", "sim_real_guard", "real"}:
            approved = False
            reason_code = "invalid_mode"
            normalized_signal = "HOLD"
        elif normalized_signal not in {"BUY", "SELL", "HOLD"}:
            approved = False
            reason_code = "invalid_signal"
            normalized_signal = "HOLD"
        elif validated.hold_until_ts > now_ts:
            approved = False
            reason_code = "hold_window_active"
            normalized_signal = "HOLD"
        elif normalized_signal in {"BUY", "SELL"} and validated.mode in {"sim", "sim_real_guard", "real"} and not validated.session_allowed:
            approved = False
            reason_code = "session_blocked"
            normalized_signal = "HOLD"
        elif normalized_signal in {"BUY", "SELL"} and validated.mode in {"sim", "sim_real_guard", "real"} and not validated.risk_allowed:
            approved = False
            reason_code = "risk_blocked"
            normalized_signal = "HOLD"
        elif normalized_signal in {"BUY", "SELL"} and validated.confluence_score < validated.min_confluence:
            approved = False
            reason_code = "below_min_confluence"
            normalized_signal = "HOLD"

        out = PolicyDecisionSchema.model_validate(
            {
                "approved": approved,
                "signal": normalized_signal,
                "reason_code": reason_code,
                "confidence": float(validated.confidence if approved else 0.0),
                "policy_version": self.policy_version,
                "lineage": validated.lineage.model_dump(mode="json"),
            }
        )
        return out.model_dump(mode="json")


def default_lineage(
    *,
    model_identifier: str,
    prompt_version: str,
    prompt_hash: str,
    provider_route: list[str] | None = None,
    policy_version: str = "agent-policy-gateway-v1",
    calibration_factor: float = 1.0,
) -> dict[str, Any]:
    return DecisionLineageSchema.model_validate(
        {
            "model_identifier": str(model_identifier or "unknown-model"),
            "prompt_version": str(prompt_version or "unknown-prompt"),
            "prompt_hash": str(prompt_hash or "unknown-hash"),
            "policy_version": str(policy_version),
            "provider_route": [str(item) for item in (provider_route or ["unknown-provider"])],
            "calibration_factor": max(0.01, float(calibration_factor or 1.0)),
        }
    ).model_dump(mode="json")

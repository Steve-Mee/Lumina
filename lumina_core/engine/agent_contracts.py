from __future__ import annotations

import hashlib
import json
import threading
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable, TypeVar

from pydantic import BaseModel, Field, ValidationError

from .agent_decision_log import AgentDecisionLog
from .agent_policy_gateway import AgentPolicyGateway, default_lineage


F = TypeVar("F", bound=Callable[..., Any])

_DECISION_LOG_PATH = Path("state/thought_log.jsonl")
_DECISION_LOG_LOCK = threading.Lock()
_LAST_ENTRY_HASH = ""
_AGENT_DECISION_LOG = AgentDecisionLog(path=Path("state/agent_decision_log.jsonl"))


class AgentContractError(RuntimeError):
    pass


class ContractOutputBase(BaseModel):
    confidence: float = Field(ge=0.0, le=1.0)


class NewsInputSchema(BaseModel):
    schedule_events_count: int = Field(ge=0)
    xai_model: str
    update_interval_seconds: int = Field(ge=1)
    timestamp: str


class NewsOutputSchema(ContractOutputBase):
    sentiment_signal: str
    sentiment_score: float = Field(ge=-1.0, le=1.0)
    high_impact: bool
    high_impact_events: list[str]
    summary: str
    dynamic_multiplier: float = Field(ge=0.0)
    news_avoidance_window: bool
    news_avoidance_hold_until_ts: float
    last_update: str


class EmotionalTwinInputSchema(BaseModel):
    signal: str
    confidence: float = Field(ge=0.0, le=1.0)
    confluence_score: float = Field(ge=0.0, le=1.0)
    regime: str
    timestamp: str


class EmotionalTwinOutputSchema(ContractOutputBase):
    signal: str
    confluence_score: float = Field(ge=0.0, le=1.0)
    reason: str | None = None


class TapeReadingInputSchema(BaseModel):
    volume_delta: float
    avg_volume_delta_10: float
    bid_ask_imbalance: float
    cumulative_delta_10: float
    timestamp: str


class TapeReadingOutputSchema(ContractOutputBase):
    signal: str
    direction: str
    fast_path_trigger: bool
    reason: str


class ExecutionDecisionInputSchema(BaseModel):
    signal: str
    confluence_score: float = Field(ge=0.0, le=1.0)
    min_confluence: float = Field(ge=0.0, le=1.0)
    hold_until_ts: float
    timestamp: str


class ExecutionDecisionOutputSchema(ContractOutputBase):
    approved: bool
    signal: str
    reason: str


def _append_immutable_decision_log(payload: dict[str, Any]) -> None:
    global _LAST_ENTRY_HASH
    with _DECISION_LOG_LOCK:
        _DECISION_LOG_PATH.parent.mkdir(parents=True, exist_ok=True)
        if not _LAST_ENTRY_HASH and _DECISION_LOG_PATH.exists():
            try:
                last_line = ""
                with _DECISION_LOG_PATH.open("r", encoding="utf-8") as handle:
                    for line in handle:
                        if line.strip():
                            last_line = line
                if last_line:
                    parsed = json.loads(last_line)
                    if isinstance(parsed, dict):
                        _LAST_ENTRY_HASH = str(parsed.get("entry_hash", ""))
            except Exception:
                _LAST_ENTRY_HASH = ""

        entry = dict(payload)
        entry["prev_hash"] = _LAST_ENTRY_HASH
        encoded = json.dumps(entry, sort_keys=True, ensure_ascii=False).encode("utf-8")
        entry_hash = hashlib.sha256(encoded).hexdigest()
        entry["entry_hash"] = entry_hash
        with _DECISION_LOG_PATH.open("a", encoding="utf-8") as handle:
            handle.write(json.dumps(entry, ensure_ascii=False) + "\n")
        _LAST_ENTRY_HASH = entry_hash

    # Mirror every contract decision into the immutable agent decision log.
    try:
        full_context = payload.get("full_context", {}) if isinstance(payload.get("full_context"), dict) else {}
        raw_input = full_context.get("input", {}) if isinstance(full_context.get("input"), dict) else {}
        raw_output = full_context.get("output", {}) if isinstance(full_context.get("output"), dict) else {}
        prompt_seed = json.dumps(raw_input, sort_keys=True, ensure_ascii=True)
        _AGENT_DECISION_LOG.log_decision(
            agent_id=str(payload.get("agent", "UnknownAgent")),
            raw_input=raw_input,
            raw_output=raw_output,
            confidence=float(payload.get("confidence", 0.0) or 0.0),
            policy_outcome=str(payload.get("status", "unknown")),
            decision_context_id=str(payload.get("method", "unknown_method")),
            model_version=str(payload.get("model_hash", "unknown_model")),
            prompt_hash=hashlib.sha256(prompt_seed.encode("utf-8")).hexdigest(),
        )
    except Exception:
        pass


def enforce_contract(
    input_schema: type[BaseModel],
    output_schema: type[BaseModel],
    *,
    prompt_version: str,
    model_hash_getter: Callable[[Any], str],
    input_builder: Callable[[Any, tuple[Any, ...], dict[str, Any]], dict[str, Any]],
) -> Callable[[F], F]:
    def decorator(func: F) -> F:
        def wrapped(self, *args: Any, **kwargs: Any) -> Any:
            timestamp = datetime.now(timezone.utc).isoformat()
            try:
                input_payload = input_builder(self, args, kwargs)
                validated_input = input_schema.model_validate(input_payload)
                result = func(self, *args, **kwargs)
                validated_output = output_schema.model_validate(result)
            except ValidationError as exc:
                _append_immutable_decision_log(
                    {
                        "ts": timestamp,
                        "status": "rejected",
                        "agent": type(self).__name__,
                        "method": func.__name__,
                        "prompt_version": prompt_version,
                        "model_hash": model_hash_getter(self),
                        "confidence": 0.0,
                        "full_context": {
                            "validation_error": str(exc),
                            "input": input_builder(self, args, kwargs),
                        },
                    }
                )
                raise AgentContractError(
                    f"Contract validation failed for {type(self).__name__}.{func.__name__}: {exc}"
                ) from exc

            output_dict = dict(result) if isinstance(result, dict) else validated_output.model_dump(mode="json")
            required_output = validated_output.model_dump(mode="json")
            output_dict.update(required_output)
            _append_immutable_decision_log(
                {
                    "ts": timestamp,
                    "status": "accepted",
                    "agent": type(self).__name__,
                    "method": func.__name__,
                    "prompt_version": prompt_version,
                    "model_hash": model_hash_getter(self),
                    "confidence": float(output_dict.get("confidence", 0.0)),
                    "full_context": {
                        "input": validated_input.model_dump(mode="json"),
                        "output": output_dict,
                    },
                }
            )
            return output_dict

        return wrapped  # type: ignore[return-value]

    return decorator


def validate_execution_decision(
    *, signal: str, confluence_score: float, min_confluence: float, hold_until_ts: float
) -> dict[str, Any]:
    return apply_agent_policy_gateway(
        signal=signal,
        confluence_score=confluence_score,
        min_confluence=min_confluence,
        hold_until_ts=hold_until_ts,
        mode="paper",
        session_allowed=True,
        risk_allowed=True,
        lineage=None,
    )


def apply_agent_policy_gateway(
    *,
    signal: str,
    confluence_score: float,
    min_confluence: float,
    hold_until_ts: float,
    mode: str,
    session_allowed: bool,
    risk_allowed: bool,
    lineage: dict[str, Any] | None,
) -> dict[str, Any]:
    timestamp = datetime.now(timezone.utc).isoformat()
    validated_input = ExecutionDecisionInputSchema.model_validate(
        {
            "signal": signal,
            "confluence_score": float(confluence_score),
            "min_confluence": float(min_confluence),
            "hold_until_ts": float(hold_until_ts),
            "timestamp": timestamp,
        }
    )

    lineage_payload = lineage or default_lineage(
        model_identifier="deterministic-rule-gate",
        prompt_version="execution-gate-v1",
        prompt_hash=hashlib.sha256(
            json.dumps(validated_input.model_dump(mode="json"), sort_keys=True, ensure_ascii=True).encode("utf-8")
        ).hexdigest(),
        provider_route=["rule-engine"],
        policy_version="agent-policy-gateway-v1",
        calibration_factor=1.0,
    )

    gateway = AgentPolicyGateway(policy_version="agent-policy-gateway-v1")
    gateway_result = gateway.evaluate(
        {
            "signal": validated_input.signal,
            "confidence": 1.0,
            "confluence_score": validated_input.confluence_score,
            "min_confluence": validated_input.min_confluence,
            "hold_until_ts": validated_input.hold_until_ts,
            "mode": str(mode).strip().lower(),
            "session_allowed": bool(session_allowed),
            "risk_allowed": bool(risk_allowed),
            "lineage": lineage_payload,
            "context": {},
        }
    )

    validated_output = ExecutionDecisionOutputSchema.model_validate(
        {
            "approved": bool(gateway_result.get("approved", False)),
            "signal": str(gateway_result.get("signal", "HOLD")),
            "reason": str(gateway_result.get("reason_code", "unknown")),
            "confidence": float(gateway_result.get("confidence", 0.0) or 0.0),
        }
    )

    payload = {
        "ts": timestamp,
        "status": "accepted" if bool(validated_output.approved) else "rejected",
        "agent": "AgentPolicyGateway",
        "method": "apply_agent_policy_gateway",
        "prompt_version": "execution-gate-v1",
        "model_hash": "deterministic-rule-gate",
        "confidence": float(validated_output.confidence),
        "full_context": {
            "input": validated_input.model_dump(mode="json"),
            "output": validated_output.model_dump(mode="json"),
        },
    }
    _append_immutable_decision_log(payload)
    return validated_output.model_dump(mode="json")

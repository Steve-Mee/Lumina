"""Canonical HMAC bytes for Phase 4 continuity events and live-signal admission."""

from __future__ import annotations

import json
from typing import Mapping

from lumina_core.agent_orchestration.schemas_research import (
    CAPACITY_SCHEMA_VERSION,
    DECAY_SCHEMA_VERSION,
    DEWEIGHT_SCHEMA_VERSION,
    GUARDIAN_SCHEMA_VERSION,
    REPLENISH_SCHEMA_VERSION,
    RETIRE_SCHEMA_VERSION,
    SUSPEND_SCHEMA_VERSION,
)
from lumina_research.agents.objects import as_object_dict, as_object_list
from lumina_research.agents.provenance import ProvenanceAuthority


def canonical_admission(fields: Mapping[str, object]) -> bytes:
    body = {
        "signal_id": fields["signal_id"],
        "hypothesis_id": fields["hypothesis_id"],
        "config_id": fields["config_id"],
        "trial_id": fields["trial_id"],
        "instrument": fields["instrument"],
        "family_id": fields["family_id"],
        "cluster_id": fields["cluster_id"],
        "base_quantity": fields["base_quantity"],
        "base_price": fields["base_price"],
        "base_notional": fields["base_notional"],
        "oos_values": fields["oos_values"],
        "oos_mean": fields["oos_mean"],
        "oos_stdev": fields["oos_stdev"],
        "n_oos_windows": fields["n_oos_windows"],
        "median_oos_after_costs": fields["median_oos_after_costs"],
        "pbo": fields["pbo"],
        "dsr_probability": fields["dsr_probability"],
        "purge_applied": fields["purge_applied"],
        "embargo_applied": fields["embargo_applied"],
        "cost_applied": fields["cost_applied"],
        "cost_model_id": fields["cost_model_id"],
        "regimes_complete": fields["regimes_complete"],
        "validation_mac": fields["validation_mac"],
        "issue_mac": fields["issue_mac"],
        "report_sha256": fields["report_sha256"],
    }
    return _dumps(body)


def canonical_decay(fields: Mapping[str, object]) -> bytes:
    body: dict[str, object] = {
        "schema_version": fields.get("schema_version", DECAY_SCHEMA_VERSION),
        "signal_id": fields["signal_id"],
        "hypothesis_id": fields["hypothesis_id"],
        "config_id": fields["config_id"],
        "trial_id": fields["trial_id"],
        "agent_id": fields["agent_id"],
        "method": fields["method"],
        "statistic": fields["statistic"],
        "threshold": fields["threshold"],
        "window": fields["window"],
        "live_mean": fields["live_mean"],
        "oos_mean": fields["oos_mean"],
        "oos_stdev": fields["oos_stdev"],
        "percentile": fields["percentile"],
        "cusum": fields["cusum"],
        "sprt_llr": fields["sprt_llr"],
        "stage": fields["stage"],
    }
    if "vol_regime" in fields:
        body["vol_regime"] = fields["vol_regime"]
    if "horizon" in fields:
        body["horizon"] = fields["horizon"]
    return _dumps(body)


def canonical_deweight(fields: Mapping[str, object]) -> bytes:
    return _weight_event(fields, DEWEIGHT_SCHEMA_VERSION)


def canonical_suspend(fields: Mapping[str, object]) -> bytes:
    return _weight_event(fields, SUSPEND_SCHEMA_VERSION)


def canonical_retire(fields: Mapping[str, object]) -> bytes:
    return _weight_event(fields, RETIRE_SCHEMA_VERSION)


def canonical_capacity(fields: Mapping[str, object]) -> bytes:
    return _dumps(
        {
            "schema_version": fields.get("schema_version", CAPACITY_SCHEMA_VERSION),
            "signal_id": fields["signal_id"],
            "instrument": fields["instrument"],
            "family_id": fields["family_id"],
            "cluster_id": fields["cluster_id"],
            "agent_id": fields["agent_id"],
            "previous_scale": fields["previous_scale"],
            "new_scale": fields["new_scale"],
            "reasons": _require_sequence(fields["reasons"]),
        }
    )


def canonical_guardian(fields: Mapping[str, object]) -> bytes:
    return _dumps(
        {
            "schema_version": fields.get("schema_version", GUARDIAN_SCHEMA_VERSION),
            "finding_id": fields["finding_id"],
            "cadence": fields["cadence"],
            "check_id": fields["check_id"],
            "signal_id": fields["signal_id"],
            "agent_id": fields["agent_id"],
            "passed": fields["passed"],
            "severity": fields["severity"],
            "suspend_proposed": fields["suspend_proposed"],
            "evidence": fields["evidence"],
        }
    )


def canonical_replenish(fields: Mapping[str, object]) -> bytes:
    return _dumps(
        {
            "schema_version": fields.get("schema_version", REPLENISH_SCHEMA_VERSION),
            "request_id": fields["request_id"],
            "agent_id": fields["agent_id"],
            "reason": fields["reason"],
            "n_active": fields["n_active"],
            "floor": fields["floor"],
            "n_requested": fields["n_requested"],
        }
    )


def canonical_state(fields: Mapping[str, object]) -> bytes:
    return _dumps(
        {
            "signal_id": fields["signal_id"],
            "admission_mac": fields["admission_mac"],
            "stage": fields["stage"],
            "weight": fields["weight"],
            "capacity_scale": fields["capacity_scale"],
        }
    )


def mac_ok(authority: ProvenanceAuthority, canonical: bytes, digest: object) -> bool:
    if not isinstance(digest, str):
        return False
    return bool(authority.mac_ok(canonical, digest))


def accept_mac(
    authority: ProvenanceAuthority,
    canonical: bytes,
    digest: object,
    seen: set[str] | None = None,
) -> bool:
    if not mac_ok(authority, canonical, digest):
        return False
    if seen is None:
        return True
    if not isinstance(digest, str):
        return False
    if digest in seen:
        return False
    seen.add(digest)
    return True


def _weight_event(fields: Mapping[str, object], default_version: str) -> bytes:
    return _dumps(
        {
            "schema_version": fields.get("schema_version", default_version),
            "signal_id": fields["signal_id"],
            "hypothesis_id": fields["hypothesis_id"],
            "config_id": fields["config_id"],
            "trial_id": fields["trial_id"],
            "agent_id": fields["agent_id"],
            "previous_weight": fields["previous_weight"],
            "new_weight": fields["new_weight"],
            "reason": fields["reason"],
        }
    )


def _require_sequence(value: object) -> list[object]:
    items = as_object_list(value)
    if items is None:
        raise KeyError("reasons")
    return list(items)


def _dumps(value: object) -> bytes:
    return json.dumps(_stable(value), sort_keys=True, separators=(",", ":"), allow_nan=False).encode("utf-8")


def _stable(value: object) -> object:
    as_dict = as_object_dict(value)
    if as_dict is not None:
        return {key: _stable(as_dict[key]) for key in sorted(as_dict)}
    as_list = as_object_list(value)
    if as_list is not None:
        return [_stable(item) for item in as_list]
    return value

"""Canonical HMAC bytes for Phase 3 mutation and governance events."""

from __future__ import annotations

import hashlib
import json
from typing import Mapping

from lumina_core.agent_orchestration.schemas_research import (
    GOVERNANCE_SCHEMA_VERSION,
    MUTATION_SCHEMA_VERSION,
)
from lumina_research.agents.objects import as_object_dict, as_object_list


def canonical_mutation(fields: Mapping[str, object]) -> bytes:
    body = {
        "schema_version": fields.get("schema_version", MUTATION_SCHEMA_VERSION),
        "mutation_id": fields["mutation_id"],
        "parent_config_id": fields["parent_config_id"],
        "config_id": fields["config_id"],
        "trial_id": fields["trial_id"],
        "agent_id": fields["agent_id"],
        "kind": fields["kind"],
        "target": fields["target"],
        "seed": fields["seed"],
        "genome": fields["genome"],
        "rationale": fields["rationale"],
        "adr_path": fields.get("adr_path", ""),
        "review": fields.get("review"),
    }
    return _dumps(body)


def canonical_governance(fields: Mapping[str, object]) -> bytes:
    body = {
        "schema_version": fields.get("schema_version", GOVERNANCE_SCHEMA_VERSION),
        "mutation_id": fields["mutation_id"],
        "config_id": fields["config_id"],
        "trial_id": fields["trial_id"],
        "agent_id": fields["agent_id"],
        "kind": fields["kind"],
        "admitted": fields["admitted"],
        "recorded_for_human": fields["recorded_for_human"],
        "applied": fields["applied"],
        "reasons": _require_sequence(fields["reasons"]),
    }
    return _dumps(body)


def review_binding(*, config_id: str, kind: str, target: str) -> bytes:
    return _dumps({"config_id": config_id, "kind": kind, "target": target})


def mutation_fingerprint(
    *,
    config_id: str,
    kind: str,
    target: str,
    genome: object,
    parent_config_id: str,
) -> str:
    """Bind a TrialRegistry row to the mutation body so a stolen trial_id cannot change the genome."""
    body = {
        "config_id": config_id,
        "kind": kind,
        "target": target,
        "parent_config_id": parent_config_id,
        "genome": genome,
    }
    return hashlib.sha256(_dumps(body)).hexdigest()


def _require_sequence(value: object) -> list[object]:
    items = as_object_list(value)
    if items is None:
        raise KeyError("reasons")
    return items


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

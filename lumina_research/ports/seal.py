"""Canonical HMAC bytes for research-side Execution Fabric port events."""

from __future__ import annotations

import json
from typing import Mapping

from lumina_research.agents.objects import as_object_dict, as_object_list
from lumina_research.agents.provenance import ProvenanceAuthority


def canonical_signal(fields: Mapping[str, object]) -> bytes:
    return _dumps(
        {
            "schema_version": fields.get("schema_version", "research.signal.intent.v1"),
            "strategy_id": fields["strategy_id"],
            "direction": fields["direction"],
            "size": fields["size"],
            "timestamp": fields["timestamp"],
            "expected_horizon": fields["expected_horizon"],
            "instrument": fields["instrument"],
            "account_id": fields["account_id"],
            "mode": fields["mode"],
            "client_order_id": fields["client_order_id"],
        }
    )


def canonical_order(fields: Mapping[str, object]) -> bytes:
    return _dumps(
        {
            "schema_version": fields.get("schema_version", "research.order.intent.v1"),
            "strategy_id": fields["strategy_id"],
            "direction": fields["direction"],
            "size": fields["size"],
            "timestamp": fields["timestamp"],
            "expected_horizon": fields["expected_horizon"],
            "instrument": fields["instrument"],
            "account_id": fields["account_id"],
            "mode": fields["mode"],
            "client_order_id": fields["client_order_id"],
            "order_type": fields.get("order_type", "LIMIT"),
            "limit_price": fields.get("limit_price"),
        }
    )


def canonical_fill(fields: Mapping[str, object]) -> bytes:
    return _dumps(
        {
            "schema_version": fields.get("schema_version", "research.fill.observed.v1"),
            "strategy_id": fields["strategy_id"],
            "fill_price": fields["fill_price"],
            "qty": fields["qty"],
            "slippage": fields["slippage"],
            "commission": fields["commission"],
            "timestamp": fields["timestamp"],
            "fill_id": fields["fill_id"],
            "instrument": fields["instrument"],
            "client_order_id": fields["client_order_id"],
            "source": fields["source"],
        }
    )


def canonical_alert(fields: Mapping[str, object]) -> bytes:
    return _dumps(
        {
            "schema_version": fields.get("schema_version", "research.execution.alert.v1"),
            "alert_id": fields["alert_id"],
            "kind": fields["kind"],
            "action": fields["action"],
            "allow_new_orders": fields["allow_new_orders"],
            "flatten_recommended": fields["flatten_recommended"],
            "open_position": fields["open_position"],
            "reason": fields["reason"],
        }
    )


def accept_mac(
    authority: ProvenanceAuthority,
    canonical: bytes,
    digest: object,
    seen: set[str] | None,
) -> bool:
    if not isinstance(digest, str) or len(digest) != 64:
        return False
    if not authority.mac_ok(canonical, digest):
        return False
    if seen is None:
        return True
    if digest in seen:
        return False
    seen.add(digest)
    return True


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

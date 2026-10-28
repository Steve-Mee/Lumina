"""T0–T3 tables for genesis HOLD_COMPARE. Measure only."""

from __future__ import annotations

from typing import Any

from lumina_core.birth.data_source_honesty import real_data_percentage, synthetic_source_reasons
from lumina_core.birth.foundation_metrics import POLICY_EDGE_MIN_TRADES
from lumina_core.rl.observation_builder import OBSERVATION_DIM

HONESTY_PARAGRAPH = (
    "PR #35 G5 is GENESIS_EYES_FAIL. This PR does not convert it to EYES_OK. "
    "Floor 150 is unchanged. No second 10k. "
    "Engine 100% on certified synthetic is a lie; Gate 1 removes that lie. "
    "Source synthetic_cloud_fixture. REAL=no. Playground=no. Proof=false."
)


def table_t0_identity(
    *,
    origin_main: str,
    train_hash: str,
    newborn_sha16: str,
    child_sha16: str,
) -> dict[str, Any]:
    return {
        "origin_main": str(origin_main),
        "genesis_train_hash": str(train_hash),
        "newborn_sha16": str(newborn_sha16),
        "child_sha16": str(child_sha16),
        "OBSERVATION_DIM": int(OBSERVATION_DIM),
        "POLICY_EDGE_MIN_TRADES": int(POLICY_EDGE_MIN_TRADES),
    }


def table_t1_honesty() -> dict[str, Any]:
    syn = [{"source": "synthetic_cloud_fixture"}]
    real = [{"source": "real"}]
    reasons = synthetic_source_reasons(syn)
    return {
        "pct_synthetic_cloud_fixture": real_data_percentage(syn),
        "pct_real": real_data_percentage(real),
        "certificate_reasons_contain_synthetic_source": any(
            r.startswith("synthetic_source:") for r in reasons
        ),
        "synthetic_source_reasons": reasons,
        "min_real_data_pct": 95.0,
    }


def table_t2_leg(leg: str, payload: dict[str, Any]) -> dict[str, Any]:
    birth = dict(payload.get("birth") or {})
    child = dict(payload.get("child") or {})
    return {
        "leg": str(leg),
        "n_policy_birth": int(birth.get("n_policy") or 0),
        "n_policy_child": int(child.get("n_policy") or 0),
        "bars_held_p50_birth": birth.get("bars_held_p50"),
        "bars_held_p50_child": child.get("bars_held_p50"),
        "bars_held_p90_birth": birth.get("bars_held_p90"),
        "bars_held_p90_child": child.get("bars_held_p90"),
        "trades_per_10k_birth": payload.get("trades_per_10k_birth"),
        "trades_per_10k_child": payload.get("trades_per_10k_child"),
        "n_H_birth": int(birth.get("n_H") or 0),
        "n_H_child": int(child.get("n_H") or 0),
        "mean_r_birth": birth.get("mean_r"),
        "mean_r_child": child.get("mean_r"),
        "cause_tag": payload.get("cause"),
        "child_last_close_reason": payload.get("child_last_close_reason"),
    }


def table_t3_license(
    *,
    combined_tag: str,
    gate1_tag: str,
    gate2_tag: str,
    licensed_next: str,
) -> dict[str, Any]:
    return {
        "combined_tag": str(combined_tag),
        "gate1_tag": str(gate1_tag),
        "gate2_tag": str(gate2_tag),
        "law": "SHADOW",
        "licensed_next_family": str(licensed_next),
        "Proof": False,
        "REAL": "no",
        "GENESIS_EYES_OK": False,
        "HOLE_MOVED_A": False,
        "HOLE_MOVED_B": False,
        "honesty": HONESTY_PARAGRAPH,
    }


__all__ = [
    "HONESTY_PARAGRAPH",
    "table_t0_identity",
    "table_t1_honesty",
    "table_t2_leg",
    "table_t3_license",
]

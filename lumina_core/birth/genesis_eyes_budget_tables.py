"""T0–T3 tables for GENESIS_EYES_BUDGET. Measure only."""

from __future__ import annotations

from typing import Any

from lumina_core.birth.data_source_honesty import real_data_percentage, synthetic_source_reasons
from lumina_core.birth.foundation_metrics import POLICY_EDGE_MIN_TRADES
from lumina_core.rl.observation_builder import OBSERVATION_DIM

HONESTY_PARAGRAPH = (
    "Frozen first-life zips sit a NEW thick paper. Not a second Birth. Not a second 10k. "
    "Floor POLICY_EDGE_MIN_TRADES=150 stays. GENESIS_EYES_OK stays false. "
    "BUDGET_OK is not Evolution Proof. REAL=no. Source synthetic_cloud_fixture."
)


def table_t0_identity(
    *,
    origin_main: str,
    train_hash: str,
    birth_sha: str,
    eyes_sha: str,
) -> dict[str, Any]:
    return {
        "origin_main": str(origin_main),
        "fixture_seed": 20260905,
        "fixture_train_hash": str(train_hash),
        "student_birth_sha256": str(birth_sha),
        "student_eyes_sha256": str(eyes_sha),
        "OBSERVATION_DIM": int(OBSERVATION_DIM),
        "POLICY_EDGE_MIN_TRADES": int(POLICY_EDGE_MIN_TRADES),
        "learn_called": False,
    }


def table_t1_honesty() -> dict[str, Any]:
    syn = [{"source": "synthetic_cloud_fixture"}]
    return {
        "pct_synthetic_cloud_fixture": real_data_percentage(syn),
        "pct_real_historical": real_data_percentage([{"source": "real_historical"}]),
        "pct_real": real_data_percentage([{"source": "real"}]),
        "synthetic_source_reasons": synthetic_source_reasons(syn),
        "min_real_data_pct": 95.0,
        "G6_tag": "REAL_DOOR_LOCKED",
    }


def table_t2_leg(leg: str, payload: dict[str, Any]) -> dict[str, Any]:
    return {
        "leg": str(leg),
        "n_policy_birth": int(payload.get("n_policy_birth") or 0),
        "n_policy_child": int(payload.get("n_policy_child") or 0),
        "wr_birth": payload.get("wr_birth"),
        "wr_child": payload.get("wr_child"),
        "mean_r_birth": payload.get("mean_r_birth"),
        "mean_r_child": payload.get("mean_r_child"),
        "n_H_birth": int(payload.get("n_H_birth") or 0),
        "n_H_child": int(payload.get("n_H_child") or 0),
        "n_W_birth": int(payload.get("n_W_birth") or 0),
        "n_W_child": int(payload.get("n_W_child") or 0),
        "bars_held_p50_birth": payload.get("bars_held_p50_birth"),
        "bars_held_p50_child": payload.get("bars_held_p50_child"),
        "HOLE_MOVED": bool(payload.get("HOLE_MOVED")),
        "S_THIN": bool(payload.get("S_THIN")),
        "S_HARM": bool(payload.get("S_HARM")),
        "S_MISSING": bool(payload.get("S_MISSING")),
    }


def table_t3_license(licensed: dict[str, Any]) -> dict[str, Any]:
    return {
        "tag": str(licensed.get("tag") or ""),
        "law": str(licensed.get("law") or "NONE"),
        "licensed_next_family": str(licensed.get("licensed_next_family") or "H_NONE"),
        "HOLE_MOVED_A": bool(licensed.get("HOLE_MOVED_A")),
        "HOLE_MOVED_B": bool(licensed.get("HOLE_MOVED_B")),
        "GENESIS_EYES_OK": False,
        "Proof": False,
        "REAL": "no",
        "honesty": HONESTY_PARAGRAPH,
    }


__all__ = [
    "HONESTY_PARAGRAPH",
    "table_t0_identity",
    "table_t1_honesty",
    "table_t2_leg",
    "table_t3_license",
]

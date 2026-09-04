"""Genesis first-life ladder constants. Isolated from the old birth_cloud_run body."""

from __future__ import annotations

from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
GENESIS_ROOT = REPO_ROOT / "reports" / "genesis_cloud_run"
GENESIS_WORK = GENESIS_ROOT / "workspace"
GENESIS_ART = GENESIS_ROOT / "artifacts"

GENESIS_FIXTURE_SEED = 20260904
GENESIS_INSTRUMENT = "NQ SEP26"
GENESIS_START_PRICE = 21_150.0
GENESIS_HOLDOUT_PCT = 0.20
# Default fixture calendar (2026-06-01) + 10s/60s bars fingerprints as 7e86c2bb
# because train_hash is len+first+last timestamp, not prices. Offset +7d keeps
# 90-day density and yields a distinct tape identity for this first life.
GENESIS_START_ET_ISO = "2026-06-08T18:00:00-04:00"
FORBIDDEN_TICKS_SHA16 = "7e86c2bb1c71d514"
SOURCE_GENESIS = "genesis_cloud_ladder"
G6_TAG = "REAL_DOOR_LOCKED"
G5_BIRTH_ONLY = "GENESIS_BIRTH_ONLY"
G5_EYES_OK = "GENESIS_EYES_OK"
G5_EYES_FAIL = "GENESIS_EYES_FAIL"
G5_S_MISSING = "GENESIS_S_MISSING"
OVERALL = "GENESIS_CLOUD_LADDER SHADOW_MEASURE"
BIRTH_INCOMPLETE = "BIRTH_INCOMPLETE"
SKIP_BIRTH_INCOMPLETE = "birth_incomplete"

NEWBORN_ZIP_NAME = "genesis_birth_exit_pi_star.zip"
NEWBORN_META_NAME = "genesis_birth_exit_pi_star.json"
EYES_ZIP_NAME = "genesis_mark_eyes_pi_star.zip"
EYES_META_NAME = "genesis_mark_eyes_pi_star.json"
FLAGS_NAME = "genesis_cloud_flags.json"
OLD_ENGINE_ZIP_NAME = "birth_exit_pi_star.zip"

FORBIDDEN_PARENT_ZIP_NAMES = frozenset(
    {
        "birth_exit_pi_star.zip",
        "awakening_select_pi_star.zip",
        "awakening_hole_tax_pi_star.zip",
        "awakening_mark_eyes_pi_star.zip",
        "awakening_select_obj_bounce_pi_star.zip",
    }
)
FORBIDDEN_OLD_ARTIFACT_NAMES = frozenset(
    {
        "path_early_A_close_ledger.jsonl",
        "path_early_B_close_ledger.jsonl",
        "path_exit_k3_A_close_ledger.jsonl",
        "path_exit_k3_B_close_ledger.jsonl",
        "path_shape_k3_dead_A_close_ledger.jsonl",
        "path_shape_k3_dead_B_close_ledger.jsonl",
    }
)
OLD_PARENT_ZIPS = (
    "birth_exit_pi_star.zip",
    "awakening_select_pi_star.zip",
    "awakening_hole_tax_pi_star.zip",
    "awakening_mark_eyes_pi_star.zip",
)
STAGE_RECEIPT_FILES = (
    ("stage1_trend", "s1_receipt.json"),
    ("stage2_range", "s2_receipt.json"),
    ("stage3_mixed", "s3_receipt.json"),
    ("stage4_viable_plant", "s4_receipt.json"),
    ("stage5_probe_handoff", "s5_receipt.json"),
)
HONESTY = (
    "This run is first life. Old path_early / 8cc435c6 / 53df2d78 were not inputs.\n"
    "Tape source synthetic_cloud_fixture. real_data_pct=0.0.\n"
    "Birth exit ≠ REAL. Certificate OOS 0.48 ≠ Birth floor.\n"
    "T/DEAD/bounce families were not rerun.\n"
    "MARK_EYES init=scratch on the newborn, one 10k, hooks off.\n"
    "Evolution Proof stamped: False.\n"
    "REAL: no.\n"
    "Playground: no.\n"
    "G6 tag: REAL_DOOR_LOCKED."
)

__all__ = [
    "BIRTH_INCOMPLETE",
    "EYES_META_NAME",
    "EYES_ZIP_NAME",
    "FLAGS_NAME",
    "FORBIDDEN_OLD_ARTIFACT_NAMES",
    "FORBIDDEN_PARENT_ZIP_NAMES",
    "FORBIDDEN_TICKS_SHA16",
    "G5_BIRTH_ONLY",
    "G5_EYES_FAIL",
    "G5_EYES_OK",
    "G5_S_MISSING",
    "G6_TAG",
    "GENESIS_ART",
    "GENESIS_FIXTURE_SEED",
    "GENESIS_HOLDOUT_PCT",
    "GENESIS_INSTRUMENT",
    "GENESIS_ROOT",
    "GENESIS_START_ET_ISO",
    "GENESIS_START_PRICE",
    "GENESIS_WORK",
    "HONESTY",
    "NEWBORN_META_NAME",
    "NEWBORN_ZIP_NAME",
    "OLD_ENGINE_ZIP_NAME",
    "OLD_PARENT_ZIPS",
    "OVERALL",
    "REPO_ROOT",
    "SKIP_BIRTH_INCOMPLETE",
    "SOURCE_GENESIS",
    "STAGE_RECEIPT_FILES",
]

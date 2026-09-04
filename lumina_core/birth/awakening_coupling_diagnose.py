"""G1: generator phase × enricher regime. Pin ONE cause. No oracle stamp."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from lumina_core.birth.awakening_physics_tape import (
    PHYSICS_HOLD_PCT,
    attempt_specs,
    generate_physics_tape_ticks,
    intended_for_price,
    trend_fracs,
)
from lumina_core.birth.genesis_cloud_const import REPO_ROOT
from lumina_core.birth.purged_split import purged_train_holdout_split
from lumina_core.birth.tick_enricher import enrich_ticks_for_sim
from lumina_core.rl.trend_features import regime_from_strength

DIAGNOSE_SEED = 20260908  # diagnose seed 20260908
EXAM_SEED = 20260909  # exam seed 20260909
# cause rules order GEN_ASYM → ENR_ASYM → FLOOR_CLIP → OTHER
CAUSE_RULES_ORDER = ("GEN_ASYM", "ENR_ASYM", "FLOOR_CLIP", "OTHER")
ENR_THRESHOLD_POS = 0.15
ENR_THRESHOLD_NEG = -0.15
SOURCE = "awakening_enricher_coupling"
COUPLING_ROOT = REPO_ROOT / "reports" / "awakening_coupling_run"
COUPLING_WORK = COUPLING_ROOT / "workspace"
COUPLING_ART = COUPLING_ROOT / "artifacts"
MIN_TREND_UP_FRAC = 0.25  # 25/25 train AND holdout
MIN_TREND_DOWN_FRAC = 0.25
MIN_HOLDOUT_TICKS = 80_000
MIN_TICKS_PER_LEG = 40_000
FAMILY = "AWAKENING_MARK_EYES"
BASELINE_SHA256 = "a9ffa8529e02f2d8f8a535be4dcce205a43abe20bdec492add78126a8181188b"
BASELINE_ZIP_NAME = "baseline_a9ffa852_pi_star.zip"
CHILD_ZIP_NAME = "awakening_coupling_v1_pi_star.zip"
CHILD_META_NAME = "awakening_coupling_v1_pi_star.json"
FLAGS_NAME = "awakening_coupling_flags.json"
FORBIDDEN_TAPE_PREFIXES = ("5726ae7e", "e963d1ce", "afcea4fa", "5e7eae98", "8d1aa6f8", "7e86c2bb")


class CouplingProtocolError(RuntimeError):
    """AWAKENING_ENRICHER_COUPLING protocol crime (fail-closed)."""


def phase_label(intended: str) -> str:
    if intended == "TREND_UP":
        return "up"
    if intended == "TREND_DOWN":
        return "down"
    return "range"


def attempt2_spec() -> Any:
    spec = attempt_specs()[2]
    if int(spec.seed) != int(DIAGNOSE_SEED):
        raise CouplingProtocolError("diagnose seed must stay 20260908")
    return spec


def generate_diagnose_raw() -> tuple[list[dict[str, Any]], list[str], Any]:
    spec = attempt2_spec()
    raw = generate_physics_tape_ticks(spec)
    if any("regime" in row for row in raw):
        raise CouplingProtocolError("generator must not write tick['regime']")
    n = len(raw)
    phases = [phase_label(intended_for_price(i, n, spec.phase_blocks)) for i in range(n)]
    return raw, phases, spec


def peel_gen_phase(rows: list[dict[str, Any]]) -> tuple[list[dict[str, Any]], list[str]]:
    phases: list[str] = []
    clean: list[dict[str, Any]] = []
    for row in rows:
        item = dict(row)
        phases.append(str(item.pop("_gen_phase")))
        clean.append(item)
    return clean, phases


def split_with_phases(
    ticks: list[dict[str, Any]], phases: list[str]
) -> tuple[list[dict[str, Any]], list[str], list[dict[str, Any]], list[str]]:
    tagged = [{**t, "_gen_phase": p} for t, p in zip(ticks, phases)]
    split = purged_train_holdout_split(tagged, holdout_pct=PHYSICS_HOLD_PCT)
    train, tr_ph = peel_gen_phase(list(split.train))
    hold, ho_ph = peel_gen_phase(list(split.holdout))
    return train, tr_ph, hold, ho_ph


def _regimes(ticks: list[dict[str, Any]]) -> list[str]:
    return [str(t.get("regime") or "NEUTRAL").upper() for t in ticks]


def confusion_table(phases: list[str], regimes: list[str]) -> dict[str, Any]:
    n = max(1, len(phases))
    cells: dict[str, Any] = {}
    for gen in ("up", "down", "range"):
        for enr in ("TREND_UP", "TREND_DOWN", "NEUTRAL"):
            c = sum(1 for p, r in zip(phases, regimes) if p == gen and r == enr)
            cells[f"{gen}|{enr}"] = {"n": int(c), "frac": float(c) / float(n)}
    return {"n": len(phases), "cells": cells}


def _mean(rows: list[dict[str, Any]], key: str) -> float:
    if not rows:
        return 0.0
    return float(sum(float(r.get(key) or 0.0) for r in rows) / len(rows))


def phase_feature_means(ticks: list[dict[str, Any]], phases: list[str], phase: str) -> dict[str, Any]:
    rows = [t for t, p in zip(ticks, phases) if p == phase]
    return {
        "n": len(rows),
        "mean_signed_slope": _mean(rows, "trend_slope_15"),
        "mean_adx_14": _mean(rows, "trend_adx_14"),
        "mean_strength": _mean(rows, "trend_regime_strength"),
        "used_threshold_pos": float(ENR_THRESHOLD_POS),
        "used_threshold_neg": float(ENR_THRESHOLD_NEG),
    }


def floor_cap_counts(ticks: list[dict[str, Any]], phases: list[str]) -> dict[str, int]:
    prices = [float(t.get("last") or 0.0) for t in ticks]
    run_min = min(prices) if prices else 0.0
    run_max = max(prices) if prices else 0.0
    down_floor = sum(
        1 for t, p in zip(ticks, phases) if p == "down" and float(t.get("last") or 0.0) <= run_min * 1.005
    )
    up_cap = sum(
        1 for t, p in zip(ticks, phases) if p == "up" and float(t.get("last") or 0.0) >= run_max * 0.995
    )
    hard = sum(1 for t, p in zip(ticks, phases) if p == "down" and float(t.get("last") or 0.0) <= 1005.0)
    return {
        "down_near_floor_n": int(down_floor),
        "up_near_cap_n": int(up_cap),
        "down_hard_floor_n": int(hard),
        "run_min_x100": int(run_min * 100),
        "run_max_x100": int(run_max * 100),
    }


def pin_cause(meas: dict[str, Any]) -> str:
    """cause rules order GEN_ASYM → ENR_ASYM → FLOOR_CLIP → OTHER"""
    if abs(float(meas["drift_down_used"])) < abs(float(meas["drift_up_used"])) - 1e-6:
        return "GEN_ASYM"
    pos = float(meas["enr_threshold_pos"])
    neg = float(meas["enr_threshold_neg"])
    if abs(pos - abs(neg)) > 1e-12:
        return "ENR_ASYM"
    if -float(meas["mean_slope_emitted_down"]) > float(meas["mean_slope_emitted_up"]) + 1e-6:
        return "ENR_ASYM"
    if int(meas["down_near_floor_n"]) > int(meas["up_near_cap_n"]):
        return "FLOOR_CLIP"
    return "OTHER"


def _cause_detail(cause: str, meas: dict[str, Any]) -> str:
    if cause == "GEN_ASYM":
        return (
            f"|drift_down|={meas['drift_down_used']} used in the path < "
            f"|drift_up|={meas['drift_up_used']} - 1e-6"
        )
    if cause == "ENR_ASYM":
        return (
            f"enricher needs more extreme negative slope than positive "
            f"(emitted_up={meas['mean_slope_emitted_up']} emitted_down={meas['mean_slope_emitted_down']} "
            f"thr_pos={meas['enr_threshold_pos']} thr_neg={meas['enr_threshold_neg']})"
        )
    if cause == "FLOOR_CLIP":
        return (
            f"down phases hit floor proxy n={meas['down_near_floor_n']} more than "
            f"up hits cap n={meas['up_near_cap_n']}"
        )
    return (
        f"none of GEN_ASYM/ENR_ASYM/FLOOR_CLIP; train_up={meas.get('train_up_frac')} "
        f"train_down={meas.get('train_down_frac')} hold_up={meas.get('hold_up_frac')} "
        f"hold_down={meas.get('hold_down_frac')}"
    )


def run_g1_diagnose(*, art: Path) -> dict[str, Any]:
    raw, phases, spec = generate_diagnose_raw()
    enriched = enrich_ticks_for_sim([dict(t) for t in raw])
    if any("_gen_phase" in t for t in enriched):
        raise CouplingProtocolError("gen_phase leaked onto enriched ticks")
    train, tr_ph, hold, ho_ph = split_with_phases(enriched, phases)
    tr_reg, ho_reg = _regimes(train), _regimes(hold)
    train_up, train_down = trend_fracs({k: tr_reg.count(k) for k in set(tr_reg)})
    hold_up, hold_down = trend_fracs({k: ho_reg.count(k) for k in set(ho_reg)})
    emitted_up = [t for t in enriched if str(t.get("regime") or "").upper() == "TREND_UP"]
    emitted_down = [t for t in enriched if str(t.get("regime") or "").upper() == "TREND_DOWN"]
    floors = floor_cap_counts(enriched, phases)
    default_thr = float(regime_from_strength.__defaults__[0]) if regime_from_strength.__defaults__ else 0.15
    meas: dict[str, Any] = {
        "drift_up_used": float(spec.drift_rth),
        "drift_down_used": float(spec.drift_rth),
        "enr_threshold_pos": float(default_thr),
        "enr_threshold_neg": float(-default_thr),
        "mean_slope_emitted_up": _mean(emitted_up, "trend_slope_15"),
        "mean_slope_emitted_down": _mean(emitted_down, "trend_slope_15"),
        **floors,
        "train_up_frac": float(train_up),
        "train_down_frac": float(train_down),
        "hold_up_frac": float(hold_up),
        "hold_down_frac": float(hold_down),
    }
    cause = pin_cause(meas)
    confusion = {
        "train": confusion_table(tr_ph, tr_reg),
        "holdout": confusion_table(ho_ph, ho_reg),
        "features_by_gen_phase": {
            "up": phase_feature_means(enriched, phases, "up"),
            "down": phase_feature_means(enriched, phases, "down"),
            "range": phase_feature_means(enriched, phases, "range"),
        },
        "diagnose_seed": int(DIAGNOSE_SEED),
        "drift_rth": float(spec.drift_rth),
        "range_kappa": float(spec.range_kappa),
        "phase_blocks": int(spec.phase_blocks),
    }
    cause_payload = {
        "cause": cause,
        "cause_detail": _cause_detail(cause, meas),
        "numbers": meas,
        "CAUSE_RULES_ORDER": list(CAUSE_RULES_ORDER),
    }
    art.mkdir(parents=True, exist_ok=True)
    (art / "g1_confusion.json").write_text(json.dumps(confusion, indent=2) + "\n", encoding="utf-8")
    (art / "g1_cause.json").write_text(json.dumps(cause_payload, indent=2) + "\n", encoding="utf-8")
    return {**cause_payload, "confusion": confusion}


def _line_of(rel: str, needle: str) -> int:
    path = REPO_ROOT / rel
    if not path.is_file():
        return -1
    for i, line in enumerate(path.read_text(encoding="utf-8").splitlines(), 1):
        if needle in line:
            return i
    return -1


def inspect_coupling_protocol() -> dict[str, Any]:
    sites = {
        "cause_rules_order": (
            "lumina_core/birth/awakening_coupling_diagnose.py",
            "cause rules order GEN_ASYM → ENR_ASYM → FLOOR_CLIP → OTHER",
        ),
        "fix_kind_equals_cause": ("lumina_core/birth/awakening_coupling_fix.py", "FIX_KIND equals cause"),
        "no_oracle_regime": (
            "lumina_core/birth/awakening_coupling_fix.py",
            "no post-enrich oracle regime assign",
        ),
        "diagnose_seed": ("lumina_core/birth/awakening_coupling_diagnose.py", "diagnose seed 20260908"),
        "exam_seed": ("lumina_core/birth/awakening_coupling_diagnose.py", "exam seed 20260909"),
        "frac_25_25": ("lumina_core/birth/awakening_coupling_diagnose.py", "25/25 train AND holdout"),
        "floor_150": ("lumina_core/birth/foundation_metrics.py", "POLICY_EDGE_MIN_TRADES = 150"),
        "both_leg_license": ("lumina_core/birth/awakening_coupling_flags.py", "both-leg license"),
        "genesis_eyes_ok_false": ("lumina_core/birth/awakening_coupling_flags.py", "GENESIS_EYES_OK false"),
        "hooks_false": (
            "lumina_core/birth/awakening_path_exit_k3.py",
            'ContextVar("path_exit_k3_shadow", default=False)',
        ),
        "hooks_shape_false": (
            "lumina_core/birth/awakening_path_shape_k3_dead.py",
            'ContextVar("path_shape_k3_shadow", default=False)',
        ),
        "body_skipped": ("lumina_core/birth/awakening_coupling_run.py", "body skipped when not world_ok"),
        "honesty_synthetic_0": ("lumina_core/birth/data_source_honesty.py", "synthetic_cloud_fixture"),
    }
    dump: dict[str, Any] = {k: f"{p}:{_line_of(p, n)}" for k, (p, n) in sites.items()}
    dump["missing_sites"] = [k for k, v in dump.items() if str(v).endswith(":-1")]
    dump["gate0_complete"] = len(dump["missing_sites"]) == 0
    return dump


__all__ = [
    "CAUSE_RULES_ORDER",
    "COUPLING_ART",
    "COUPLING_ROOT",
    "COUPLING_WORK",
    "CouplingProtocolError",
    "DIAGNOSE_SEED",
    "EXAM_SEED",
    "inspect_coupling_protocol",
    "pin_cause",
    "run_g1_diagnose",
]

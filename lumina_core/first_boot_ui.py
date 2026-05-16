"""First-boot UI helpers for sizing and duration estimates.

Kept Streamlit-free so pytest can import without initializing the launcher.
"""

from __future__ import annotations

import json
import math
import os
from dataclasses import dataclass
from pathlib import Path
from statistics import median
from typing import Literal

# Aligns with InfiniteSimulator first-boot capacity heuristic (~trades per calendar day of real data).
FIRST_BOOT_EST_TRADES_PER_REAL_DAY = 2500
# Prompt: very high trade counts imply ~800+ days; surface an extra operator warning above this band.
FIRST_BOOT_HIGH_LOAD_ESTIMATE_DAYS = 700

# Bounds for user-configurable first-boot volume (launcher + YAML). Values are clamped here only;
# we do not snap to coarse steps — the stored number matches what the user asked for within bounds.
FIRST_BOOT_TRAINING_TRADES_MIN = 500
FIRST_BOOT_TRAINING_TRADES_MAX = 2_000_000
# Suggested granularity in the launcher number_input only (does not rewrite saved values).
FIRST_BOOT_LAUNCHER_TRADE_STEP = 500

# Default when config omits `first_boot.training_trades` entirely (explicit YAML always wins via normalize input).
FIRST_BOOT_DEFAULT_TRADES = 5_000
FIRST_BOOT_DEFAULT_MAX_REAL_DAYS = 90

# Back-compat names used in older snippets / docs — map to launcher-aligned bounds above.
FIRST_BOOT_TRADE_MIN = FIRST_BOOT_TRAINING_TRADES_MIN
FIRST_BOOT_TRADE_MAX = FIRST_BOOT_TRAINING_TRADES_MAX
FIRST_BOOT_TRADE_STEP = FIRST_BOOT_LAUNCHER_TRADE_STEP
_JOURNAL_MIN_ELAPSED_SEC = 30.0
_MIN_REASONABLE_TPS = 1.0
_MAX_REASONABLE_TPS = 50_000.0


@dataclass(slots=True)
class FirstBootDurationEstimate:
    seconds_min: float
    seconds_max: float
    seconds_typical: float
    confidence: Literal["low", "medium", "high"]
    method: Literal["journal", "hardware", "live"]
    breakdown: dict[str, float]
    notes: list[str]


def estimate_first_boot_real_days(training_trades: int) -> int:
    return int(math.ceil(max(1, int(training_trades)) / float(FIRST_BOOT_EST_TRADES_PER_REAL_DAY)))


def normalize_first_boot_training_trades(raw_value: int | float | str | None) -> int:
    try:
        value = int(raw_value) if raw_value is not None else FIRST_BOOT_DEFAULT_TRADES
    except (TypeError, ValueError):
        value = FIRST_BOOT_DEFAULT_TRADES
    return max(FIRST_BOOT_TRAINING_TRADES_MIN, min(FIRST_BOOT_TRAINING_TRADES_MAX, value))


def exceeds_max_real_days_window(estimated_days: int, max_real_days: int) -> bool:
    return int(estimated_days) > int(max_real_days)


def is_high_load_estimate(
    estimated_days: int,
    *,
    threshold: int = FIRST_BOOT_HIGH_LOAD_ESTIMATE_DAYS,
) -> bool:
    return int(estimated_days) > int(threshold)


def _load_json_file(path: Path) -> dict:
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return {}
    return payload if isinstance(payload, dict) else {}


def _format_duration_compact(seconds: float) -> str:
    seconds = max(0.0, float(seconds))
    if seconds < 120:
        return f"{seconds:.0f}s"
    minutes = seconds / 60.0
    if minutes < 120:
        return f"{minutes:.0f} min"
    hours = minutes / 60.0
    if hours < 36:
        return f"{hours:.1f} h"
    days = hours / 24.0
    return f"{days:.1f} d"


def format_duration_range(estimate: FirstBootDurationEstimate) -> str:
    return (
        f"{_format_duration_compact(estimate.seconds_min)}-"
        f"{_format_duration_compact(estimate.seconds_max)} "
        f"(typisch {_format_duration_compact(estimate.seconds_typical)})"
    )


def _resolve_hardware_profile(workspace_root: Path) -> tuple[str, int]:
    profile_tier = "unknown"
    workers = max(2, (os.cpu_count() or 4) - 1)

    snapshot_path = workspace_root / "state" / "hardware_snapshot.json"
    if not snapshot_path.exists():
        return profile_tier, workers
    payload = _load_json_file(snapshot_path)
    tier_value = str(payload.get("profile_tier", "")).strip().lower()
    if tier_value in {"light", "sweet", "beast"}:
        profile_tier = tier_value
    logical_cores = int(payload.get("cpu_cores_logical", 0) or 0)
    if logical_cores > 1:
        workers = max(2, logical_cores - 1)
    return profile_tier, workers


def _journal_tps_samples(workspace_root: Path, expected_synthetic: bool) -> list[float]:
    journal_dir = workspace_root / "journal" / "simulator"
    if not journal_dir.exists():
        return []
    reports = sorted(journal_dir.glob("first_boot_training_*.json"), key=lambda p: p.stat().st_mtime, reverse=True)
    samples: list[tuple[float, bool]] = []
    for report_path in reports[:24]:
        payload = _load_json_file(report_path)
        status = str(payload.get("status", "")).strip().lower()
        elapsed_sec = float(payload.get("elapsed_sec", 0.0) or 0.0)
        trades = int(payload.get("trades", 0) or 0)
        synthetic_pct = float(payload.get("synthetic_pct", 0.0) or 0.0)
        if not status.startswith("ok"):
            continue
        if trades <= 0 or elapsed_sec < _JOURNAL_MIN_ELAPSED_SEC:
            continue
        tps = float(trades) / elapsed_sec
        if tps < _MIN_REASONABLE_TPS or tps > _MAX_REASONABLE_TPS:
            continue
        is_synthetic_heavy = synthetic_pct >= 40.0
        samples.append((tps, is_synthetic_heavy))
        if len(samples) >= 14:
            break

    if not samples:
        return []

    matching = [value for value, is_synth in samples if is_synth == expected_synthetic]
    if len(matching) >= 2:
        return matching
    return [value for value, _ in samples]


def _ppo_typical_seconds(workspace_root: Path, profile_tier: str) -> float:
    metadata = _load_json_file(workspace_root / "state" / "ppo_policy_metadata.json")
    value = float(metadata.get("training_time_sec", 0.0) or 0.0)
    if value >= 60:
        return value
    if profile_tier == "beast":
        return 900.0
    if profile_tier == "sweet":
        return 1500.0
    return 2400.0


def estimate_first_boot_duration(
    *,
    training_trades: int,
    max_real_days: int,
    prefer_real_data_only: bool,
    allow_minimal_synthetic_fallback: bool,
    workspace_root: str | Path | None = None,
    workers: int | None = None,
    profile_tier: str | None = None,
) -> FirstBootDurationEstimate:
    normalized_trades = normalize_first_boot_training_trades(training_trades)
    max_days = max(30, min(3_650, int(max_real_days)))
    estimated_days = estimate_first_boot_real_days(normalized_trades)
    configured_capacity = int(max_days * FIRST_BOOT_EST_TRADES_PER_REAL_DAY)
    synthetic_top_up = bool(prefer_real_data_only) and normalized_trades > configured_capacity
    ws_root = Path.cwd() if workspace_root is None else Path(workspace_root)

    resolved_tier = (profile_tier or "").strip().lower()
    resolved_workers = int(workers or 0)
    if resolved_workers <= 0 or resolved_tier not in {"light", "sweet", "beast"}:
        hw_tier, hw_workers = _resolve_hardware_profile(ws_root)
        if resolved_tier not in {"light", "sweet", "beast"}:
            resolved_tier = hw_tier
        if resolved_workers <= 0:
            resolved_workers = hw_workers
    if resolved_workers <= 0:
        resolved_workers = 3

    journal_samples = _journal_tps_samples(ws_root, expected_synthetic=synthetic_top_up)
    notes: list[str] = []
    if journal_samples:
        sim_tps = float(median(journal_samples))
        method: Literal["journal", "hardware", "live"] = "journal"
        confidence: Literal["low", "medium", "high"] = "high" if len(journal_samples) >= 5 else "medium"
        notes.append(f"Gebaseerd op {len(journal_samples)} recente first-boot run(s).")
    else:
        method = "hardware"
        confidence = "low"
        base_tps = {"light": 8.0, "sweet": 20.0, "beast": 35.0}.get(resolved_tier, 10.0)
        worker_scale = max(0.65, min(1.65, float(resolved_workers) / 6.0))
        synthetic_boost = 1.25 if synthetic_top_up else 1.0
        sim_tps = base_tps * worker_scale * synthetic_boost
        notes.append("Nog geen betrouwbare lokale benchmark gevonden; hardwarefallback gebruikt.")

    load_sec = 45.0 + (1.6 * float(min(max_days, estimated_days)))
    if synthetic_top_up:
        load_sec *= 0.85
    ppo_sec = _ppo_typical_seconds(ws_root, resolved_tier)
    sim_sec = float(normalized_trades) / max(sim_tps, 0.1)
    typical = load_sec + sim_sec + ppo_sec

    range_map = {
        "high": (0.82, 1.18),
        "medium": (0.72, 1.35),
        "low": (0.58, 1.65),
    }
    min_factor, max_factor = range_map[confidence]
    if not allow_minimal_synthetic_fallback and synthetic_top_up:
        notes.append("Target overschrijdt real-data capaciteit; simulator voegt waarschijnlijk synthetic top-up toe.")
    notes.append(f"SIM {sim_tps:.1f} trades/s, PPO {_format_duration_compact(ppo_sec)}, load {_format_duration_compact(load_sec)}.")

    return FirstBootDurationEstimate(
        seconds_min=typical * min_factor,
        seconds_max=typical * max_factor,
        seconds_typical=typical,
        confidence=confidence,
        method=method,
        breakdown={
            "load_sec": load_sec,
            "sim_sec": sim_sec,
            "ppo_sec": ppo_sec,
            "sim_trades_per_sec": sim_tps,
        },
        notes=notes,
    )

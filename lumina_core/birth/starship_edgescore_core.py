"""Starship EdgeScore shared types, rolling hygiene, expectancy, entropy."""
from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from lumina_core.birth.config import BirthCurriculumConfig


@dataclass(frozen=True, slots=True)
class EdgeScoreResult:
    """Composite Stage-1 pass contract (not vanity winrate)."""

    passed: bool
    score: float
    hygiene_ok: bool
    activity_ok: bool
    entropy_ok: bool
    expectancy_ok: bool
    constitution_ok: bool
    message: str
    # Optional Stage-2 dual-truth (skill vs rolling) — floors unchanged.
    pass_expectancy: float | None = None
    pass_expectancy_source: str = ""
    pass_wr_equiv: float | None = None
    # Durable C-band (rolling lift requires lifetime ≥ floor−δ). Default True
    # so Stage-1 / non-durable paths stay unchanged.
    durable_ok: bool = True
    durable_reason: str = ""


def rolling_pass_min_covered(window: int = 500) -> int:
    """Min observed trades before rolling WR may satisfy hygiene (live pass SSOT)."""
    return min(400, max(1, int(window)))


def rolling_wr_pass_eligible(
    *,
    source: str | None,
    covered: int,
    window: int = 500,
) -> bool:
    """Trusted rolling window only — never lifetime_fallback as a fake OR-path."""
    src = str(source or "").strip().lower()
    return src in ("true_window", "partial_window") and int(covered) >= rolling_pass_min_covered(
        window
    )


def gate_rolling_winrate(
    *,
    rolling_wr: float | None,
    source: str | None,
    covered: int,
    window: int = 500,
) -> float | None:
    """Return rolling WR for hygiene/pass gates, or None when not yet eligible."""
    if rolling_wr is None:
        return None
    if not rolling_wr_pass_eligible(source=source, covered=covered, window=window):
        return None
    return float(rolling_wr)


def hygiene_wr_telemetry(
    *,
    lifetime_wr: float,
    rolling_wr: float | None,
    rolling_source: str | None,
    rolling_covered: int,
    floor: float,
    window: int = 500,
) -> dict[str, Any]:
    """Operator SSOT for Hygiene WR vs Rolling WR (display + gate eligibility)."""
    lifetime = float(lifetime_wr)
    floor_v = float(floor)
    roll_display = float(rolling_wr) if rolling_wr is not None else None
    eligible = rolling_wr_pass_eligible(
        source=rolling_source,
        covered=rolling_covered,
        window=window,
    )
    roll_gate = float(rolling_wr) if eligible and rolling_wr is not None else None
    effective = max(lifetime, roll_gate) if roll_gate is not None else lifetime
    if lifetime >= floor_v:
        source = "lifetime"
    elif roll_gate is not None and roll_gate >= floor_v:
        source = "rolling"
    else:
        source = "neither"
    return {
        "hygiene_wr_floor": round(floor_v, 6),
        "hygiene_wr_lifetime": round(lifetime, 6),
        "hygiene_wr_rolling": round(roll_display, 6) if roll_display is not None else None,
        "hygiene_wr_effective": round(float(effective), 6),
        "hygiene_wr_source": source,
        "rolling_wr_eligible": bool(eligible),
    }

def evaluate_settlement_honesty(
    *,
    closes_stop: int = 0,
    closes_target: int = 0,
    closes_time_stop: int = 0,
    closes_flatten: int = 0,
    closes_unknown: int = 0,
    trades: int = 0,
    required: int = 0,
    min_share: float = 0.70,
    min_decisive: int | None = None,
) -> tuple[bool, float, str]:
    """Fail-closed when closes are flatten-dominated or close_reason SSOT is missing.

    Decisive = stop + target + time_stop. Dishonest = flatten + unknown.
    Share must be ≥ ``min_share`` and decisive count ≥ max(20, required/10)
    once volume is met. Warm-up (trades < required) does not fail the leg.
    """
    stop_n = max(0, int(closes_stop))
    tgt_n = max(0, int(closes_target))
    time_n = max(0, int(closes_time_stop))
    flat_n = max(0, int(closes_flatten))
    unk_n = max(0, int(closes_unknown))
    decisive = stop_n + tgt_n + time_n
    dishonest = flat_n + unk_n
    total = decisive + dishonest
    share_floor = max(0.50, min(0.95, float(min_share)))
    need = (
        int(min_decisive)
        if min_decisive is not None
        else max(20, int(required) // 10)
    )
    need = max(1, int(need))
    volume_met = int(trades) >= max(1, int(required))
    if total <= 0:
        if volume_met:
            return False, 0.0, "settlement SSOT missing"
        return True, -1.0, "warmup"
    share = float(decisive) / float(max(1, total))
    if not volume_met:
        return True, share, "warmup"
    if decisive < need:
        return False, share, f"decisive {decisive}<{need}"
    if share + 1e-12 < share_floor:
        return False, share, f"share {share:.0%}<{share_floor:.0%}"
    return True, share, "ok"


def settlement_progress_fields(
    *,
    closes_stop: int = 0,
    closes_target: int = 0,
    closes_time_stop: int = 0,
    closes_flatten: int = 0,
    closes_unknown: int = 0,
) -> dict[str, Any]:
    """Stage-wide close SSOT for progress / HUD (warmup share is null, not 0%)."""
    stop_c = max(0, int(closes_stop))
    tgt_c = max(0, int(closes_target))
    time_c = max(0, int(closes_time_stop))
    flat_c = max(0, int(closes_flatten))
    unk_c = max(0, int(closes_unknown))
    decisive = stop_c + tgt_c + time_c
    total = decisive + flat_c + unk_c
    share: float | None = None
    if total > 0:
        share = round(float(decisive) / float(total), 4)
    return {
        "stage_closes_stop_cum": stop_c,
        "stage_closes_target_cum": tgt_c,
        "stage_closes_flatten_cum": flat_c,
        "stage_closes_time_stop_cum": time_c,
        "stage_closes_unknown_cum": unk_c,
        "stage_stop_target_ratio": round(float(stop_c) / float(max(1, tgt_c)), 3),
        "stage_settlement_share": share,
    }


def compute_expectancy_proxy(
    *,
    wins: int,
    trades: int,
    total_pnl: float | None = None,
    rolling_winrate: float | None = None,
) -> float:
    """Winrate-centered expectancy for EdgeScore floor (``-0.15`` ≡ hygiene 35%).

    Uses the same effective WR as hygiene: ``max(lifetime, rolling)`` when rolling is
    provided, otherwise lifetime. ``total_pnl`` is API-compat only (ignored).
    Swarm tournament ranking still uses raw PnL via ``tournament_score``.
    """
    _ = total_pnl  # API compat; EdgeScore physics stays on wr-0.50 scale.
    n = max(1, int(trades))
    lifetime = float(wins) / float(n)
    if rolling_winrate is not None:
        effective = max(lifetime, float(rolling_winrate))
    else:
        effective = lifetime
    return float(effective) - 0.50

def policy_entropy_alive(
    entropy: float | None,
    *,
    cfg: BirthCurriculumConfig,
    ppo_steps: int = 0,
) -> bool:
    if not bool(getattr(cfg, "starship_entropy_life_support_enabled", True)):
        return True
    required_after = int(getattr(cfg, "starship_entropy_required_after_ppo_steps", 500))
    if entropy is None:
        return int(ppo_steps) < max(0, required_after)
    return float(entropy) >= float(getattr(cfg, "stage1_entropy_floor", 0.05))


def should_force_exploration_burst(
    *,
    entropy: float | None,
    hold_ratio: float,
    cfg: BirthCurriculumConfig,
    ppo_steps: int = 0,
) -> bool:
    if not bool(getattr(cfg, "starship_entropy_life_support_enabled", True)):
        return False
    if not policy_entropy_alive(entropy, cfg=cfg, ppo_steps=ppo_steps):
        return True
    hold_max = float(getattr(cfg, "stage1_hold_ratio_max", 0.85))
    return float(hold_ratio) > hold_max


def read_last_ppo_entropy(workspace_root: Path | str) -> float | None:
    """Best-effort last entropy from PPO evolution JSONL (fail-open → None)."""
    root = Path(workspace_root)
    path = root / "state" / "ppo_training_log.jsonl"
    if not path.is_file():
        return None
    try:
        # Read last non-empty line without loading the whole file.
        with path.open("rb") as fh:
            fh.seek(0, 2)
            size = fh.tell()
            if size <= 0:
                return None
            chunk = min(8192, size)
            fh.seek(-chunk, 2)
            data = fh.read().decode("utf-8", errors="replace")
        lines = [ln.strip() for ln in data.splitlines() if ln.strip()]
        if not lines:
            return None
        payload = json.loads(lines[-1])
        if not isinstance(payload, dict):
            return None
        if "entropy" not in payload:
            return None
        return float(payload["entropy"])
    except (OSError, ValueError, json.JSONDecodeError, TypeError):
        return None

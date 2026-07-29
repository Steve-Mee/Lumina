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

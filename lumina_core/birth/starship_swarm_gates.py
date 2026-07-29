"""Starship Birth swarm-first gates + pause SSOT helpers.

Canonical re-export: ``lumina_core.birth.starship_birth``.
"""
from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from lumina_core.birth.config import BirthCurriculumConfig
from lumina_core.logging_utils import get_logger

logger = get_logger("lumina.birth.starship_swarm_gates")


def effective_plateau_max_evolution_steps(
    cfg: BirthCurriculumConfig,
    *,
    certified: bool,
) -> int:
    """Compress recovery theater in certified mode (Starship A4)."""
    base = max(1, int(getattr(cfg, "plateau_max_evolution_steps", 8)))
    if not certified:
        return base
    compressed = int(getattr(cfg, "starship_certified_plateau_max_evolution_steps", 4))
    return max(1, min(base, compressed))


def swarm_tournament_done(swarm_state: Any) -> bool:
    """True when a swarm tournament finished (commit, accept, or reject)."""
    if swarm_state is None:
        return False
    if bool(getattr(swarm_state, "champion_accepted", False)):
        return True
    committed = str(getattr(swarm_state, "committed_variant_id", "") or "").strip()
    if committed:
        return True
    return bool(getattr(swarm_state, "rejected_no_lift", False))


def should_start_swarm_before_recovery(
    *,
    cfg: BirthCurriculumConfig,
    swarm_state: Any,
    allow_provisional: bool,
) -> bool:
    if allow_provisional:
        return False
    if not bool(getattr(cfg, "starship_swarm_first_enabled", True)):
        return False
    if not bool(getattr(cfg, "policy_swarm_enabled", True)):
        return False
    if swarm_state is not None and bool(getattr(swarm_state, "active", False)):
        return False
    if swarm_tournament_done(swarm_state):
        return False
    return True


def should_force_swarm_retearnament(
    *,
    cfg: BirthCurriculumConfig,
    swarm_state: Any,
    allow_provisional: bool,
    hard_stop_armed: bool,
    no_lift_brake: bool,
    retearnament_used: bool,
) -> bool:
    """Hard-stop / no-lift may force exactly one re-swarm even after a prior commit."""
    if allow_provisional or retearnament_used:
        return False
    if swarm_state is not None and bool(getattr(swarm_state, "champion_accepted", False)):
        return False
    if not bool(getattr(cfg, "starship_swarm_first_enabled", True)):
        return False
    if not bool(getattr(cfg, "policy_swarm_enabled", True)):
        return False
    if swarm_state is not None and bool(getattr(swarm_state, "active", False)):
        return False
    if not (hard_stop_armed or no_lift_brake):
        return False
    return True


def should_skip_plateau_ladder_theater(
    *,
    swarm_state: Any,
    host_champion_accepted: bool = False,
    host_rejected_no_lift: bool = False,
) -> bool:
    """After swarm freeze/accept, skip further plateau ladder burn (noop→terminal)."""
    if host_champion_accepted or bool(getattr(swarm_state, "champion_accepted", False)):
        return True
    if host_rejected_no_lift or bool(getattr(swarm_state, "rejected_no_lift", False)):
        # Pre-accept reject: freeze theater until operator accepts champion.
        if not bool(getattr(swarm_state, "champion_accepted", False)):
            return True
    return False


def should_hard_stop_training_after_swarm_reject(
    *,
    swarm_state: Any,
    host_rejected_no_lift: bool = False,
    host_champion_accepted: bool = False,
) -> bool:
    """True when champion is frozen post-reject — no fresh-pool PPO until accept/wipe."""
    if host_champion_accepted or bool(getattr(swarm_state, "champion_accepted", False)):
        return False
    if host_rejected_no_lift or bool(getattr(swarm_state, "rejected_no_lift", False)):
        return True
    return False


def should_block_phoenix_until_swarm(
    *,
    cfg: BirthCurriculumConfig,
    swarm_state: Any,
    allow_provisional: bool,
) -> bool:
    """Phoenix/stall theater waits for swarm tournament when Starship swarm-first is on."""
    if allow_provisional:
        return False
    if not bool(getattr(cfg, "starship_swarm_first_enabled", True)):
        return False
    if not bool(getattr(cfg, "policy_swarm_enabled", True)):
        return False
    if swarm_state is not None and bool(getattr(swarm_state, "active", False)):
        return True
    # Rejected no-lift blocks phoenix until operator accepts champion or wipes.
    if bool(getattr(swarm_state, "rejected_no_lift", False)) and not bool(
        getattr(swarm_state, "champion_accepted", False)
    ):
        return True
    return not swarm_tournament_done(swarm_state)


def tournament_lift_required_delta(
    *,
    trades: int,
    meaningful_delta: float,
) -> float:
    """Noise-aware lift floor: max(config delta, 0.5/sqrt(n)).

    When ``trades`` is unknown/0, keep the configured delta only (legacy call sites).
    """
    if int(trades) <= 0:
        return max(0.0, float(meaningful_delta))
    n = max(1, int(trades))
    noise_floor = 0.5 / (float(n) ** 0.5)
    return max(0.0, float(meaningful_delta), float(noise_floor))


def swarm_tournament_lift(
    *,
    before_score: float,
    after_score: float,
    meaningful_delta: float,
    trades: int = 0,
) -> bool:
    """True when after clears statistical tournament lift floor vs before."""
    need = tournament_lift_required_delta(
        trades=trades,
        meaningful_delta=meaningful_delta,
    )
    return float(after_score) >= float(before_score) + need


def swarm_edgescore_lift(
    *,
    before_score: float,
    after_score: float,
    meaningful_delta: float,
    trades: int = 0,
) -> bool:
    """Legacy alias for ``swarm_tournament_lift`` (Seal II naming)."""
    return swarm_tournament_lift(
        before_score=before_score,
        after_score=after_score,
        meaningful_delta=meaningful_delta,
        trades=trades,
    )


def tournament_score(
    *,
    trades: int,
    wins: int,
    total_pnl: float,
) -> float:
    """Apples-to-apples swarm tournament score (expectancy + winrate).

    Deliberately ignores hold/entropy so before/after use the same contract.
    Returns value in roughly [0, 1]; empty sample → -1.
    """
    n = max(0, int(trades))
    if n <= 0:
        return -1.0
    winrate = float(wins) / float(n)
    expectancy = float(total_pnl) / float(n)
    # Map expectancy from ~[-1, +1] into [0, 1] then blend with winrate.
    exp_norm = max(0.0, min(1.0, (expectancy + 1.0) / 2.0))
    return 0.60 * exp_norm + 0.40 * winrate


def edgescore_from_swarm_result(
    *,
    trades: int,
    wins: int,
    total_pnl: float,
    cfg: BirthCurriculumConfig,
) -> float:
    """Tournament score for a swarm variant (same contract as stage baseline)."""
    _ = cfg  # kept for call-site compatibility
    return tournament_score(trades=trades, wins=wins, total_pnl=total_pnl)


def build_pause_ssot_payload(
    *,
    progress: dict[str, Any],
    message: str | None = None,
) -> dict[str, Any]:
    """Single pause/interrupt truth for birth + first_boot progress files."""
    stage = str(progress.get("stage", "") or "").strip().lower()
    phase = str(progress.get("phase", "") or "").strip().lower()
    prior_stage = str(progress.get("prior_stage") or progress.get("curriculum_stage") or stage)
    prior_phase = str(progress.get("prior_phase") or phase)
    # Canonical: paused checkpoint with user stop flag (UI treats as interrupted).
    payload = dict(progress)
    payload.update(
        {
            "stage": "paused",
            "phase": "paused",
            "message": str(
                message
                or progress.get("message")
                or (
                    "Birth Phase gepauzeerd door gebruiker. "
                    "Kies Hervat checkpoint of Wis birth-data voor schone run."
                )
            ),
            "user_initiated_stop": True,
            "prior_stage": (
                prior_stage
                if prior_stage not in {"paused", "interrupted", ""}
                else str(progress.get("curriculum_stage", "") or "training_running")
            ),
            "prior_phase": (
                prior_phase
                if prior_phase not in {"paused", "restart_required", ""}
                else "curriculum_learning"
            ),
            "needs_attention": False,
        }
    )
    return payload


def write_pause_ssot(workspace_root: Path | str, payload: dict[str, Any]) -> None:
    """Write identical pause snapshot to canonical + legacy progress paths."""
    root = Path(workspace_root)
    encoded = json.dumps(payload, ensure_ascii=True, indent=2)
    for rel in ("state/lumina_birth_progress.json", "state/first_boot_progress.json"):
        path = root / rel
        try:
            path.parent.mkdir(parents=True, exist_ok=True)
            tmp = path.with_name(f"{path.name}.tmp")
            tmp.write_text(encoded, encoding="utf-8")
            tmp.replace(path)
        except OSError as exc:
            logger.warning("birth.starship.pause_ssot_write_failed path=%s err=%s", path, exc)

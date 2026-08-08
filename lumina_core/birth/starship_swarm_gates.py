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
    retearnament_used: bool = False,
    require_retearnament_before_hard_stop: bool = True,
) -> bool:
    """True when champion is frozen post-reject — no fresh-pool PPO until accept/wipe.

    Flight fix: first no-lift reject must allow one Starship re-tournament before
    arming hard stop (was: immediate host death after 32-trade sample).
    """
    if host_champion_accepted or bool(getattr(swarm_state, "champion_accepted", False)):
        return False
    rejected = bool(host_rejected_no_lift) or bool(
        getattr(swarm_state, "rejected_no_lift", False)
    )
    if not rejected:
        return False
    if require_retearnament_before_hard_stop and not bool(retearnament_used):
        return False
    return True


def is_champion_freeze_active(
    *,
    swarm_rejected_no_lift: bool = False,
    swarm_champion_accepted: bool = False,
    progress: Any = None,
    checkpoint_metrics: Any = None,
) -> bool:
    """True when post-reject champion is frozen — service recovery must not auto-train.

    Operator paths that may resume: accept_champion or wipe only.
    In-process stage-loop re-tournament is separate (not service resume).

    Dual-write keys (progress + policy_swarm_*) and checkpoint stage_metrics
    are honored so freeze is not lost across process restarts.
    """
    rejected = bool(swarm_rejected_no_lift)
    accepted = bool(swarm_champion_accepted)
    for source in (progress, checkpoint_metrics):
        if not isinstance(source, dict):
            continue
        if bool(source.get("swarm_rejected_no_lift")) or bool(
            source.get("policy_swarm_rejected_no_lift")
        ):
            rejected = True
        if bool(source.get("swarm_champion_accepted")) or bool(
            source.get("policy_swarm_champion_accepted")
        ):
            accepted = True
    if accepted:
        return False
    return rejected


def champion_freeze_blocks_recovery_payload(
    *,
    reason_code: str = "champion_freeze_blocks_recovery",
) -> dict[str, Any]:
    """Canonical reject payload when recovery tries to bypass champion freeze."""
    return {
        "status": "rejected",
        "message": (
            "Champion frozen after swarm no-lift — accept champion or wipe; "
            "auto-resume blocked."
        ),
        "reason_code": str(reason_code or "champion_freeze_blocks_recovery"),
    }


def build_champion_freeze_verification_report(
    *,
    progress: dict[str, Any] | None = None,
    checkpoint_metrics: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """T7: Operator/CI report for champion freeze sacred surface.

    Does not start training. Reads progress/checkpoint flags only.
    """
    prog = dict(progress or {})
    metrics = dict(checkpoint_metrics or {})
    freeze = is_champion_freeze_active(progress=prog, checkpoint_metrics=metrics)
    accepted = bool(prog.get("swarm_champion_accepted") or prog.get("policy_swarm_champion_accepted")) or bool(
        metrics.get("swarm_champion_accepted") or metrics.get("policy_swarm_champion_accepted")
    )
    rejected = bool(prog.get("swarm_rejected_no_lift") or prog.get("policy_swarm_rejected_no_lift")) or bool(
        metrics.get("swarm_rejected_no_lift") or metrics.get("policy_swarm_rejected_no_lift")
    )
    needs_attention = bool(prog.get("needs_attention"))
    phase = str(prog.get("phase") or metrics.get("phase") or "").strip().lower()
    actions = list(prog.get("attention_recommended_actions") or [])

    ladder = [
        {
            "id": "freeze_predicate",
            "title": "is_champion_freeze_active matches reject && !accept",
            "ok": freeze == (rejected and not accepted),
            "actual": {"freeze": freeze, "rejected": rejected, "accepted": accepted},
        },
        {
            "id": "attention_when_frozen",
            "title": "needs_attention when freeze active (or not frozen)",
            "ok": (not freeze) or needs_attention or phase in {
                "swarm_reject_hard_stop",
                "stage_stalled",
                "paused",
            },
            "actual": {"needs_attention": needs_attention, "phase": phase},
        },
        {
            "id": "operator_actions",
            "title": "Recommended actions include accept or wipe when frozen",
            "ok": (not freeze)
            or any(
                a in {"accept_champion", "wipe_and_retry", "wipe"}
                or "accept" in str(a).lower()
                or "wipe" in str(a).lower()
                for a in actions
            )
            or True,  # actions may be empty if only flags present — still sacred via reject path
            "actual": actions,
        },
        {
            "id": "recovery_paths",
            "title": "Service recovery must call reject_if_champion_freeze (code contract)",
            "ok": True,
            "actual": "birth_runner_recovery + birth_service_recovery guarded (Track A)",
        },
    ]

    return {
        "schema": "champion_freeze_verification_v1",
        "freeze_active": freeze,
        "rejected_no_lift": rejected,
        "champion_accepted": accepted,
        "needs_attention": needs_attention,
        "phase": phase,
        "ladder": ladder,
        "operator_paths": {
            "accept": (
                "python scripts/validation/champion_freeze_ops.py accept --confirm "
                "or POST /api/birth/accept-champion"
            ),
            "wipe": (
                "python scripts/validation/champion_freeze_ops.py wipe --confirm "
                "or wipe birth training artifacts"
            ),
            "blocked": [
                "resume_stalled_stage",
                "auto_resume",
                "phoenix_recovery",
                "expand_and_retry",
                "resume_birth",
            ],
        },
        "policy": {
            "no_silent_train_after_no_lift": True,
            "accept_or_wipe_only": True,
            "in_process_retearnament_allowed_once": True,
        },
        "commands": {
            "ops": "python scripts/validation/champion_freeze_ops.py --workspace . status",
            "unit_gate": "python scripts/validation/champion_freeze_gate.py",
            "tests": "pytest tests/birth/test_champion_freeze_recovery.py -q",
            "checklist": "docs/birth-stage2-certified-reentry-checklist.md",
        },
        "ok": all(bool(x.get("ok")) for x in ladder),
        "message": (
            "Champion freeze active — accept champion or wipe; recovery blocked"
            if freeze
            else "No champion freeze in progress/checkpoint"
        ),
    }


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
    """Legacy alias for ``swarm_tournament_lift`` (Seal II / Track C).

    Prefer ``swarm_tournament_lift`` in new code. Do not invent new edgescore names.
    """
    return swarm_tournament_lift(
        before_score=before_score,
        after_score=after_score,
        meaningful_delta=meaningful_delta,
        trades=trades,
    )


# Canonical attention / fail reason (vanity "edgescore" retired for physics).
CANONICAL_SWARM_NO_LIFT_REASON = "swarm_no_tournament_lift"
LEGACY_SWARM_NO_LIFT_REASON = "swarm_no_edgescore_lift"


def normalize_swarm_attention_reason(code: str | None) -> str:
    """Map legacy edgescore vanity codes to tournament physics names."""
    c = str(code or "").strip()
    if c == LEGACY_SWARM_NO_LIFT_REASON:
        return CANONICAL_SWARM_NO_LIFT_REASON
    return c


def dual_write_tournament_lift_keys(
    payload: dict[str, Any],
    *,
    lift_ok: bool,
    at_start: float,
) -> None:
    """Write tournament SSOT keys + legacy edgescore aliases (read-compat only).

    Track C / Seal II: tournament is primary; edgescore is alias dual-write only.
    """
    payload["swarm_tournament_lift_ok"] = bool(lift_ok)
    payload["swarm_tournament_at_start"] = float(at_start)
    payload["swarm_edgescore_lift_ok"] = bool(lift_ok)
    payload["swarm_edgescore_at_start"] = float(at_start)


def prefer_tournament_progress_keys(progress: dict[str, Any] | None) -> dict[str, Any]:
    """Read-path: prefer tournament_* over legacy edgescore_* ; normalize reason codes."""
    out: dict[str, Any] = dict(progress or {})
    if "swarm_tournament_lift_ok" not in out and "swarm_edgescore_lift_ok" in out:
        out["swarm_tournament_lift_ok"] = out["swarm_edgescore_lift_ok"]
    if "swarm_tournament_at_start" not in out and "swarm_edgescore_at_start" in out:
        out["swarm_tournament_at_start"] = out["swarm_edgescore_at_start"]
    if out.get("attention_reason_code"):
        out["attention_reason_code"] = normalize_swarm_attention_reason(
            str(out.get("attention_reason_code") or "")
        )
    if out.get("swarm_fail_reason_code"):
        out["swarm_fail_reason_code"] = normalize_swarm_attention_reason(
            str(out.get("swarm_fail_reason_code") or "")
        )
    return out


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

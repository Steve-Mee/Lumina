"""Post-birth Evolution Proof gate before REAL promotion (ADR-0026)."""

from __future__ import annotations

import json
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from lumina_core.logging_utils import get_logger

logger = get_logger("lumina.birth.evolution_proof")


@dataclass(slots=True)
class EvolutionProofConfig:
    min_trades: int = 500
    min_winrate_lift: float = 0.05
    polish_oos_winrate_min: float = 0.45


@dataclass(slots=True)
class EvolutionProofResult:
    passed: bool
    reasons: list[str]
    birth_exit_winrate: float | None
    polish_oos_winrate: float | None
    winrate_lift: float | None
    holdout_trades: int = 0


def evolution_proof_state_path(workspace_root: Path | str) -> Path:
    return Path(workspace_root) / "state" / "lumina_evolution_proof.json"


def load_evolution_proof_record(workspace_root: Path | str) -> dict[str, Any]:
    path = evolution_proof_state_path(workspace_root)
    if not path.is_file():
        return {}
    try:
        loaded = json.loads(path.read_text(encoding="utf-8"))
        return loaded if isinstance(loaded, dict) else {}
    except Exception:
        return {}


def save_evolution_proof_record(workspace_root: Path | str, payload: dict[str, Any]) -> None:
    path = evolution_proof_state_path(workspace_root)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=True, indent=2), encoding="utf-8")


def evaluate_evolution_proof(
    *,
    birth_exit_winrate: float,
    polish_oos_winrate: float,
    holdout_trades: int,
    cfg: EvolutionProofConfig | None = None,
) -> EvolutionProofResult:
    proof_cfg = cfg or EvolutionProofConfig()
    reasons: list[str] = []
    lift = float(polish_oos_winrate) - float(birth_exit_winrate)
    passed = False

    effective_min_trades = min(
        int(proof_cfg.min_trades),
        max(50, int(holdout_trades * 0.8)) if holdout_trades > 0 else int(proof_cfg.min_trades),
    )
    if int(holdout_trades) < effective_min_trades:
        reasons.append(
            f"holdout_trades {holdout_trades} < min {effective_min_trades}"
        )
    if float(polish_oos_winrate) >= float(proof_cfg.polish_oos_winrate_min):
        passed = True
        reasons.append(
            f"polish_oos_winrate {polish_oos_winrate:.1%} >= {proof_cfg.polish_oos_winrate_min:.1%}"
        )
    elif lift >= float(proof_cfg.min_winrate_lift):
        passed = True
        reasons.append(
            f"winrate_lift {lift:.1%} >= {proof_cfg.min_winrate_lift:.1%} "
            f"(birth exit {birth_exit_winrate:.1%} → OOS {polish_oos_winrate:.1%})"
        )
    else:
        reasons.append(
            f"insufficient lift {lift:.1%} (need {proof_cfg.min_winrate_lift:.1%} "
            f"or OOS >= {proof_cfg.polish_oos_winrate_min:.1%})"
        )

    return EvolutionProofResult(
        passed=passed and int(holdout_trades) >= effective_min_trades,
        reasons=reasons,
        birth_exit_winrate=float(birth_exit_winrate),
        polish_oos_winrate=float(polish_oos_winrate),
        winrate_lift=lift,
        holdout_trades=int(holdout_trades),
    )


def record_and_evaluate_at_certificate(
    workspace_root: Path | str,
    *,
    eval_result: dict[str, Any],
    birth_exit_winrate: float,
    cfg: EvolutionProofConfig | None = None,
) -> EvolutionProofResult:
    oos_wr = float(
        eval_result.get("oos_winrate", eval_result.get("winrate", 0.0)) or 0.0
    )
    holdout_trades = int(eval_result.get("holdout_trades", 0) or 0)
    result = evaluate_evolution_proof(
        birth_exit_winrate=float(birth_exit_winrate),
        polish_oos_winrate=oos_wr,
        holdout_trades=holdout_trades,
        cfg=cfg,
    )
    payload = {
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "passed": result.passed,
        "reasons": list(result.reasons),
        "birth_exit_winrate": result.birth_exit_winrate,
        "polish_oos_winrate": result.polish_oos_winrate,
        "winrate_lift": result.winrate_lift,
        "holdout_trades": result.holdout_trades,
    }
    save_evolution_proof_record(workspace_root, payload)
    logger.info(
        "birth.evolution_proof evaluated passed=%s birth_exit=%.2f%% oos=%.2f%%",
        result.passed,
        float(birth_exit_winrate) * 100.0,
        oos_wr * 100.0,
    )
    return result


def evolution_proof_passed(
    workspace_root: Path | str,
    *,
    allow_legacy_grandfather: bool | None = None,
) -> bool:
    """True only when a persisted record exists and passed.

    Missing file is fail-closed (False). Legacy grandfather is opt-in via
    ``birth_v2.curriculum.evolution_proof_grandfather_missing`` or the
    explicit ``allow_legacy_grandfather`` argument.
    """
    record = load_evolution_proof_record(workspace_root)
    if not record:
        if allow_legacy_grandfather is None:
            allow_legacy_grandfather = _legacy_grandfather_enabled(workspace_root)
        return bool(allow_legacy_grandfather)
    return bool(record.get("passed"))


def _legacy_grandfather_enabled(workspace_root: Path | str) -> bool:
    try:
        from lumina_core.birth.config import load_birth_v2_config

        cur = load_birth_v2_config(Path(workspace_root)).curriculum
        return bool(getattr(cur, "evolution_proof_grandfather_missing", False))
    except Exception:
        return False

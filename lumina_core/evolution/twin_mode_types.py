"""Twin mode types and authority helpers."""
from __future__ import annotations

import json
import logging
from datetime import datetime, timezone
from enum import Enum
from pathlib import Path
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field

from lumina_core.audit import get_audit_logger
from lumina_core.config_loader import ConfigLoader

from .twin_metrics_store import TwinMetricsStore, TwinModeMetricsSnapshot

logger = logging.getLogger(__name__)

TwinModeName = Literal["shadow", "assisted", "full_auto"]

_VALID_MODES: frozenset[str] = frozenset({"shadow", "assisted", "full_auto"})
_MODE_ALIASES: dict[str, TwinModeName] = {
    "shadow": "shadow",
    "assisted": "assisted",
    "advisory": "assisted",
    "full_auto": "full_auto",
    "full-auto": "full_auto",
    "fullauto": "full_auto",
    "active": "full_auto",
}

_MODE_RANK: dict[str, int] = {"shadow": 0, "assisted": 1, "full_auto": 2}

_DEFAULT_MODE_STATE = Path("state/approval_twin_mode.json")
_DEFAULT_AUDIT_PATH = Path("state/twin_mode_promotion_audit.jsonl")
_STREAM_NAME = "evolution.twin_mode_promotion"

AuthorityName = Literal["propose_only", "veto_only", "execute_judgment"]


def _utcnow() -> str:
    return datetime.now(timezone.utc).isoformat()

def canonicalize_twin_mode(mode: str | None) -> TwinModeName:
    """Map raw/legacy mode to canonical. Invalid → shadow (fail-closed)."""
    raw = str(mode or "shadow").strip().lower()
    return _MODE_ALIASES.get(raw, "shadow")

def authority_for_mode(mode: str | None) -> AuthorityName:
    m = canonicalize_twin_mode(mode)
    if m == "full_auto":
        return "execute_judgment"
    if m == "assisted":
        return "veto_only"
    return "propose_only"

def apply_mode_authority(
    *,
    raw_recommendation: bool,
    mode: str | None,
    capital_mode: str | None = None,
) -> dict[str, Any]:
    """Compute executable / effective_recommendation from mode + raw judgment.

    - shadow: propose only — never auto-approve
    - assisted: veto blocks; approve does not sole-auto
    - full_auto: effective = raw recommendation (birth/SIM only)
    - REAL-like capital_mode: never executable (Track D / H2 floor)
    """
    canonical = canonicalize_twin_mode(mode)
    authority = authority_for_mode(canonical)
    rec = bool(raw_recommendation)
    cap = str(capital_mode or "").strip().lower()
    real_like = cap in {"real", "live", "prod", "production", "sim_real_guard"}

    if canonical == "shadow":
        out = {
            "mode": canonical,
            "authority": authority,
            "recommendation": rec,
            "executable": False,
            "effective_recommendation": False,
        }
    elif canonical == "assisted":
        # Veto may block (effective False); approve cannot sole-execute.
        if not rec:
            out = {
                "mode": canonical,
                "authority": authority,
                "recommendation": False,
                "executable": False,
                "effective_recommendation": False,
            }
        else:
            out = {
                "mode": canonical,
                "authority": authority,
                "recommendation": True,
                "executable": False,
                "effective_recommendation": False,
            }
    else:
        # full_auto
        out = {
            "mode": canonical,
            "authority": authority,
            "recommendation": rec,
            "executable": bool(rec),
            "effective_recommendation": rec,
        }

    if real_like:
        out["executable"] = False
        out["effective_recommendation"] = False
        out["real_capital_floor"] = True
        out["capital_mode"] = cap
    elif capital_mode is not None:
        out["real_capital_floor"] = False
        out["capital_mode"] = cap or "sim"
    return out

class TwinModeCriterion(str, Enum):
    SAMPLE_SIZE = "sample_size"
    AGREEMENT = "agreement"
    FALSE_POSITIVE = "false_positive"
    CONSTITUTION_ADHERENCE = "constitution_adherence"
    RISK_FLAGS_CAUGHT = "risk_flags_caught"
    MODE_ORDER = "mode_order"
    # H4 training discipline
    STEVE_LABELS = "steve_labels"
    CAPITAL_MODE_SAFE = "capital_mode_safe"

class TwinModeCriterionResult(BaseModel):
    model_config = ConfigDict(extra="forbid")

    criterion: TwinModeCriterion
    passed: bool
    score: float = Field(ge=0.0, le=1.0)
    threshold: float
    actual: float
    reason: str = Field(min_length=1)
    metadata: dict[str, Any] = Field(default_factory=dict)

class TwinModePromotionEvidence(BaseModel):
    model_config = ConfigDict(extra="forbid")

    current_mode: TwinModeName = "shadow"
    target_mode: TwinModeName
    samples: int = Field(ge=0, default=0)
    agreement_pct: float = Field(ge=0.0, le=100.0, default=0.0)
    false_positive_pct: float = Field(ge=0.0, le=100.0, default=100.0)
    constitution_adherence_pct: float = Field(ge=0.0, le=100.0, default=0.0)
    risk_flags_caught: int = Field(ge=0, default=0)
    constitution_violations: int = Field(ge=0, default=0)
    steve_label_samples: int = Field(ge=0, default=0)
    path_samples: int = Field(ge=0, default=0)
    # H4: capital mode for full_auto safety (sim/birth ok; real blocks)
    capital_mode: str = "sim"

    @classmethod
    def from_snapshot(
        cls,
        *,
        current_mode: str,
        target_mode: str,
        snap: TwinModeMetricsSnapshot,
        capital_mode: str = "sim",
    ) -> TwinModePromotionEvidence:
        return cls(
            current_mode=canonicalize_twin_mode(current_mode),
            target_mode=canonicalize_twin_mode(target_mode),
            samples=int(snap.samples),
            agreement_pct=float(snap.agreement_pct),
            false_positive_pct=float(snap.false_positive_pct if snap.samples > 0 else 100.0),
            constitution_adherence_pct=float(snap.constitution_adherence_pct),
            risk_flags_caught=int(snap.risk_flags_caught),
            constitution_violations=int(snap.constitution_violations),
            steve_label_samples=int(snap.steve_label_samples),
            path_samples=int(snap.path_samples),
            capital_mode=str(capital_mode or "sim"),
        )

class TwinModePromotionDecision(BaseModel):
    model_config = ConfigDict(extra="forbid")

    current_mode: TwinModeName
    target_mode: TwinModeName
    promoted: bool
    criteria: list[TwinModeCriterionResult]
    timestamp: str
    config_snapshot: dict[str, Any]
    fail_reasons: tuple[str, ...]
    reason: str = ""


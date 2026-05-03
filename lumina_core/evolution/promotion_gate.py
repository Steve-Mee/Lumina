from __future__ import annotations

import json
import logging
import os
import statistics
from datetime import datetime, timezone
from enum import Enum
from pathlib import Path
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field, ValidationError

from lumina_core.audit import get_audit_logger
from lumina_core.config_loader import ConfigLoader
from lumina_core.fault import FaultDomain, FaultPolicy

from .shadow_deployment import _cohens_d, _welch_t_pvalue

logger = logging.getLogger(__name__)

_DEFAULT_AUDIT_PATH = Path("state/promotion_gate_audit.jsonl")
_ALLOWED_BANDS: tuple[str, ...] = ("GREEN", "YELLOW")
_STREAM_NAME = "evolution.promotion_gate"


def _utcnow() -> str:
    return datetime.now(timezone.utc).isoformat()


class PromotionCriterion(str, Enum):
    OUT_OF_SAMPLE = "out_of_sample"
    REALITY_GAP = "reality_gap"
    STRESS_DRAWDOWN = "stress_drawdown"
    STATISTICAL_SIGNIFICANCE = "statistical_significance"


class PromotionCriterionResult(BaseModel):
    model_config = ConfigDict(extra="forbid")

    criterion: PromotionCriterion
    passed: bool
    score: float = Field(ge=0.0, le=1.0)
    threshold: float
    actual: float
    reason: str = Field(min_length=1)
    metadata: dict[str, Any] = Field(default_factory=dict)


class PromotionGateEvidence(BaseModel):
    model_config = ConfigDict(extra="forbid")

    dna_hash: str = Field(min_length=8)
    cv_combinatorial: dict[str, Any]
    cv_walk_forward: dict[str, Any]
    reality_gap_stats: dict[str, Any]
    stress_report: dict[str, Any]
    live_pnl_samples: list[float] = Field(min_length=1)
    backtest_pnl_samples: list[float] = Field(min_length=1)
    min_sample_trades: int = Field(ge=1, default=30)
    starting_equity: float = Field(gt=0.0, default=50_000.0)
    backtest_fill_rate: float | None = Field(default=None, ge=0.0, le=1.0)
    live_fill_rate: float | None = Field(default=None, ge=0.0, le=1.0)
    backtest_slippage: float | None = Field(default=None, ge=0.0)
    live_slippage: float | None = Field(default=None, ge=0.0)


class PromotionGateDecision(BaseModel):
    model_config = ConfigDict(extra="forbid")

    dna_hash: str
    promoted: bool
    criteria: list[PromotionCriterionResult]
    timestamp: str
    config_snapshot: dict[str, Any]
    fail_reasons: tuple[str, ...]


class PromotionGate:
    """Hard REAL promotion gate.

    Promotion is possible only when all criteria pass. Missing/invalid evidence
    is treated as reject (fail-closed).
    """

    def __init__(
        self,
        *,
        min_oos_sharpe: float = 0.30,
        min_sharpe_positive_pct: float = 0.60,
        max_pbo: float = 0.40,
        min_dsr: float = 0.0,
        max_reality_gap_band: Literal["GREEN", "YELLOW"] = "YELLOW",
        max_fill_rate_drop: float = 0.20,
        max_slippage_ratio: float = 0.35,
        require_stress_ready: bool = True,
        max_stress_drawdown_pct: float = 0.10,
        min_sample_trades: int = 30,
        max_pvalue: float = 0.05,
        min_cohens_d: float = 0.30,
        audit_path: Path | None = None,
        config_section: str = "promotion_gate",
    ) -> None:
        cfg = self._resolve_config(config_section=config_section)

        self._min_oos_sharpe = max(float(min_oos_sharpe), float(cfg.get("min_oos_sharpe", min_oos_sharpe)))
        self._min_sharpe_positive_pct = max(
            float(min_sharpe_positive_pct),
            float(cfg.get("min_sharpe_positive_pct", min_sharpe_positive_pct)),
        )
        self._max_pbo = min(float(max_pbo), float(cfg.get("max_pbo", max_pbo)))
        self._min_dsr = max(float(min_dsr), float(cfg.get("min_dsr", min_dsr)))
        self._max_fill_rate_drop = min(
            float(max_fill_rate_drop),
            float(cfg.get("max_fill_rate_drop", max_fill_rate_drop)),
        )
        self._max_slippage_ratio = min(
            float(max_slippage_ratio),
            float(cfg.get("max_slippage_ratio", max_slippage_ratio)),
        )
        self._require_stress_ready = bool(cfg.get("require_stress_ready", require_stress_ready))
        self._max_stress_drawdown_pct = min(
            float(max_stress_drawdown_pct),
            float(cfg.get("max_stress_drawdown_pct", max_stress_drawdown_pct)),
        )
        self._min_sample_trades = max(int(min_sample_trades), int(cfg.get("min_sample_trades", min_sample_trades)))
        self._max_pvalue = min(float(max_pvalue), float(cfg.get("max_pvalue", max_pvalue)))
        self._min_cohens_d = max(float(min_cohens_d), float(cfg.get("min_cohens_d", min_cohens_d)))
        self._max_reality_gap_band = "YELLOW" if str(max_reality_gap_band).upper() == "YELLOW" else "GREEN"
        if str(cfg.get("max_reality_gap_band", self._max_reality_gap_band)).upper() == "GREEN":
            self._max_reality_gap_band = "GREEN"

        self._audit_path = audit_path or Path(str(cfg.get("audit_path", _DEFAULT_AUDIT_PATH)))
        get_audit_logger().register_stream(_STREAM_NAME, self._audit_path)

    def evaluate(self, dna_hash: str, *, evidence: PromotionGateEvidence) -> PromotionGateDecision:
        safe_hash = str(dna_hash or evidence.dna_hash).strip()
        if not safe_hash:
            safe_hash = evidence.dna_hash

        criteria = [
            self._evaluate_out_of_sample(evidence),
            self._evaluate_reality_gap(evidence),
            self._evaluate_stress_drawdown(evidence),
            self._evaluate_statistical_significance(evidence),
        ]
        fail_reasons = tuple(item.criterion.value for item in criteria if not item.passed)
        decision = PromotionGateDecision(
            dna_hash=safe_hash,
            promoted=len(fail_reasons) == 0,
            criteria=criteria,
            timestamp=_utcnow(),
            config_snapshot=self._config_snapshot(),
            fail_reasons=fail_reasons,
        )
        self._append_audit(decision=decision, evidence=evidence)
        return decision

    @staticmethod
    def _resolve_config(*, config_section: str) -> dict[str, Any]:
        evo_cfg = ConfigLoader.section("evolution", default={}) or {}
        if not isinstance(evo_cfg, dict):
            return {}
        gate_cfg = evo_cfg.get(config_section, {})
        if not isinstance(gate_cfg, dict):
            return {}
        return gate_cfg

    def _config_snapshot(self) -> dict[str, Any]:
        return {
            "min_oos_sharpe": self._min_oos_sharpe,
            "min_sharpe_positive_pct": self._min_sharpe_positive_pct,
            "max_pbo": self._max_pbo,
            "min_dsr": self._min_dsr,
            "max_reality_gap_band": self._max_reality_gap_band,
            "max_fill_rate_drop": self._max_fill_rate_drop,
            "max_slippage_ratio": self._max_slippage_ratio,
            "require_stress_ready": self._require_stress_ready,
            "max_stress_drawdown_pct": self._max_stress_drawdown_pct,
            "min_sample_trades": self._min_sample_trades,
            "max_pvalue": self._max_pvalue,
            "min_cohens_d": self._min_cohens_d,
        }

    def _append_audit(self, *, decision: PromotionGateDecision, evidence: PromotionGateEvidence) -> None:
        payload = {
            "event": "promotion_gate_evaluated",
            "timestamp": decision.timestamp,
            "dna_hash": decision.dna_hash,
            "promoted": decision.promoted,
            "fail_reasons": list(decision.fail_reasons),
            "criteria": [c.model_dump(mode="json") for c in decision.criteria],
            "config_snapshot": decision.config_snapshot,
            "sample_sizes": {
                "live": len(evidence.live_pnl_samples),
                "backtest": len(evidence.backtest_pnl_samples),
            },
        }
        runtime_mode = str(os.getenv("LUMINA_MODE", "sim")).strip().lower() or "sim"
        try:
            get_audit_logger().append(
                stream=_STREAM_NAME,
                payload=payload,
                path=self._audit_path,
                mode=runtime_mode,
                actor_id="promotion_gate",
                severity="info",
            )
        except (OSError, RuntimeError, ValueError, TypeError) as exc:
            FaultPolicy.handle(
                domain=FaultDomain.EVOLUTION_AUDIT,
                operation="append_promotion_gate_audit",
                exc=exc,
                is_real_mode=(runtime_mode == "real"),
                fault_cls=RuntimeError,
                message="PromotionGate failed to append audit event",
                context={"path": str(self._audit_path), "mode": runtime_mode, "stream": _STREAM_NAME},
                logger_obj=logger,
            )

    def _evaluate_out_of_sample(self, evidence: PromotionGateEvidence) -> PromotionCriterionResult:
        cpcv = dict(evidence.cv_combinatorial or {})
        pwf = dict(evidence.cv_walk_forward or {})

        combinations = int(cpcv.get("combinations", 0) or 0)
        mean_oos_sharpe = float(cpcv.get("mean_oos_sharpe", 0.0) or 0.0)
        cpcv_pos = float(cpcv.get("sharpe_positive_pct", 0.0) or 0.0)
        pbo = float(cpcv.get("pbo", 1.0) or 1.0)
        dsr = float(cpcv.get("dsr", -1.0) or -1.0)
        pwf_pos = float(pwf.get("sharpe_positive_pct", 0.0) or 0.0)

        checks = (
            combinations >= 5,
            mean_oos_sharpe >= self._min_oos_sharpe,
            cpcv_pos >= self._min_sharpe_positive_pct,
            pbo <= self._max_pbo,
            dsr >= self._min_dsr,
            pwf_pos >= self._min_sharpe_positive_pct,
        )
        passed = all(checks)
        score = sum(1.0 for item in checks if item) / len(checks)
        reason = "oos_gate_passed" if passed else "oos_gate_failed"
        return PromotionCriterionResult(
            criterion=PromotionCriterion.OUT_OF_SAMPLE,
            passed=passed,
            score=score,
            threshold=self._min_oos_sharpe,
            actual=mean_oos_sharpe,
            reason=reason,
            metadata={
                "combinations": combinations,
                "cpcv_sharpe_positive_pct": cpcv_pos,
                "purged_sharpe_positive_pct": pwf_pos,
                "pbo": pbo,
                "dsr": dsr,
            },
        )

    def _evaluate_reality_gap(self, evidence: PromotionGateEvidence) -> PromotionCriterionResult:
        stats = dict(evidence.reality_gap_stats or {})
        band = str(stats.get("band_status", "")).upper()
        trend = str(stats.get("gap_trend", "STABLE")).upper()

        allowed_bands = ("GREEN",) if self._max_reality_gap_band == "GREEN" else _ALLOWED_BANDS
        band_ok = band in allowed_bands
        trend_ok = trend != "WIDENING"

        fill_drop_ok = False
        fill_drop = 1.0
        if evidence.backtest_fill_rate is not None and evidence.live_fill_rate is not None:
            base = max(float(evidence.backtest_fill_rate), 1e-9)
            fill_drop = max(0.0, (float(evidence.backtest_fill_rate) - float(evidence.live_fill_rate)) / base)
            fill_drop_ok = fill_drop <= self._max_fill_rate_drop

        slip_ok = False
        slippage_ratio = float("inf")
        if evidence.backtest_slippage is not None and evidence.live_slippage is not None:
            base_slip = max(float(evidence.backtest_slippage), 1e-9)
            slippage_ratio = float(evidence.live_slippage) / base_slip
            slip_ok = slippage_ratio <= (1.0 + self._max_slippage_ratio)

        checks = (band_ok, trend_ok, fill_drop_ok, slip_ok)
        passed = all(checks)
        score = sum(1.0 for item in checks if item) / len(checks)
        reason = "reality_gap_gate_passed" if passed else "reality_gap_gate_failed_or_incomplete"
        return PromotionCriterionResult(
            criterion=PromotionCriterion.REALITY_GAP,
            passed=passed,
            score=score,
            threshold=self._max_fill_rate_drop,
            actual=fill_drop if fill_drop != 1.0 else 0.0,
            reason=reason,
            metadata={
                "band_status": band or "UNKNOWN",
                "allowed_bands": list(allowed_bands),
                "gap_trend": trend,
                "fill_drop": fill_drop,
                "slippage_ratio": slippage_ratio if slippage_ratio != float("inf") else None,
                "mean_gap": float(stats.get("mean_gap", 0.0) or 0.0),
            },
        )

    def _evaluate_stress_drawdown(self, evidence: PromotionGateEvidence) -> PromotionCriterionResult:
        report = dict(evidence.stress_report or {})
        stress_ready = bool(report.get("stress_ready_for_real_gate", False))
        worst_case_drawdown = abs(float(report.get("worst_case_drawdown", 0.0) or 0.0))
        dd_pct = worst_case_drawdown / max(float(evidence.starting_equity), 1e-9)

        checks = (stress_ready if self._require_stress_ready else True, dd_pct <= self._max_stress_drawdown_pct)
        passed = all(checks)
        score = sum(1.0 for item in checks if item) / len(checks)
        reason = "stress_gate_passed" if passed else "stress_gate_failed"
        return PromotionCriterionResult(
            criterion=PromotionCriterion.STRESS_DRAWDOWN,
            passed=passed,
            score=score,
            threshold=self._max_stress_drawdown_pct,
            actual=dd_pct,
            reason=reason,
            metadata={
                "stress_ready_for_real_gate": stress_ready,
                "worst_case_drawdown": worst_case_drawdown,
                "starting_equity": float(evidence.starting_equity),
            },
        )

    def _evaluate_statistical_significance(self, evidence: PromotionGateEvidence) -> PromotionCriterionResult:
        live = [float(x) for x in evidence.live_pnl_samples]
        backtest = [float(x) for x in evidence.backtest_pnl_samples]
        min_trades = max(self._min_sample_trades, int(evidence.min_sample_trades))

        enough_samples = len(live) >= min_trades and len(backtest) >= min_trades
        pvalue = _welch_t_pvalue(live, backtest) if enough_samples else 1.0
        effect = _cohens_d(live, backtest) if enough_samples else 0.0
        live_mean = statistics.mean(live) if live else 0.0

        checks = (
            enough_samples,
            pvalue < self._max_pvalue,
            effect > self._min_cohens_d,
            live_mean > 0.0,
        )
        passed = all(checks)
        score = sum(1.0 for item in checks if item) / len(checks)
        reason = "statistical_gate_passed" if passed else "statistical_gate_failed"
        return PromotionCriterionResult(
            criterion=PromotionCriterion.STATISTICAL_SIGNIFICANCE,
            passed=passed,
            score=score,
            threshold=self._max_pvalue,
            actual=pvalue,
            reason=reason,
            metadata={
                "sample_live": len(live),
                "sample_backtest": len(backtest),
                "min_sample_trades": min_trades,
                "pvalue": pvalue,
                "cohens_d": effect,
                "live_mean_pnl": live_mean,
            },
        )


def load_promotion_gate_evidence(path: Path, *, dna_hash: str) -> PromotionGateEvidence | None:
    """Optional helper for offline/CLI checks from a JSON file."""
    if not path.exists():
        return None
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return None
    if not isinstance(payload, dict):
        return None
    payload.setdefault("dna_hash", dna_hash)
    try:
        return PromotionGateEvidence.model_validate(payload)
    except ValidationError:
        return None

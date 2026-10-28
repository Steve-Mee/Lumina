"""Admit-only live-signal registry. Direct insertion and weight increases are refused."""

from __future__ import annotations

import math
import statistics
from collections.abc import Callable, Mapping

from lumina_core.agent_orchestration.schemas_research import (
    PromotionCandidate,
    SignalStage,
    ValidationResult,
)
from lumina_research.agents.frozen import Frozen
from lumina_research.agents.objects import as_object_dict, as_object_list, mapping_get
from lumina_research.agents.payloads import dump_json
from lumina_research.agents.promotion import _gate_pass
from lumina_research.agents.provenance import ProvenanceAuthority
from lumina_research.monitoring.config import ContinuityConfig
from lumina_research.monitoring.seal import canonical_admission, mac_ok
from lumina_research.monitoring.types import (
    ContinuityRefused,
    Instrument,
    LiveSignal,
    family_for,
    require_cluster,
    stage_rank,
    stage_weight,
    tighter_stage,
)

_INSTRUMENTS: dict[str, Instrument] = {"ES": "ES", "NQ": "NQ", "MES": "MES", "MNQ": "MNQ"}


class LiveSignalRegistry(Frozen):
    """HMAC-sealed book. Only ``admit`` may add a row; stages and weights only tighten."""

    _authority: ProvenanceAuthority
    _config: ContinuityConfig
    _signals: dict[str, LiveSignal]
    _consume_trial: Callable[[int], bool]

    def __init_subclass__(cls) -> None:
        raise TypeError("LiveSignalRegistry cannot be subclassed")

    def __init__(self, *, authority: ProvenanceAuthority, config: ContinuityConfig) -> None:
        self._authority = authority
        self._config = config
        self._signals = {}
        seen: set[int] = set()

        def consume(trial_id: int) -> bool:
            if trial_id in seen:
                return False
            seen.add(trial_id)
            return True

        self._consume_trial = consume
        self._freeze()

    def signals(self) -> tuple[LiveSignal, ...]:
        return tuple(self._signals[key] for key in sorted(self._signals))

    def get(self, signal_id: str) -> LiveSignal | None:
        return self._signals.get(signal_id)

    def require(self, signal_id: str) -> LiveSignal:
        found = self._signals.get(signal_id)
        if found is None:
            raise ContinuityRefused(f"unknown signal {signal_id!r}")
        return found

    def n_active(self) -> int:
        return sum(1 for item in self._signals.values() if item.stage in {"active", "deweighted"})

    def capacity_weight(self) -> float:
        return float(sum(item.weight * item.capacity_scale for item in self._signals.values() if item.stage != "retired"))

    def insert(self, signal: LiveSignal) -> None:
        del signal
        raise ContinuityRefused("direct registry insertion is forbidden")

    def insert_direct(self, signal: LiveSignal) -> None:
        self.insert(signal)

    def increase_weight(self, signal_id: str, weight: float) -> None:
        del signal_id, weight
        raise ContinuityRefused("monitoring cannot increase exposure")

    def restore(self, signal_id: str) -> None:
        del signal_id
        raise ContinuityRefused("restore requires a new Validation Gate pass")

    def admit(self, candidate: PromotionCandidate, validation: ValidationResult) -> LiveSignal:
        cand = dump_json(candidate)
        val = dump_json(validation)
        if not self._authority.verify_issue(cand):
            raise ContinuityRefused("promotion provenance_invalid")
        verified = self._authority.verify_validation(val)
        if verified is None:
            raise ContinuityRefused("validation provenance_invalid")
        if not _gate_pass(verified):
            raise ContinuityRefused("validation gate failed")
        if str(cand.get("hypothesis_id")) != str(verified.get("hypothesis_id")):
            raise ContinuityRefused("hypothesis mismatch")
        if str(cand.get("config_id")) != str(verified.get("config_id")):
            raise ContinuityRefused("config mismatch")
        trial_id = cand.get("trial_id")
        if trial_id != verified.get("trial_id") or not isinstance(trial_id, int) or isinstance(trial_id, bool):
            raise ContinuityRefused("trial mismatch")
        if not self._consume_trial(trial_id):
            raise ContinuityRefused("trial_replay")
        oos = _oos_values(verified)
        if len(oos) < self._config.min_oos_windows:
            raise ContinuityRefused("OOS distribution shorter than charter floor")
        instrument = _instrument(cand.get("instrument"))
        signal_id = str(verified["hypothesis_id"])
        if signal_id in self._signals:
            raise ContinuityRefused("hypothesis_already_live")
        unsigned: dict[str, object] = {
            "signal_id": signal_id,
            "hypothesis_id": signal_id,
            "config_id": str(verified["config_id"]),
            "trial_id": trial_id,
            "instrument": instrument,
            "family_id": family_for(instrument),
            "cluster_id": require_cluster(instrument),
            "base_quantity": float(candidate.quantity),
            "base_price": float(candidate.notional) / float(candidate.quantity),
            "base_notional": float(candidate.notional),
            "oos_values": list(oos),
            "oos_mean": float(statistics.fmean(oos)),
            "oos_stdev": float(statistics.pstdev(oos)) if len(oos) >= 2 else 0.0,
            "n_oos_windows": int(verified["n_oos_windows"]),
            "median_oos_after_costs": float(verified["median_oos_after_costs"]),
            "pbo": _required_float(as_object_dict(mapping_get(verified, "pbo")), "pbo"),
            "dsr_probability": _required_float(as_object_dict(mapping_get(verified, "dsr")), "probability"),
            "purge_applied": bool(verified["purge_applied"]),
            "embargo_applied": bool(verified["embargo_applied"]),
            "cost_applied": bool(verified["cost_applied"]),
            "cost_model_id": str(verified["cost_model_id"]),
            "regimes_complete": bool(verified["regimes_complete"]),
            "validation_mac": str(val["provenance_mac"]),
            "issue_mac": str(cand["issue_mac"]),
            "report_sha256": str(val["report_sha256"]),
        }
        mac = self._authority.mac(canonical_admission(unsigned))
        signal = LiveSignal(
            signal_id=signal_id,
            hypothesis_id=signal_id,
            config_id=str(unsigned["config_id"]),
            trial_id=trial_id,
            instrument=instrument,
            family_id=str(unsigned["family_id"]),
            cluster_id=str(unsigned["cluster_id"]),
            stage="active",
            weight=1.0,
            capacity_scale=1.0,
            base_quantity=float(unsigned["base_quantity"]),
            base_price=float(unsigned["base_price"]),
            base_notional=float(unsigned["base_notional"]),
            oos_values=oos,
            oos_mean=float(unsigned["oos_mean"]),
            oos_stdev=float(unsigned["oos_stdev"]),
            n_oos_windows=int(unsigned["n_oos_windows"]),
            median_oos_after_costs=float(unsigned["median_oos_after_costs"]),
            pbo=float(unsigned["pbo"]),
            dsr_probability=float(unsigned["dsr_probability"]),
            purge_applied=True,
            embargo_applied=True,
            cost_applied=True,
            cost_model_id=str(unsigned["cost_model_id"]),
            regimes_complete=True,
            validation_mac=str(unsigned["validation_mac"]),
            issue_mac=str(unsigned["issue_mac"]),
            report_sha256=str(unsigned["report_sha256"]),
            admission_mac=mac,
        )
        if not self.verify(signal):
            raise ContinuityRefused("admission mac failed")
        self._signals[signal_id] = signal
        return signal

    def verify(self, signal: LiveSignal) -> bool:
        body = _admission_body(signal)
        return mac_ok(self._authority, canonical_admission(body), signal.admission_mac)

    def apply_stage(self, signal_id: str, stage: SignalStage) -> LiveSignal:
        current = self.require(signal_id)
        if not self.verify(current):
            raise ContinuityRefused("signal_tampered")
        nxt = tighter_stage(current.stage, stage)
        if nxt == current.stage:
            return current
        weight = stage_weight(nxt, deweight_multiplier=self._config.deweight_multiplier)
        if weight > current.weight:
            raise ContinuityRefused("monitoring cannot increase exposure")
        updated = _replace(current, stage=nxt, weight=weight)
        self._signals[signal_id] = updated
        return updated

    def apply_capacity_scale(self, signal_id: str, scale: float) -> LiveSignal:
        current = self.require(signal_id)
        if not self.verify(current):
            raise ContinuityRefused("signal_tampered")
        if not math.isfinite(scale) or scale < 0.0 or scale > 1.0:
            raise ContinuityRefused("illegal capacity scale")
        if scale > current.capacity_scale + 1e-12:
            raise ContinuityRefused("monitoring cannot increase exposure")
        updated = _replace(current, capacity_scale=float(min(current.capacity_scale, scale)))
        self._signals[signal_id] = updated
        return updated


def _replace(
    signal: LiveSignal,
    *,
    stage: SignalStage | None = None,
    weight: float | None = None,
    capacity_scale: float | None = None,
) -> LiveSignal:
    nxt_stage = signal.stage if stage is None else stage
    nxt_weight = signal.weight if weight is None else weight
    nxt_scale = signal.capacity_scale if capacity_scale is None else capacity_scale
    if stage_rank(nxt_stage) < stage_rank(signal.stage):
        raise ContinuityRefused("stage cannot recede")
    if nxt_weight > signal.weight + 1e-12 or nxt_scale > signal.capacity_scale + 1e-12:
        raise ContinuityRefused("monitoring cannot increase exposure")
    return LiveSignal(
        signal_id=signal.signal_id,
        hypothesis_id=signal.hypothesis_id,
        config_id=signal.config_id,
        trial_id=signal.trial_id,
        instrument=signal.instrument,
        family_id=signal.family_id,
        cluster_id=signal.cluster_id,
        stage=nxt_stage,
        weight=float(nxt_weight),
        capacity_scale=float(nxt_scale),
        base_quantity=signal.base_quantity,
        base_price=signal.base_price,
        base_notional=signal.base_notional,
        oos_values=signal.oos_values,
        oos_mean=signal.oos_mean,
        oos_stdev=signal.oos_stdev,
        n_oos_windows=signal.n_oos_windows,
        median_oos_after_costs=signal.median_oos_after_costs,
        pbo=signal.pbo,
        dsr_probability=signal.dsr_probability,
        purge_applied=signal.purge_applied,
        embargo_applied=signal.embargo_applied,
        cost_applied=signal.cost_applied,
        cost_model_id=signal.cost_model_id,
        regimes_complete=signal.regimes_complete,
        validation_mac=signal.validation_mac,
        issue_mac=signal.issue_mac,
        report_sha256=signal.report_sha256,
        admission_mac=signal.admission_mac,
    )


def _admission_body(signal: LiveSignal) -> dict[str, object]:
    return {
        "signal_id": signal.signal_id,
        "hypothesis_id": signal.hypothesis_id,
        "config_id": signal.config_id,
        "trial_id": signal.trial_id,
        "instrument": signal.instrument,
        "family_id": signal.family_id,
        "cluster_id": signal.cluster_id,
        "base_quantity": signal.base_quantity,
        "base_price": signal.base_price,
        "base_notional": signal.base_notional,
        "oos_values": list(signal.oos_values),
        "oos_mean": signal.oos_mean,
        "oos_stdev": signal.oos_stdev,
        "n_oos_windows": signal.n_oos_windows,
        "median_oos_after_costs": signal.median_oos_after_costs,
        "pbo": signal.pbo,
        "dsr_probability": signal.dsr_probability,
        "purge_applied": signal.purge_applied,
        "embargo_applied": signal.embargo_applied,
        "cost_applied": signal.cost_applied,
        "cost_model_id": signal.cost_model_id,
        "regimes_complete": signal.regimes_complete,
        "validation_mac": signal.validation_mac,
        "issue_mac": signal.issue_mac,
        "report_sha256": signal.report_sha256,
    }


def _oos_values(verified: Mapping[str, object]) -> tuple[float, ...]:
    oos = as_object_dict(mapping_get(verified, "oos_distribution"))
    if oos is None:
        raise ContinuityRefused("OOS distribution missing")
    raw = as_object_list(mapping_get(oos, "values"))
    if raw is None:
        raise ContinuityRefused("OOS values missing")
    values: list[float] = []
    for item in raw:
        if isinstance(item, bool) or not isinstance(item, (int, float)) or not math.isfinite(float(item)):
            raise ContinuityRefused("non-finite OOS value")
        values.append(float(item))
    return tuple(values)


def _required_float(payload: dict[str, object] | None, key: str) -> float:
    if payload is None:
        raise ContinuityRefused(f"{key} missing")
    value = mapping_get(payload, key)
    if isinstance(value, bool) or not isinstance(value, (int, float)) or not math.isfinite(float(value)):
        raise ContinuityRefused(f"{key} missing")
    return float(value)


def _instrument(value: object) -> Instrument:
    if not isinstance(value, str):
        raise ContinuityRefused("instrument missing")
    mapped = _INSTRUMENTS.get(value.strip().upper())
    if mapped is None:
        raise ContinuityRefused(f"unknown instrument {value!r}")
    return mapped

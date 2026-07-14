"""Runtime twin oversight — fail-closed guards + autonomy telemetry for production runtime."""

from __future__ import annotations

import json
import logging
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from lumina_core.config_loader import ConfigLoader
from lumina_core.logging_utils import (
    compute_autonomy_snapshot,
    record_autonomy_metrics_monitoring,
    resolve_monitoring_state_dir,
)

logger = logging.getLogger("lumina.runtime.twin_oversight")

_TWIN_DECISION_TOPIC = "evolution.twin.decision"
_AUTO_CONF_THRESHOLD = 0.80
_TWIN_MODEL_PATH = Path("state/approval_twin_model.json")
_TWIN_REGISTRY_PATH = Path("state/steve_values_registry.jsonl")
_OVERSIGHT_JSONL = "monitoring_runtime_oversight.jsonl"
_APPROVAL_DAEMON_MARKERS = ("approval", "twin", "evolution")


@dataclass(slots=True)
class AutonomySnapshot:
    decisions_total: int = 0
    auto_approved_total: int = 0
    veto_total: int = 0
    deferred_total: int = 0
    autonomy_level_pct: float = 0.0
    # Perfect Birth Phase KPIs (twin accuracy vs Steve + shadow alignment)
    twin_steve_agreement_pct: float = 0.0
    shadow_twin_alignment_pct: float = 0.0
    samples_for_twin_accuracy: int = 0

    def to_dict(self) -> dict[str, Any]:
        d = {
            "decisions_total": self.decisions_total,
            "auto_approved_total": self.auto_approved_total,
            "veto_total": self.veto_total,
            "deferred_total": self.deferred_total,
            "autonomy_level_pct": round(self.autonomy_level_pct, 2),
        }
        if self.twin_steve_agreement_pct or self.samples_for_twin_accuracy:
            d["twin_steve_agreement_pct"] = round(self.twin_steve_agreement_pct, 2)
            d["samples_for_twin_accuracy"] = int(self.samples_for_twin_accuracy)
        if self.shadow_twin_alignment_pct:
            d["shadow_twin_alignment_pct"] = round(self.shadow_twin_alignment_pct, 2)
        return d


@dataclass(slots=True)
class OversightVerdict:
    allowed: bool
    reason: str = ""
    blocked_fields: list[str] = field(default_factory=list)


def _classify_outcome(*, recommendation: bool, confidence: float, risk_flags: list[str]) -> str:
    conf = float(confidence)
    risks = list(risk_flags or [])
    if conf >= _AUTO_CONF_THRESHOLD:
        if recommendation and not risks:
            return "auto_approved"
        if not recommendation:
            return "veto"
    return "deferred"


def _snapshot_from_dict(raw: dict[str, Any]) -> AutonomySnapshot:
    snap = AutonomySnapshot(
        decisions_total=int(raw.get("decisions_total", 0) or 0),
        auto_approved_total=int(raw.get("auto_approved_total", 0) or 0),
        veto_total=int(raw.get("veto_total", 0) or 0),
        deferred_total=int(raw.get("deferred_total", 0) or 0),
        autonomy_level_pct=float(raw.get("autonomy_level_pct", 0.0) or 0.0),
        twin_steve_agreement_pct=float(raw.get("twin_steve_agreement_pct", 0.0) or 0.0),
        shadow_twin_alignment_pct=float(raw.get("shadow_twin_alignment_pct", 0.0) or 0.0),
        samples_for_twin_accuracy=int(raw.get("samples_for_twin_accuracy", 0) or 0),
    )
    return snap


class RuntimeTwinOversight:
    """Cross-cutting twin oversight for config reload, headless, and recovery."""

    _instance: RuntimeTwinOversight | None = None

    def __init__(self) -> None:
        self._mode = "sim"
        self._bus_token: str | None = None
        self._live_decisions: list[dict[str, Any]] = []

    @classmethod
    def get(cls) -> RuntimeTwinOversight:
        if cls._instance is None:
            cls._instance = cls()
        return cls._instance

    @classmethod
    def reset_for_tests(cls) -> None:
        cls._instance = None

    def bind(self, event_bus: Any, *, mode: str) -> str:
        self._mode = _norm_mode(mode)
        if self._bus_token is not None:
            try:
                event_bus.unsubscribe(self._bus_token)
            except Exception:
                logger.debug("twin_oversight.unsubscribe_failed", exc_info=True)
            self._bus_token = None

        def _on_decision(event: Any) -> None:
            payload = getattr(event, "payload", None) or event
            if isinstance(payload, dict):
                self._record_live_decision(payload)

        self._bus_token = event_bus.subscribe(_TWIN_DECISION_TOPIC, _on_decision)
        return self._bus_token

    def _record_live_decision(self, payload: dict[str, Any]) -> None:
        rec = bool(payload.get("recommendation", False))
        conf = float(payload.get("confidence", payload.get("score", 0.0)) or 0.0)
        risks = list(payload.get("risk_flags", []) or [])
        entry = {
            "timestamp": payload.get("timestamp") or time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
            "recommendation": rec,
            "confidence": conf,
            "risk_flags": risks,
            "outcome": _classify_outcome(recommendation=rec, confidence=conf, risk_flags=risks),
        }
        self._live_decisions.append(entry)
        if len(self._live_decisions) > 500:
            self._live_decisions = self._live_decisions[-500:]

    def twin_artifacts_healthy(self) -> tuple[bool, str]:
        model = _resolve_state_path(_TWIN_MODEL_PATH)
        registry = _resolve_state_path(_TWIN_REGISTRY_PATH)
        if not model.is_file():
            return False, f"missing_twin_model:{model}"
        if not registry.is_file():
            return False, f"missing_twin_registry:{registry}"
        try:
            mstat = model.stat()
            if mstat.st_size < 2:
                return False, "twin_model_too_small"
            raw = json.loads(model.read_text(encoding="utf-8"))
            if not isinstance(raw, dict) or "threshold" not in raw:
                return False, "invalid_twin_model_schema"
        except Exception:
            return False, "unreadable_twin_model"
        return True, "ok"

    def autonomy_level_pct(self) -> float:
        """Convenience: current autonomy level (% decisions auto-approved by twin)."""
        return self.snapshot().autonomy_level_pct

    def snapshot(self, *, window_hours: int = 24) -> AutonomySnapshot:
        raw = compute_autonomy_snapshot(window_hours=window_hours)
        snap = _snapshot_from_dict(raw)

        # Enrich with latest twin Steve accuracy (from training jsonl rollups) for Perfect Birth KPI
        try:
            acc_path = resolve_monitoring_state_dir() / "monitoring_twin_training.jsonl"
            if acc_path.exists():
                lines = acc_path.read_text(encoding="utf-8").strip().splitlines()
                for line in reversed(lines[-20:]):  # recent last
                    try:
                        row = json.loads(line.strip())
                        if "twin_steve_agreement_pct" in row:
                            snap.twin_steve_agreement_pct = float(row.get("twin_steve_agreement_pct", 0.0) or 0.0)
                            snap.samples_for_twin_accuracy = int(row.get("samples", 0) or 0)
                            break
                    except Exception:
                        continue
        except Exception:
            pass

        # Shadow alignment % best-effort (count recent aligned true / total in dedicated log)
        try:
            align_path = resolve_monitoring_state_dir() / "monitoring_shadow_twin_alignment.jsonl"
            if align_path.exists():
                lines = align_path.read_text(encoding="utf-8").strip().splitlines()[-50:]
                aligned = 0
                tot = 0
                for line in lines:
                    try:
                        r = json.loads(line.strip())
                        tot += 1
                        if bool(r.get("aligned")):
                            aligned += 1
                    except Exception:
                        continue
                if tot > 0:
                    snap.shadow_twin_alignment_pct = round((aligned / tot) * 100.0, 2)
        except Exception:
            pass

        return snap

    def audit_config_reload(
        self,
        changed_sections: list[str],
        new_cfg: dict[str, Any],
        *,
        mode: str,
    ) -> OversightVerdict:
        norm_mode = _norm_mode(mode)
        blocked: list[str] = []

        if _contains_auto_approve_real(new_cfg):
            blocked.append("auto_approve_real")

        if "evolution" in changed_sections or _evolution_section_touched(new_cfg):
            twin_section = _approval_twin_section(new_cfg)
            if twin_section and norm_mode == "real":
                threshold = twin_section.get("threshold")
                if threshold is not None:
                    try:
                        prior = ConfigLoader.section("evolution", "approval_twin", default={}) or {}
                        prior_thr = float((prior if isinstance(prior, dict) else {}).get("threshold", 0.8) or 0.8)
                        new_thr = float(threshold)
                        if new_thr < prior_thr:
                            blocked.append("approval_twin.threshold_decrease")
                    except (TypeError, ValueError):
                        blocked.append("approval_twin.threshold_invalid")

        if blocked:
            return OversightVerdict(allowed=False, reason="twin_oversight_blocked", blocked_fields=blocked)
        return OversightVerdict(allowed=True)

    def record_runtime_event(self, kind: str, detail: dict[str, Any] | None = None) -> None:
        snap = self.snapshot()
        payload = {
            "timestamp": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
            "kind": str(kind),
            "mode": self._mode,
            "detail": dict(detail or {}),
            "autonomy_level_pct": round(snap.autonomy_level_pct, 2),
            "autonomy": snap.to_dict(),
        }
        path = resolve_monitoring_state_dir() / _OVERSIGHT_JSONL
        path.parent.mkdir(parents=True, exist_ok=True)
        with path.open("a", encoding="utf-8") as fh:
            fh.write(json.dumps(payload, ensure_ascii=True, sort_keys=True) + "\n")

    def maybe_record_autonomy_rollup(self, *, min_interval_s: float = 3600.0) -> None:
        """Hourly autonomy rollup for monitoring_autonomy_metrics.jsonl."""
        path = resolve_monitoring_state_dir() / "monitoring_autonomy_metrics.jsonl"
        now = time.time()
        last_ts = 0.0
        if path.is_file():
            try:
                lines = path.read_text(encoding="utf-8").strip().splitlines()
                if lines:
                    last = json.loads(lines[-1])
                    ts = str(last.get("timestamp", ""))
                    if ts:
                        from datetime import datetime, timezone

                        last_ts = datetime.strptime(ts, "%Y-%m-%dT%H:%M:%SZ").replace(tzinfo=timezone.utc).timestamp()
            except Exception:
                last_ts = 0.0
        if now - last_ts >= min_interval_s:
            record_autonomy_metrics_monitoring(self.snapshot().to_dict())

    def is_approval_related_daemon(self, daemon_name: str) -> bool:
        name = str(daemon_name or "").strip().lower()
        return any(marker in name for marker in _APPROVAL_DAEMON_MARKERS)

    def twin_oversight_status(self) -> dict[str, Any]:
        healthy, reason = self.twin_artifacts_healthy()
        snap = self.snapshot()
        status = {
            "artifacts_healthy": healthy,
            "artifacts_reason": reason,
            "autonomy_level_pct": round(snap.autonomy_level_pct, 2),
            **snap.to_dict(),
        }
        # Explicit Perfect Birth Phase fields (for dashboards / runbook queries)
        status.setdefault("twin_steve_agreement_pct", round(snap.twin_steve_agreement_pct, 2))
        status.setdefault("shadow_twin_alignment_pct", round(snap.shadow_twin_alignment_pct, 2))
        return status


def _norm_mode(mode: str) -> str:
    m = str(mode or "").strip().lower()
    if m in {"live"}:
        return "real"
    return m if m else "sim"


def _resolve_state_path(rel: Path) -> Path:
    return resolve_monitoring_state_dir().parent / rel if str(rel).startswith("state") else rel


def _approval_twin_section(cfg: dict[str, Any]) -> dict[str, Any] | None:
    evo = cfg.get("evolution")
    if not isinstance(evo, dict):
        return None
    twin = evo.get("approval_twin")
    return twin if isinstance(twin, dict) else None


def _evolution_section_touched(cfg: dict[str, Any]) -> bool:
    return isinstance(cfg.get("evolution"), dict)


def _contains_auto_approve_real(cfg: dict[str, Any]) -> bool:
    def _walk(obj: Any) -> bool:
        if isinstance(obj, dict):
            if obj.get("auto_approve_real") is True:
                return True
            return any(_walk(v) for v in obj.values())
        if isinstance(obj, list):
            return any(_walk(v) for v in obj)
        return False

    return _walk(cfg)


__all__ = [
    "AutonomySnapshot",
    "OversightVerdict",
    "RuntimeTwinOversight",
]
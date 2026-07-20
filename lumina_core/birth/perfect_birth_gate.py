"""Perfect Birth conjunction gate — SSOT unlock for Phase 2 Autonomy (Slice C).

Fail-closed. A hollow ``perfect_birth_complete.flag`` is not enough when evidence
sidecar is required: declaration must pass measurable KPIs from the birth runbook §8–9.
"""

from __future__ import annotations

import json
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from lumina_core.logging_utils import get_logger, resolve_monitoring_state_dir

logger = get_logger("lumina.birth.perfect_birth_gate")

DEFAULT_FLAG_REL = "state/perfect_birth_complete.flag"
DEFAULT_EVIDENCE_REL = "state/perfect_birth_complete.json"
MILESTONE_ID = "perfect_birth_autonomy_proven"


@dataclass(frozen=True, slots=True)
class PerfectBirthThresholds:
    min_twin_steve_agreement_pct: float = 80.0
    min_autonomous_recovery_rate_pct: float = 85.0
    min_auto_approved_pct: float = 60.0
    min_shadow_twin_alignment_pct: float = 75.0
    min_samples_labels: int = 30
    min_recovery_attempts: int = 8
    max_constitution_violations: int = 0
    require_certificate: bool = True
    max_terminal_notify_recent: int = 0

    @classmethod
    def from_curriculum_cfg(cls, cfg: Any | None) -> PerfectBirthThresholds:
        if cfg is None:
            return cls()
        return cls(
            min_twin_steve_agreement_pct=float(
                getattr(cfg, "perfect_birth_min_twin_steve_agreement_pct", 80.0) or 80.0
            ),
            min_autonomous_recovery_rate_pct=float(
                getattr(cfg, "perfect_birth_min_autonomous_recovery_rate_pct", 85.0) or 85.0
            ),
            min_auto_approved_pct=float(
                getattr(cfg, "perfect_birth_min_auto_approved_pct", 60.0) or 60.0
            ),
            min_shadow_twin_alignment_pct=float(
                getattr(cfg, "perfect_birth_min_shadow_twin_alignment_pct", 75.0) or 75.0
            ),
            min_samples_labels=int(getattr(cfg, "perfect_birth_min_samples_labels", 30) or 30),
            min_recovery_attempts=int(
                getattr(cfg, "perfect_birth_min_recovery_attempts", 8) or 8
            ),
        )


@dataclass(frozen=True, slots=True)
class PerfectBirthKpis:
    """Measured inputs for the conjunction (explicit / injected or gathered)."""

    certificate_valid: bool = False
    constitution_violations: int = 0
    twin_steve_agreement_pct: float = 0.0
    twin_samples: int = 0
    autonomous_recovery_rate_pct: float = 0.0
    autonomous_recovery_attempts: int = 0
    auto_approved_pct: float = 0.0
    auto_approved_decisions: int = 0
    shadow_twin_alignment_pct: float = 0.0
    shadow_samples: int = 0
    terminal_notify_recent: int = 0
    source_notes: dict[str, str] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(frozen=True, slots=True)
class PerfectBirthConjunctionResult:
    passed: bool
    failures: list[str] = field(default_factory=list)
    metrics: dict[str, Any] = field(default_factory=dict)
    thresholds: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return {
            "passed": self.passed,
            "failures": list(self.failures),
            "metrics": dict(self.metrics),
            "thresholds": dict(self.thresholds),
        }


def evaluate_perfect_birth_conjunction(
    kpis: PerfectBirthKpis,
    *,
    thresholds: PerfectBirthThresholds | None = None,
) -> PerfectBirthConjunctionResult:
    """Pure conjunction: ALL runbook §8–9 measurable gates must pass."""
    thr = thresholds or PerfectBirthThresholds()
    failures: list[str] = []

    if thr.require_certificate and not kpis.certificate_valid:
        failures.append("certificate_invalid_or_missing")

    if int(kpis.constitution_violations) > int(thr.max_constitution_violations):
        failures.append(
            f"constitution_violations={kpis.constitution_violations} "
            f"> {thr.max_constitution_violations}"
        )

    if kpis.twin_samples < thr.min_samples_labels:
        failures.append(
            f"twin_samples={kpis.twin_samples} < {thr.min_samples_labels}"
        )
    elif kpis.twin_steve_agreement_pct < thr.min_twin_steve_agreement_pct:
        failures.append(
            f"twin_steve_agreement_pct={kpis.twin_steve_agreement_pct:.1f} "
            f"< {thr.min_twin_steve_agreement_pct}"
        )

    if kpis.autonomous_recovery_attempts < thr.min_recovery_attempts:
        failures.append(
            f"recovery_attempts={kpis.autonomous_recovery_attempts} "
            f"< {thr.min_recovery_attempts}"
        )
    elif kpis.autonomous_recovery_rate_pct < thr.min_autonomous_recovery_rate_pct:
        failures.append(
            f"autonomous_recovery_rate_pct={kpis.autonomous_recovery_rate_pct:.1f} "
            f"< {thr.min_autonomous_recovery_rate_pct}"
        )

    # Auto-approve: runbook requires ≥20 decisions in window + ≥60% auto-approved
    min_decisions = 20
    if kpis.auto_approved_decisions < min_decisions:
        failures.append(
            f"auto_approved_decisions={kpis.auto_approved_decisions} < {min_decisions}"
        )
    elif kpis.auto_approved_pct < thr.min_auto_approved_pct:
        failures.append(
            f"auto_approved_pct={kpis.auto_approved_pct:.1f} < {thr.min_auto_approved_pct}"
        )

    min_shadow = 5
    if kpis.shadow_samples < min_shadow:
        failures.append(f"shadow_samples={kpis.shadow_samples} < {min_shadow}")
    elif kpis.shadow_twin_alignment_pct < thr.min_shadow_twin_alignment_pct:
        failures.append(
            f"shadow_twin_alignment_pct={kpis.shadow_twin_alignment_pct:.1f} "
            f"< {thr.min_shadow_twin_alignment_pct}"
        )

    if int(kpis.terminal_notify_recent) > int(thr.max_terminal_notify_recent):
        failures.append(
            f"terminal_notify_recent={kpis.terminal_notify_recent} "
            f"> {thr.max_terminal_notify_recent}"
        )

    metrics = kpis.to_dict()
    thr_dict = asdict(thr)
    return PerfectBirthConjunctionResult(
        passed=len(failures) == 0,
        failures=failures,
        metrics=metrics,
        thresholds=thr_dict,
    )


def _read_json(path: Path) -> dict[str, Any]:
    try:
        if path.is_file():
            raw = json.loads(path.read_text(encoding="utf-8"))
            return raw if isinstance(raw, dict) else {}
    except Exception:
        pass
    return {}


def _tail_jsonl(path: Path, limit: int = 50) -> list[dict[str, Any]]:
    if not path.is_file():
        return []
    try:
        lines = path.read_text(encoding="utf-8").strip().splitlines()
    except OSError:
        return []
    rows: list[dict[str, Any]] = []
    for raw in lines[-max(1, limit) :]:
        raw = raw.strip()
        if not raw:
            continue
        try:
            row = json.loads(raw)
        except Exception:
            continue
        if isinstance(row, dict):
            rows.append(row)
    return rows


def gather_perfect_birth_kpis(
    workspace_root: Path | str | None = None,
) -> PerfectBirthKpis:
    """Best-effort KPI gather from state/monitoring files (fail-soft → zeros)."""
    root = Path(workspace_root) if workspace_root else Path.cwd()
    state = root / "state"
    notes: dict[str, str] = {}

    # Certificate
    cert_path = state / "lumina_birth_certificate.json"
    cert = _read_json(cert_path)
    certificate_valid = False
    constitution_violations = 0
    if cert:
        constitution_violations = int(
            cert.get("constitution_violations", cert.get("violations", 0)) or 0
        )
        # Accept common validity signals
        if cert.get("valid") is True or cert.get("status") in {"issued", "valid", "ok"}:
            certificate_valid = True
        elif cert.get("certificate_id") or cert.get("issued_at") or cert.get("stage"):
            certificate_valid = constitution_violations == 0
        notes["certificate"] = str(cert_path)
    else:
        notes["certificate"] = "missing"

    # Progress recovery metrics
    progress = _read_json(state / "lumina_birth_progress.json")
    recovery_rate = float(
        progress.get("autonomous_recovery_rate_pct")
        or progress.get("autonomous_recovery_rate")
        or 0.0
    )
    recovery_attempts = int(
        progress.get("autonomous_recovery_attempts")
        or progress.get("recovery_attempts")
        or 0
    )
    if progress.get("constitution_violations") is not None:
        constitution_violations = max(
            constitution_violations, int(progress.get("constitution_violations") or 0)
        )
    notes["progress"] = "state/lumina_birth_progress.json"

    # Twin agreement from training jsonl
    mon = resolve_monitoring_state_dir()
    twin_rows = _tail_jsonl(mon / "monitoring_twin_training.jsonl", limit=30)
    twin_pct = 0.0
    twin_samples = 0
    for row in reversed(twin_rows):
        if "twin_steve_agreement_pct" in row:
            twin_pct = float(row.get("twin_steve_agreement_pct", 0.0) or 0.0)
            twin_samples = int(row.get("samples", 0) or 0)
            break
    notes["twin_training"] = str(mon / "monitoring_twin_training.jsonl")

    # Autonomy auto-approve from compute_autonomy_snapshot
    auto_pct = 0.0
    auto_decisions = 0
    try:
        from lumina_core.logging_utils import compute_autonomy_snapshot

        snap = compute_autonomy_snapshot(window_hours=24)
        auto_pct = float(snap.get("autonomy_level_pct", 0.0) or 0.0)
        auto_decisions = int(snap.get("decisions_total", 0) or 0)
        notes["autonomy"] = "monitoring_twin_decisions.jsonl"
    except Exception:
        notes["autonomy"] = "unavailable"

    # Shadow alignment
    align_rows = _tail_jsonl(mon / "monitoring_shadow_twin_alignment.jsonl", limit=50)
    shadow_samples = len(align_rows)
    shadow_aligned = sum(1 for r in align_rows if bool(r.get("aligned")))
    shadow_pct = (
        round((shadow_aligned / shadow_samples) * 100.0, 2) if shadow_samples else 0.0
    )
    notes["shadow"] = str(mon / "monitoring_shadow_twin_alignment.jsonl")

    # Terminal notify heuristic from progress / autonomy metrics
    terminal_notify = int(progress.get("terminal_notify_count_recent", 0) or 0)
    if progress.get("needs_attention"):
        terminal_notify = max(terminal_notify, 1)

    return PerfectBirthKpis(
        certificate_valid=certificate_valid,
        constitution_violations=constitution_violations,
        twin_steve_agreement_pct=twin_pct,
        twin_samples=twin_samples,
        autonomous_recovery_rate_pct=recovery_rate,
        autonomous_recovery_attempts=recovery_attempts,
        auto_approved_pct=auto_pct,
        auto_approved_decisions=auto_decisions,
        shadow_twin_alignment_pct=shadow_pct,
        shadow_samples=shadow_samples,
        terminal_notify_recent=terminal_notify,
        source_notes=notes,
    )


def evidence_path_for_flag(flag_path: Path | str) -> Path:
    p = Path(flag_path)
    if p.suffix == ".flag":
        return p.with_suffix(".json")
    return p.parent / "perfect_birth_complete.json"


def load_perfect_birth_evidence(flag_path: Path | str | None = None) -> dict[str, Any] | None:
    path = evidence_path_for_flag(flag_path or DEFAULT_FLAG_REL)
    data = _read_json(path)
    return data if data else None


def perfect_birth_unlock_valid(
    *,
    flag_path: Path | str = DEFAULT_FLAG_REL,
    require_evidence: bool = True,
    recheck_kpis: PerfectBirthKpis | None = None,
    thresholds: PerfectBirthThresholds | None = None,
) -> tuple[bool, str]:
    """Whether Phase 2 may treat Perfect Birth as unlocked.

    - Flag must exist.
    - If require_evidence: sidecar JSON must exist with passed=true.
    - If recheck_kpis provided: live conjunction must still pass (stale evidence fail-closed).
    """
    flag = Path(flag_path)
    try:
        if not flag.is_file():
            return False, f"missing_flag:{flag}"
    except OSError as exc:
        return False, f"flag_unreadable:{exc}"

    if require_evidence:
        evidence = load_perfect_birth_evidence(flag)
        if not evidence:
            return False, "missing_evidence_sidecar"
        if not bool(evidence.get("passed")):
            return False, "evidence_not_passed"

    if recheck_kpis is not None:
        result = evaluate_perfect_birth_conjunction(recheck_kpis, thresholds=thresholds)
        if not result.passed:
            return False, "recheck_failed:" + ",".join(result.failures[:3])

    return True, "ok"


def declare_perfect_birth(
    workspace_root: Path | str | None = None,
    *,
    thresholds: PerfectBirthThresholds | None = None,
    kpis: PerfectBirthKpis | None = None,
    force: bool = False,
    flag_rel: str = DEFAULT_FLAG_REL,
    record_maturity: bool = True,
) -> dict[str, Any]:
    """Evaluate conjunction; write flag + evidence only if passed (or force with audit).

    Returns declaration result dict. Never enables Phase 2 flags.
    """
    root = Path(workspace_root) if workspace_root else Path.cwd()
    thr = thresholds or PerfectBirthThresholds()
    measured = kpis or gather_perfect_birth_kpis(root)
    result = evaluate_perfect_birth_conjunction(measured, thresholds=thr)

    flag_path = Path(flag_rel)
    if not flag_path.is_absolute():
        flag_path = root / flag_rel
    evidence_path = evidence_path_for_flag(flag_path)

    declared = False
    reason = "conjunction_failed"
    if result.passed:
        declared = True
        reason = "conjunction_passed"
    elif force:
        declared = True
        reason = "forced_override"

    payload = {
        "declared_at": datetime.now(timezone.utc).isoformat(),
        "passed": bool(result.passed),
        "declared": declared,
        "reason": reason,
        "forced": bool(force and not result.passed),
        "failures": list(result.failures),
        "metrics": result.metrics,
        "thresholds": result.thresholds,
        "flag_path": str(flag_path),
        "evidence_path": str(evidence_path),
        "source": "declare_perfect_birth",
    }

    if declared:
        flag_path.parent.mkdir(parents=True, exist_ok=True)
        flag_path.write_text(
            datetime.now(timezone.utc).isoformat() + "\n",
            encoding="utf-8",
        )
        evidence_path.write_text(
            json.dumps(payload, ensure_ascii=True, indent=2, sort_keys=True),
            encoding="utf-8",
        )
        if record_maturity and result.passed:
            try:
                from lumina_core.maturity.milestone_hooks import try_record_milestone

                try_record_milestone(
                    root,
                    MILESTONE_ID,
                    metadata={
                        "source": "declare_perfect_birth",
                        "twin_steve_agreement_pct": measured.twin_steve_agreement_pct,
                        "autonomous_recovery_rate_pct": measured.autonomous_recovery_rate_pct,
                    },
                )
            except Exception as exc:
                logger.debug("perfect_birth.maturity_hook_failed: %s", exc)
        logger.info(
            "perfect_birth.declared passed=%s forced=%s path=%s",
            result.passed,
            force and not result.passed,
            flag_path,
        )
    else:
        # Write evidence of failed attempt for operator visibility (no flag)
        try:
            evidence_path.parent.mkdir(parents=True, exist_ok=True)
            fail_path = evidence_path.with_name("perfect_birth_last_attempt.json")
            fail_path.write_text(
                json.dumps(payload, ensure_ascii=True, indent=2, sort_keys=True),
                encoding="utf-8",
            )
            payload["last_attempt_path"] = str(fail_path)
        except Exception:
            pass
        logger.warning(
            "perfect_birth.declare_blocked failures=%s",
            result.failures,
        )

    return payload


__all__ = [
    "DEFAULT_EVIDENCE_REL",
    "DEFAULT_FLAG_REL",
    "MILESTONE_ID",
    "PerfectBirthConjunctionResult",
    "PerfectBirthKpis",
    "PerfectBirthThresholds",
    "declare_perfect_birth",
    "evaluate_perfect_birth_conjunction",
    "evidence_path_for_flag",
    "gather_perfect_birth_kpis",
    "load_perfect_birth_evidence",
    "perfect_birth_unlock_valid",
]

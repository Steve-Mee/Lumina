"""Four-market D13 audit with the pre-registered drift-aware null. No templates."""

from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path

from lumina_research.cycles.daily import unique_sessions
from lumina_research.cycles.data import MIN_BARS, DataStatus, LoadedTape, discover_data
from lumina_research.cycles.null_model import (
    NULL_CALIBRATED_POSITIVE_SHARE,
    classify_null_a2,
    default_block_seeds,
    default_null_seeds,
    fail_closed_a2_cap,
)
from lumina_research.cycles.p2_cycle import market_series, pin_tape, prepare_for_purpose
from lumina_research.cycles.positive_control import (
    ControlReport,
    PositiveControlFailed,
    run_controls,
)
from lumina_research.cycles.wf_sizes import walk_forward_sizes
from lumina_research.proof.runner import DEFAULT_REPORTS
from lumina_research.validation.audit import utc_now_iso
from lumina_research.validation.cost_model import COST_MODEL_VERSION
from lumina_research.validation.trial_registry import TrialRegistry
from lumina_research.validation.walk_forward import WalkForwardError

_REPO = Path(__file__).resolve().parents[2]
AUDIT_ROOTS: tuple[str, ...] = ("MES", "MNQ", "ES", "NQ")
ACTION5_REQUIRED: frozenset[str] = frozenset({"MES", "MNQ", "ES"})
JSON_NAME = "phase5_p2_multiseed_null_audit.json"
MD_NAME = "phase5_p2_multiseed_null_audit.md"
PREREG_SHA_NAME = "phase5_p2_multiseed_null_preregister_2026-10-29.md"


@dataclass(frozen=True, slots=True)
class RootAudit:
    root: str
    accepted: bool
    planted_detected: bool
    reliable: bool
    n_a2: int
    n_seeds: int
    a2_share: float
    median_oos_planted: float
    median_of_null_medians: float
    n_days: int
    is_size: int
    oos_size: int
    n_trials: int
    nq_closed: bool
    note: str
    report: ControlReport | None
    borderline: bool = False
    status: str = "unreliable"
    exact_a2: str = ""
    n_edge: int = 0
    exact_edge: str = ""
    a2_status: str = "unreliable"


@dataclass(frozen=True, slots=True)
class NullAuditCycle:
    roots: tuple[RootAudit, ...]
    n_trials_total: int
    n_trials_by_root: dict[str, int]
    method_ready: bool
    nq_closed: bool
    json_path: Path
    md_path: Path
    data: DataStatus


def run_null_audit(
    *,
    work_dir: Path,
    report_dir: Path = DEFAULT_REPORTS,
    data_dir: Path | None = None,
    repo_root: Path | None = None,
) -> NullAuditCycle:
    """Apply the locked 32-seed null to every mounted PIT tape. No strategy run."""
    root = repo_root if repo_root is not None else _REPO
    work_dir.mkdir(parents=True, exist_ok=True)
    report_dir.mkdir(parents=True, exist_ok=True)
    status = discover_data(repo_root=root, data_dir=data_dir)
    registry = TrialRegistry(work_dir / "null_audit.jsonl")
    rows: list[RootAudit] = []
    for name in AUDIT_ROOTS:
        tape = _tape(status, name)
        if tape is None:
            rows.append(
                RootAudit(
                    root=name,
                    accepted=False,
                    planted_detected=False,
                    reliable=False,
                    n_a2=0,
                    n_seeds=len(default_null_seeds()),
                    a2_share=0.0,
                    median_oos_planted=float("nan"),
                    median_of_null_medians=float("nan"),
                    n_days=0,
                    is_size=0,
                    oos_size=0,
                    n_trials=0,
                    nq_closed=name == "NQ",
                    note="no usable PIT tape",
                    report=None,
                )
            )
            continue
        prepared = prepare_for_purpose(pin_tape(tape), purpose="gate")
        n_days = len(unique_sessions(prepared.session_dates))
        try:
            is_size, oos_size, _formed = walk_forward_sizes(n_days)
        except WalkForwardError as exc:
            rows.append(
                RootAudit(
                    root=name,
                    accepted=False,
                    planted_detected=False,
                    reliable=False,
                    n_a2=0,
                    n_seeds=len(default_null_seeds()),
                    a2_share=0.0,
                    median_oos_planted=float("nan"),
                    median_of_null_medians=float("nan"),
                    n_days=n_days,
                    is_size=0,
                    oos_size=0,
                    n_trials=0,
                    nq_closed=name == "NQ",
                    note=f"walk-forward refused: {exc}",
                    report=None,
                )
            )
            continue
        n_before = int(registry.n_trials)
        try:
            report = run_controls(
                prepared={name: prepared},
                registry=registry,
                audit_path=registry.audit_path,
                is_size=is_size,
                oos_size=oos_size,
                market_returns=market_series(prepared),
                n_days=n_days,
                null_seeds=default_null_seeds(),
                block_seeds=default_block_seeds(),
                fail_closed=False,
            )
            rows.append(_from_report(name, report, n_days, is_size, oos_size, int(registry.n_trials) - n_before))
        except PositiveControlFailed as exc:
            failed = exc.report
            if failed is None:
                rows.append(
                    RootAudit(
                        root=name,
                        accepted=False,
                        planted_detected=False,
                        reliable=False,
                        n_a2=0,
                        n_seeds=len(default_null_seeds()),
                        a2_share=0.0,
                        median_oos_planted=float("nan"),
                        median_of_null_medians=float("nan"),
                        n_days=n_days,
                        is_size=is_size,
                        oos_size=oos_size,
                        n_trials=int(registry.n_trials) - n_before,
                        nq_closed=True if name == "NQ" else False,
                        note=str(exc),
                        report=None,
                    )
                )
            else:
                rows.append(
                    _from_report(
                        name,
                        failed,
                        n_days,
                        is_size,
                        oos_size,
                        int(registry.n_trials) - n_before,
                        note=str(exc),
                    )
                )
    method_ready = all(item.accepted for item in rows if item.root in ACTION5_REQUIRED)
    n_by_root = {item.root: item.n_trials for item in rows}
    cycle = NullAuditCycle(
        roots=tuple(rows),
        n_trials_total=int(registry.n_trials),
        n_trials_by_root=n_by_root,
        method_ready=method_ready,
        nq_closed=True,
        json_path=report_dir / JSON_NAME,
        md_path=report_dir / MD_NAME,
        data=status,
    )
    _write_reports(cycle, report_dir=report_dir, repo_root=root)
    return cycle


def _tape(status: DataStatus, instrument: str) -> LoadedTape | None:
    for item in status.tapes:
        if item.instrument == instrument and len(item.bars) >= MIN_BARS:
            return item
    return None


def _from_report(
    root: str,
    report: ControlReport,
    n_days: int,
    is_size: int,
    oos_size: int,
    n_trials: int,
    note: str = "",
) -> RootAudit:
    audit = report.null_audit
    n_seeds = audit.n_seeds if audit is not None else len(default_null_seeds())
    n_a2 = audit.n_a2 if audit is not None else 0
    classified = classify_null_a2(n_a2, n_seeds)
    reliable = bool(audit.reliable) if audit is not None else classified.reliable
    share = float(audit.a2_share) if audit is not None else classified.n_a2 / float(n_seeds)
    median_null = float(audit.median_of_medians) if audit is not None else float("nan")
    text = note or ("accepted" if report.accepted else "planted miss or null unreliable")
    return RootAudit(
        root=root,
        accepted=bool(report.accepted),
        planted_detected=bool(report.positive.detected),
        reliable=reliable,
        n_a2=n_a2,
        n_seeds=n_seeds,
        a2_share=share,
        median_oos_planted=float(report.positive.median_oos),
        median_of_null_medians=median_null,
        n_days=n_days,
        is_size=is_size,
        oos_size=oos_size,
        n_trials=n_trials,
        nq_closed=root == "NQ",
        note=text,
        report=report,
        borderline=bool(audit.borderline) if audit is not None else classified.borderline,
        status=audit.status if audit is not None else classified.status,
        exact_a2=audit.exact_a2 if audit is not None else classified.exact,
        n_edge=int(audit.n_edge) if audit is not None else 0,
        exact_edge=audit.exact_edge if audit is not None else classified.exact,
        a2_status=audit.a2_status if audit is not None else classified.status,
    )


def _write_reports(cycle: NullAuditCycle, *, report_dir: Path, repo_root: Path) -> None:
    prereg = repo_root / "experiments" / "reports" / PREREG_SHA_NAME
    payload = {
        "generated_at": utc_now_iso(),
        "cost_model_version": COST_MODEL_VERSION,
        "preregister": PREREG_SHA_NAME,
        "preregister_present": prereg.is_file(),
        "n_seeds": len(default_null_seeds()),
        "null_seeds": list(default_null_seeds()),
        "block_seeds": list(default_block_seeds()),
        "max_a2": fail_closed_a2_cap(len(default_null_seeds())),
        "fail_closed_cap": fail_closed_a2_cap(len(default_null_seeds())),
        "borderline_count": fail_closed_a2_cap(len(default_null_seeds())) + 1,
        "calibrated_positive_share": NULL_CALIBRATED_POSITIVE_SHARE,
        "method_ready": cycle.method_ready,
        "nq_templates_closed": True,
        "nq_closed_until_new_preregister": True,
        "n_trials_total": cycle.n_trials_total,
        "n_trials_by_root": cycle.n_trials_by_root,
        "holdout_pin": "2026-01-28T23:00:00Z",
        "holdout_opened": False,
        "roots": [
            {
                "root": item.root,
                "accepted": item.accepted,
                "planted_detected": item.planted_detected,
                "reliable": item.reliable,
                "borderline": item.borderline,
                "status": item.status,
                "exact_a2": item.exact_a2 or f"{item.n_a2}/{item.n_seeds}",
                "n_edge": item.n_edge,
                "exact_edge": item.exact_edge or f"{item.n_edge}/{item.n_seeds}",
                "a2_status": item.a2_status,
                "a2_within_ten_pct": (
                    item.report.null_audit.a2_within_ten_pct
                    if item.report is not None and item.report.null_audit is not None
                    else False
                ),
                "n_a2": item.n_a2,
                "n_seeds": item.n_seeds,
                "a2_share": item.a2_share,
                "median_oos_planted": item.median_oos_planted,
                "median_of_null_medians": item.median_of_null_medians,
                "n_days": item.n_days,
                "is_size": item.is_size,
                "oos_size": item.oos_size,
                "n_trials": item.n_trials,
                "note": item.note,
                "drift_seeds": (
                    [
                        {
                            "seed": seed.seed,
                            "detected": seed.detected,
                            "false_edge": seed.false_edge,
                            "median_oos": seed.median_oos,
                            "pct_positive": seed.pct_positive,
                            "dsr": seed.dsr,
                        }
                        for seed in item.report.null_audit.drift_seeds
                    ]
                    if item.report is not None and item.report.null_audit is not None
                    else []
                ),
                "block_seeds": (
                    [
                        {
                            "seed": seed.seed,
                            "detected": seed.detected,
                            "false_edge": seed.false_edge,
                            "median_oos": seed.median_oos,
                            "pct_positive": seed.pct_positive,
                            "dsr": seed.dsr,
                        }
                        for seed in item.report.null_audit.block_seeds
                    ]
                    if item.report is not None and item.report.null_audit is not None
                    else []
                ),
            }
            for item in cycle.roots
        ],
    }
    cycle.json_path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    lines = [
        "# P2 drift-aware multi-seed null audit (2026-10-29)",
        "",
        f"- generated_at: `{payload['generated_at']}`",
        f"- pre-register: `{PREREG_SHA_NAME}`",
        f"- CostModel: `{COST_MODEL_VERSION}`",
        f"- seeds: `{len(default_null_seeds())}` (`{default_null_seeds()[0]}`..`{default_null_seeds()[-1]}`)",
        f"- A2 diagnostic cap: `{fail_closed_a2_cap(len(default_null_seeds()))}` of {len(default_null_seeds())} (not majority 16/32)",
        f"- strict fail-at: `{fail_closed_a2_cap(len(default_null_seeds())) + 1}` of {len(default_null_seeds())} (4 is fail)",
        f"- calibrated false-edge: A2 and +OOS ≥ `{NULL_CALIBRATED_POSITIVE_SHARE:.3f}` (7/8); gate uses `n_edge`",
        f"- method_ready (MES/MNQ/ES planted+calibrated-null): `{cycle.method_ready}`",
        "- NQ templates: **closed** until a new team-approved pre-register",
        "- Week-block ISO calendar-week shuffle: extra reported check, not a gate",
        f"- n_trials total: `{cycle.n_trials_total}`",
        "- holdout pin `2026-01-28T23:00:00Z`: closed",
        "",
        "## Per root",
        "",
        "| root | planted | A2 exact | A2 status | edge exact | edge status | planted median OOS | null median-of-medians | days | IS/OOS | N | note |",
        "|---|---|---|---|---|---|---|---|---|---|---|---|",
    ]
    for item in cycle.roots:
        lines.append(
            "| {root} | {planted} | {exact_a2} | {a2_status} | {exact_edge} | {edge_status} | {pmed:.6g} | {nmed:.6g} | {days} | {is_size}/{oos} | {n} | {note} |".format(
                root=item.root,
                planted=item.planted_detected,
                exact_a2=item.exact_a2 or f"{item.n_a2}/{item.n_seeds}",
                a2_status=item.a2_status or "unreliable",
                exact_edge=item.exact_edge or f"{item.n_edge}/{item.n_seeds}",
                edge_status=item.status or ("reliable" if item.reliable else "unreliable"),
                pmed=item.median_oos_planted,
                nmed=item.median_of_null_medians,
                days=item.n_days,
                is_size=item.is_size,
                oos=item.oos_size,
                n=item.n_trials,
                note=item.note,
            )
        )
    lines.extend(["", "## Trials", ""])
    for root, count in cycle.n_trials_by_root.items():
        lines.append(f"- {root}: `{count}`")
    lines.append(f"- total: `{cycle.n_trials_total}`")
    lines.extend(
        [
            "",
            "## Fail-closed",
            "",
            "- No seed reroll, no config respec.",
            "- Always report exact `n_a2/32` (A2 diagnostic) and exact `n_edge/32` (calibrated 7/8 gate).",
            "- Cycle stop: planted miss, calibrated `n_edge` unreliable (`>=4/32`), or planted does not beat median-of-medians.",
            "- `4/32` is fail (18:17). Exact `n_a2` remains diagnostic.",
            "- Raw A2 is not the cycle stop: P(A2)≈0.36 on 8 fair windows.",
            "- NQ stays closed until a new pre-register is explicitly approved. Null reliability alone does not open NQ.",
            "- Week-block is extra; it does not decide pass/fail.",
            "",
        ]
    )
    cycle.md_path.write_text("\n".join(lines) + "\n", encoding="utf-8")

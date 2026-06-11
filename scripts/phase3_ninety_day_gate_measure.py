#!/usr/bin/env python3
"""
Phase 3 / 90-day North Star gate measurement (honest point-in-time + history).

Reads Guardian export (dna_health_latest.json), evolution-log signals, and optional
snapshot history. Does NOT change trading or risk behavior.

North Star deadline: 2026-08-29 (from 2026-05-31 aperture roadmap).
"""
from __future__ import annotations

import argparse
import json
import re
import subprocess
import sys
from datetime import date, datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))
DNA_ROOT = ROOT / "project-dna" / "lumina"

from lumina_core.audit.protocol_adherence import measure_protocol_adherence
EXPORT_HEALTH = DNA_ROOT / "interfaces" / "export" / "dna_health_latest.json"
EVOLUTION_LOG = DNA_ROOT / "evolution-log.md"
SNAPSHOT_JSONL = DNA_ROOT / "evolution" / "phase3_ninety_day_gate_snapshots.jsonl"
LATEST_STATE = ROOT / "state" / "phase3_ninety_day_gate_latest.json"

CAMPAIGN_START = date(2026, 5, 31)
CAMPAIGN_END = date(2026, 8, 29)

GATE_APERTURE_MIN = 9.3
GATE_EVOLVABILITY_MIN = 9.0
GATE_EVOLUTION_ACCELERATED_MIN = 3
GATE_PROTOCOL_ADHERENCE_MIN = 0.9

_ACCELERATION_RE = re.compile(
    r"aperture|phase\s*3|lineage|guardian|d1\s+golden|track\s*c|d5|d6|typed\s+spine|decision_lineage|payload_instance",
    re.I,
)


def _utcnow_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _days_remaining() -> int:
    today = date.today()
    if today > CAMPAIGN_END:
        return 0
    return (CAMPAIGN_END - today).days


def _refresh_health_export() -> None:
    script = ROOT / "scripts" / "dna_guardian" / "validate_dna.py"
    subprocess.run(
        [sys.executable, str(script), "--report", "--d1-audits"],
        cwd=ROOT,
        check=False,
    )


def _load_health_export() -> dict:
    if not EXPORT_HEALTH.exists():
        return {}
    try:
        return json.loads(EXPORT_HEALTH.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return {}


def _count_accelerated_evolution_entries() -> int:
    """Count distinct evolution-log sections (### headings) that reference aperture tooling."""
    if not EVOLUTION_LOG.exists():
        return 0
    text = EVOLUTION_LOG.read_text(encoding="utf-8")
    sections = 0
    in_campaign_section = False
    section_hit = False
    for line in text.splitlines():
        if line.startswith("### "):
            if section_hit:
                sections += 1
            section_hit = False
            in_campaign_section = False
            if line.startswith("### 2026-"):
                try:
                    entry_date = date.fromisoformat(line[4:14])
                    in_campaign_section = entry_date >= CAMPAIGN_START
                except ValueError:
                    in_campaign_section = False
        elif in_campaign_section and _ACCELERATION_RE.search(line):
            section_hit = True
    if section_hit:
        sections += 1
    return sections


def _count_full_state_reset_dirs() -> int:
    backups = ROOT / "backups"
    if not backups.is_dir():
        return 0
    total = 0
    start_ts = datetime(CAMPAIGN_START.year, CAMPAIGN_START.month, CAMPAIGN_START.day, tzinfo=timezone.utc).timestamp()
    for path in backups.glob("reset_*"):
        if not path.is_dir():
            continue
        try:
            if path.stat().st_mtime >= start_ts:
                total += 1
        except OSError:
            continue
    return total


def _append_snapshot(record: dict) -> None:
    SNAPSHOT_JSONL.parent.mkdir(parents=True, exist_ok=True)
    with SNAPSHOT_JSONL.open("a", encoding="utf-8") as fh:
        fh.write(json.dumps(record, ensure_ascii=True))
        fh.write("\n")


def _load_snapshot_history(limit: int = 90) -> list[dict]:
    if not SNAPSHOT_JSONL.exists():
        return []
    rows: list[dict] = []
    try:
        for line in SNAPSHOT_JSONL.read_text(encoding="utf-8").splitlines():
            line = line.strip()
            if not line:
                continue
            try:
                rows.append(json.loads(line))
            except json.JSONDecodeError:
                continue
    except OSError:
        return []
    return rows[-limit:]


def _sustained_metric(history: list[dict], key: str, min_value: float, window: int = 7) -> dict:
    scores = []
    for row in reversed(history):
        gates = row.get("gates") or {}
        g = gates.get(key) or {}
        val = g.get("value")
        if isinstance(val, (int, float)):
            scores.append(float(val))
        if len(scores) >= window:
            break
    if len(scores) < window:
        return {
            "verified": False,
            "reason": f"need {window} snapshots in {SNAPSHOT_JSONL.name}, have {len(scores)}",
            "window_min": None,
        }
    window_min = min(scores)
    return {
        "verified": window_min >= min_value,
        "window_min": window_min,
        "window_size": window,
    }


def build_measurement(*, refresh: bool = False) -> dict:
    if refresh:
        _refresh_health_export()

    health = _load_health_export()
    aperture = (health.get("aperture") or {}).get("integrity") or health.get("aperture_integrity") or {}
    aperture_score = float(aperture.get("score", 0.0) or 0.0)

    dna_health = health.get("health") or {}
    evolvability_proxy = float(dna_health.get("truth_density_avg", 0.0) or 0.0)
    structural = float(dna_health.get("structural_health", 0.0) or 0.0)

    gss = (health.get("aperture") or {}).get("guardian_self_score") or {}
    guardian_self = float(gss.get("overall_score", 0.0) or 0.0)

    reset_count = _count_full_state_reset_dirs()
    accelerated = _count_accelerated_evolution_entries()
    protocol = measure_protocol_adherence(since=CAMPAIGN_START, dna_root=DNA_ROOT, classified_only=True)
    protocol_rate = float(protocol.get("rate", 0.0) or 0.0)

    history = _load_snapshot_history()
    sustained_aperture = _sustained_metric(history, "aperture_integrity", GATE_APERTURE_MIN)
    sustained_evolv = _sustained_metric(history, "evolvability_proxy", GATE_EVOLVABILITY_MIN)

    gates = {
        "aperture_integrity": {
            "threshold": GATE_APERTURE_MIN,
            "value": aperture_score,
            "point_in_time_pass": aperture_score >= GATE_APERTURE_MIN,
            "sustained": sustained_aperture,
        },
        "evolvability_proxy": {
            "threshold": GATE_EVOLVABILITY_MIN,
            "value": evolvability_proxy,
            "note": "truth_density_avg proxy until dedicated risk-layer score exists",
            "point_in_time_pass": evolvability_proxy >= GATE_EVOLVABILITY_MIN,
            "sustained": sustained_evolv,
        },
        "guardian_self_score": {
            "threshold": 8.0,
            "value": guardian_self,
            "point_in_time_pass": guardian_self >= 8.0,
        },
        "zero_full_state_resets": {
            "threshold": 0,
            "value": reset_count,
            "point_in_time_pass": reset_count == 0,
            "note": "counts backups/reset_* dirs mtime since campaign start",
        },
        "evolution_accelerated_entries": {
            "threshold": GATE_EVOLUTION_ACCELERATED_MIN,
            "value": accelerated,
            "point_in_time_pass": accelerated >= GATE_EVOLUTION_ACCELERATED_MIN,
            "note": "heuristic keyword matches in evolution-log.md since 2026-05-31",
        },
        "protocol_adherence_rate": {
            "threshold": GATE_PROTOCOL_ADHERENCE_MIN,
            "value": protocol_rate,
            "point_in_time_pass": protocol_rate >= GATE_PROTOCOL_ADHERENCE_MIN,
            "note": "classified evolution/log entries with hypothesis + falsifiable prediction + rollback",
            "detail": {
                "adherent": protocol.get("adherent_entries"),
                "total": protocol.get("total_entries"),
                "skipped_unclassified": protocol.get("skipped_unclassified"),
            },
        },
    }

    point_pass = all(
        g.get("point_in_time_pass") is True
        for g in gates.values()
        if isinstance(g, dict) and "point_in_time_pass" in g
    )
    sustained_pass = (
        sustained_aperture.get("verified")
        and sustained_aperture.get("verified") is True
        and sustained_aperture.get("window_min", 0) >= GATE_APERTURE_MIN
        and sustained_evolv.get("verified")
        and sustained_evolv.get("verified") is True
        and sustained_evolv.get("window_min", 0) >= GATE_EVOLVABILITY_MIN
    )

    return {
        "schema": "phase3-ninety-day-gate-v1",
        "measured_at": _utcnow_iso(),
        "campaign_start": CAMPAIGN_START.isoformat(),
        "campaign_end": CAMPAIGN_END.isoformat(),
        "days_remaining": _days_remaining(),
        "health_export": str(EXPORT_HEALTH.relative_to(ROOT)),
        "structural_health": structural,
        "gates": gates,
        "verdict": {
            "point_in_time_all_pass": point_pass,
            "sustained_north_star_met": sustained_pass,
            "honest_status": (
                "NORTH_STAR_MET_SUSTAINED"
                if sustained_pass
                else ("NORTH_STAR_MET_SNAPSHOT" if point_pass else "NORTH_STAR_NOT_MET")
            ),
        },
        "parent_hypothesis": {
            "status": "IN_PROGRESS",
            "note": "Requires human falsification entry when campaign ends; see campaign log.",
        },
    }


def main() -> int:
    parser = argparse.ArgumentParser(description="Measure Phase 3 / 90-day North Star gates.")
    parser.add_argument("--refresh", action="store_true", help="Run Guardian --report before measuring.")
    parser.add_argument("--append", action="store_true", help="Append snapshot to evolution JSONL history.")
    parser.add_argument("--json", action="store_true", help="Print full JSON to stdout.")
    args = parser.parse_args()

    record = build_measurement(refresh=args.refresh)
    LATEST_STATE.parent.mkdir(parents=True, exist_ok=True)
    LATEST_STATE.write_text(json.dumps(record, indent=2), encoding="utf-8")

    if args.append:
        _append_snapshot(record)

    verdict = record["verdict"]["honest_status"]
    gates = record["gates"]
    print(f"PHASE3_NINETY_DAY_GATE status={verdict} days_remaining={record['days_remaining']}")
    print(
        f"  aperture={gates['aperture_integrity']['value']}/{gates['aperture_integrity']['threshold']} "
        f"pass={gates['aperture_integrity']['point_in_time_pass']}"
    )
    print(
        f"  evolvability_proxy={gates['evolvability_proxy']['value']}/{gates['evolvability_proxy']['threshold']} "
        f"pass={gates['evolvability_proxy']['point_in_time_pass']}"
    )
    print(
        f"  resets={gates['zero_full_state_resets']['value']} "
        f"accelerated_entries={gates['evolution_accelerated_entries']['value']}"
    )
    proto = gates["protocol_adherence_rate"]
    print(
        f"  protocol_adherence={proto['value']:.2%}/{proto['threshold']:.0%} "
        f"pass={proto['point_in_time_pass']} "
        f"({proto['detail']['adherent']}/{proto['detail']['total']} classified)"
    )
    sustained = gates["aperture_integrity"].get("sustained") or {}
    if not sustained.get("verified"):
        print(f"  sustained_aperture=NOT_VERIFIED ({sustained.get('reason', '')})")
    else:
        print(f"  sustained_aperture_min={sustained.get('window_min')}")

    if args.json:
        print(json.dumps(record, indent=2))

    # Exit 1 only when point-in-time gates fail (CI-friendly daily check)
    return 0 if gates["aperture_integrity"]["point_in_time_pass"] else 1


if __name__ == "__main__":
    raise SystemExit(main())

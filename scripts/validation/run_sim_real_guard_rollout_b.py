from __future__ import annotations

import argparse
import json
import math
import os
import sqlite3
import subprocess
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


def _parse_duration_minutes(raw: str) -> float:
    text = str(raw).strip().lower()
    if text.endswith("ms"):
        return float(text[:-2]) / 60000.0
    if text.endswith("m"):
        return float(text[:-1])
    if text.endswith("h"):
        return float(text[:-1]) * 60.0
    return float(text)


def _read_json(path: Path) -> dict[str, Any]:
    if not path.exists():
        return {}
    try:
        payload = json.loads(path.read_text(encoding="utf-8", errors="replace"))
    except json.JSONDecodeError:
        return {}
    return payload if isinstance(payload, dict) else {}


def _read_jsonl(path: Path) -> list[dict[str, Any]]:
    if not path.exists():
        return []
    rows: list[dict[str, Any]] = []
    for raw in path.read_text(encoding="utf-8", errors="replace").splitlines():
        line = raw.strip()
        if not line:
            continue
        try:
            item = json.loads(line)
        except json.JSONDecodeError:
            continue
        if isinstance(item, dict):
            rows.append(item)
    return rows


def _count_advisory_reasons(log_path: Path) -> dict[str, int]:
    counts: Counter[str] = Counter()
    if not log_path.exists():
        return {}
    for raw in log_path.read_text(encoding="utf-8", errors="replace").splitlines():
        if "RISK_ADVISORY,mode=sim," not in raw:
            continue
        reason_marker = "reason="
        if reason_marker not in raw:
            counts["unknown"] += 1
            continue
        reason = raw.split(reason_marker, 1)[1].strip()
        if "," in reason:
            reason = reason.split(",", 1)[0].strip()
        counts[reason or "unknown"] += 1
    return dict(counts)


def _latest_counter_values(db_path: Path, metric_name: str) -> list[dict[str, Any]]:
    if not db_path.exists():
        return []
    con = sqlite3.connect(str(db_path))
    try:
        rows = con.execute(
            """
            SELECT labels, value, ts
            FROM metrics
            WHERE name = ?
            ORDER BY ts ASC
            """,
            (metric_name,),
        ).fetchall()
    finally:
        con.close()
    latest_by_labels: dict[str, dict[str, Any]] = {}
    for labels_raw, value, ts in rows:
        try:
            labels = json.loads(labels_raw) if labels_raw else {}
        except json.JSONDecodeError:
            labels = {}
        key = json.dumps(labels, sort_keys=True)
        latest_by_labels[key] = {
            "labels": labels if isinstance(labels, dict) else {},
            "value": float(value or 0.0),
            "ts": float(ts or 0.0),
        }
    return list(latest_by_labels.values())


def _sum_metric(db_path: Path, metric_name: str, expected_labels: dict[str, str]) -> float:
    total = 0.0
    for row in _latest_counter_values(db_path, metric_name):
        labels = {str(k): str(v) for k, v in row.get("labels", {}).items()}
        if any(labels.get(str(k)) != str(v) for k, v in expected_labels.items()):
            continue
        total += float(row.get("value", 0.0) or 0.0)
    return total


def _metric_by_reason(db_path: Path, metric_name: str, mode: str) -> dict[str, int]:
    result: dict[str, int] = {}
    for row in _latest_counter_values(db_path, metric_name):
        labels = {str(k): str(v) for k, v in row.get("labels", {}).items()}
        if labels.get("mode") != mode:
            continue
        reason = labels.get("reason", "unknown")
        result[reason] = int(round(float(row.get("value", 0.0) or 0.0)))
    return result


def _quantile(values: list[float], q: float) -> float:
    if not values:
        return 0.0
    ordered = sorted(values)
    idx = max(0, min(len(ordered) - 1, int(math.ceil(len(ordered) * q)) - 1))
    return float(ordered[idx])


def _build_window_report(control_root: Path, candidate_root: Path, window_label: str, duration: str) -> dict[str, Any]:
    control_summary = _read_json(control_root / "state" / "last_run_summary.json")
    candidate_summary = _read_json(candidate_root / "state" / "last_run_summary.json")
    candidate_status = _read_json(candidate_root / "state" / "trade_reconciler_status.json")
    candidate_audit = _read_jsonl(candidate_root / "logs" / "trade_fill_audit.jsonl")
    control_log_path = control_root / "logs" / "lumina_full_log.csv"
    control_advisories = _count_advisory_reasons(control_log_path)

    candidate_metrics_db = candidate_root / "state" / "metrics.db"
    candidate_guard_reasons = _metric_by_reason(candidate_metrics_db, "lumina_mode_guard_block_total", "sim_real_guard")
    candidate_force_close_count = int(
        round(
            _sum_metric(
                candidate_metrics_db,
                "lumina_mode_eod_force_close_total",
                {"mode": "sim_real_guard"},
            )
        )
    )
    candidate_parity_drift = _sum_metric(
        candidate_metrics_db,
        "lumina_mode_parity_drift_total",
        {"baseline": "real", "candidate": "sim_real_guard"},
    )

    reconciled = [row for row in candidate_audit if str(row.get("event", "")).lower() == "reconciled"]
    timeout_snapshot = [row for row in reconciled if str(row.get("status", "")).lower() == "timeout_snapshot"]
    fill_latencies = [
        float(row.get("fill_latency_ms", 0.0) or 0.0) for row in reconciled if row.get("fill_latency_ms") is not None
    ]
    timeout_ratio = (len(timeout_snapshot) / len(reconciled)) if reconciled else 0.0
    p95_fill_latency = _quantile(fill_latencies, 0.95)

    unmatched_candidate_reasons = sorted(
        set(candidate_guard_reasons)
        - {f"risk_{key}" for key in control_advisories}
        - {"session_outside_trading_session", "session_rollover_window", "stale_contract", "broker_metadata_block"}
    )
    pending_count = int(candidate_status.get("pending_count", 0) or 0)
    last_error = str(candidate_status.get("last_error") or "").strip()

    checks = {
        "candidate_mode_correct": str(candidate_summary.get("mode", "")).lower() == "sim_real_guard",
        "control_mode_correct": str(control_summary.get("mode", "")).lower() == "sim",
        "timeout_ratio_within_slo": timeout_ratio <= 0.02,
        "candidate_p95_fill_latency_within_slo": p95_fill_latency <= 1500.0,
        "pending_count_bounded": pending_count <= 3,
        "last_error_clear": last_error == "",
        "candidate_reasons_explainable": len(unmatched_candidate_reasons) == 0,
    }
    passed = all(checks.values())

    return {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "window_label": window_label,
        "duration_minutes": _parse_duration_minutes(duration),
        "control_root": str(control_root),
        "candidate_root": str(candidate_root),
        "control": {
            "summary": control_summary,
            "risk_advisory_by_reason": control_advisories,
        },
        "candidate": {
            "summary": candidate_summary,
            "trade_reconciler_status": candidate_status,
            "guard_blocks_by_reason": candidate_guard_reasons,
            "force_close_count": candidate_force_close_count,
            "parity_drift_total": round(candidate_parity_drift, 6),
            "reconciled_count": len(reconciled),
            "timeout_snapshot_count": len(timeout_snapshot),
            "timeout_ratio": round(timeout_ratio, 6),
            "p95_fill_latency_ms": round(p95_fill_latency, 2),
            "pending_count": pending_count,
            "last_error": last_error,
        },
        "auto_checks": checks,
        "unmatched_candidate_reasons": unmatched_candidate_reasons,
        "decision": "GO_WINDOW" if passed else "NO_GO_WINDOW",
    }


def _resolve_python_executable(root: Path, explicit_python_exe: str) -> str:
    if explicit_python_exe:
        return explicit_python_exe
    return str(root / ".venv" / "Scripts" / "python.exe")


def _run_lane(
    root: Path, *, mode: str, duration: str, broker: str, extra_env: dict[str, str], summary_path: Path, python_exe: str
) -> subprocess.Popen[str]:
    env = os.environ.copy()
    env.update(extra_env)
    env["LUMINA_HEADLESS_SUMMARY_PATH"] = str(summary_path)
    env["PYTHONUNBUFFERED"] = "1"
    cmd = [
        _resolve_python_executable(root, python_exe),
        "-m",
        "lumina_launcher",
        "--headless",
        f"--mode={mode}",
        f"--duration={duration}",
        f"--broker={broker}",
    ]
    return subprocess.Popen(cmd, cwd=str(root), env=env, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)


def _persist_report(candidate_root: Path, report: dict[str, Any]) -> tuple[Path, Path]:
    out_dir = candidate_root / "state" / "validation" / "sim_real_guard_rollout_b"
    out_dir.mkdir(parents=True, exist_ok=True)
    stamp = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")
    report_path = out_dir / f"parity_window_{stamp}_{report['window_label'].replace(':', '-').replace(' ', '_')}.json"
    history_path = out_dir / "parity_history.jsonl"
    report_path.write_text(json.dumps(report, indent=2), encoding="utf-8")
    with history_path.open("a", encoding="utf-8") as handle:
        handle.write(json.dumps(report, ensure_ascii=False) + "\n")
    return report_path, history_path


def _read_history(path: Path) -> list[dict[str, Any]]:
    if not path.exists():
        return []
    rows: list[dict[str, Any]] = []
    for raw in path.read_text(encoding="utf-8", errors="replace").splitlines():
        line = raw.strip()
        if not line:
            continue
        try:
            item = json.loads(line)
        except json.JSONDecodeError:
            continue
        if isinstance(item, dict):
            rows.append(item)
    return rows


def _build_rollout_decision(history: list[dict[str, Any]]) -> dict[str, Any]:
    window_count = len(history)
    no_go_windows = [item for item in history if str(item.get("decision", "")) != "GO_WINDOW"]
    timeout_ratios = [float(item.get("candidate", {}).get("timeout_ratio", 0.0) or 0.0) for item in history]
    p95_latencies = [float(item.get("candidate", {}).get("p95_fill_latency_ms", 0.0) or 0.0) for item in history]
    force_close_counts = [int(item.get("candidate", {}).get("force_close_count", 0) or 0) for item in history]
    unresolved_errors = [item for item in history if str(item.get("candidate", {}).get("last_error", "")).strip()]
    explainability_failures = [item for item in history if item.get("unmatched_candidate_reasons")]

    enough_windows = window_count >= 15
    ready = (
        enough_windows
        and not no_go_windows
        and max(timeout_ratios or [0.0]) <= 0.02
        and max(p95_latencies or [0.0]) <= 1500.0
        and not unresolved_errors
        and not explainability_failures
    )

    return {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "window_count": window_count,
        "required_window_count": 15,
        "max_timeout_ratio": round(max(timeout_ratios or [0.0]), 6),
        "max_p95_fill_latency_ms": round(max(p95_latencies or [0.0]), 2),
        "total_force_close_events": sum(force_close_counts),
        "no_go_window_count": len(no_go_windows),
        "unresolved_error_window_count": len(unresolved_errors),
        "explainability_failure_window_count": len(explainability_failures),
        "ready_for_rollout_c": ready,
        "decision": "GO_TO_ROLLOUT_C"
        if ready
        else ("REPEAT_ROLLOUT_B" if enough_windows else "ROLL_OUT_B_IN_PROGRESS"),
    }


def main() -> int:
    parser = argparse.ArgumentParser(description="Automate one SIM vs SIM_REAL_GUARD Rollout B validation window.")
    parser.add_argument("--control-root", required=True)
    parser.add_argument("--candidate-root", required=True)
    parser.add_argument("--window-label", required=True, help="Example: D1_09-30_10-00")
    parser.add_argument("--duration", default="30m")
    parser.add_argument("--broker", choices=["paper", "live"], default="live")
    parser.add_argument("--crosstrade-token", default=os.getenv("CROSSTRADE_TOKEN", ""))
    parser.add_argument("--crosstrade-account", default=os.getenv("CROSSTRADE_ACCOUNT", ""))
    parser.add_argument("--python-exe", default=os.getenv("LUMINA_ROLLOUT_SHARED_PYTHON", ""))
    args = parser.parse_args()

    control_root = Path(args.control_root).resolve()
    candidate_root = Path(args.candidate_root).resolve()
    control_python = Path(_resolve_python_executable(control_root, args.python_exe))
    candidate_python = Path(_resolve_python_executable(candidate_root, args.python_exe))
    if not control_python.exists():
        raise SystemExit(f"Missing control venv: {control_root}")
    if not candidate_python.exists():
        raise SystemExit(f"Missing candidate venv: {candidate_root}")
    if args.broker == "live" and (not args.crosstrade_token or not args.crosstrade_account):
        raise SystemExit("Live broker rollout requires --crosstrade-token and --crosstrade-account")

    control_summary = control_root / "state" / "last_run_summary.json"
    candidate_summary = candidate_root / "state" / "last_run_summary.json"
    common_env = {
        "BROKER_BACKEND": args.broker,
        "CROSSTRADE_TOKEN": args.crosstrade_token,
        "CROSSTRADE_ACCOUNT": args.crosstrade_account,
        "TRADE_RECONCILER_STATUS_FILE": "state/trade_reconciler_status.json",
        "TRADE_RECONCILER_AUDIT_LOG": "logs/trade_fill_audit.jsonl",
    }

    control_proc = _run_lane(
        control_root,
        mode="sim",
        duration=args.duration,
        broker=args.broker,
        extra_env={
            **common_env,
            "TRADE_MODE": "sim",
            "TRADERLEAGUE_ACCOUNT_MODE": "sim",
            "ENABLE_SIM_REAL_GUARD": "false",
        },
        summary_path=control_summary,
        python_exe=args.python_exe,
    )
    candidate_proc = _run_lane(
        candidate_root,
        mode="sim_real_guard",
        duration=args.duration,
        broker=args.broker,
        extra_env={
            **common_env,
            "TRADE_MODE": "sim_real_guard",
            "TRADERLEAGUE_ACCOUNT_MODE": "sim",
            "ENABLE_SIM_REAL_GUARD": "true",
        },
        summary_path=candidate_summary,
        python_exe=args.python_exe,
    )

    control_stdout, control_stderr = control_proc.communicate()
    candidate_stdout, candidate_stderr = candidate_proc.communicate()
    if control_proc.returncode != 0:
        raise SystemExit(
            f"Control lane failed with code {control_proc.returncode}\nSTDOUT:\n{control_stdout}\nSTDERR:\n{control_stderr}"
        )
    if candidate_proc.returncode != 0:
        raise SystemExit(
            f"Candidate lane failed with code {candidate_proc.returncode}\nSTDOUT:\n{candidate_stdout}\nSTDERR:\n{candidate_stderr}"
        )

    report = _build_window_report(control_root, candidate_root, args.window_label, args.duration)
    report["lane_outputs"] = {
        "control_stdout_tail": control_stdout[-4000:],
        "control_stderr_tail": control_stderr[-4000:],
        "candidate_stdout_tail": candidate_stdout[-4000:],
        "candidate_stderr_tail": candidate_stderr[-4000:],
    }
    report_path, history_path = _persist_report(candidate_root, report)
    history = _read_history(history_path)
    decision = _build_rollout_decision(history)
    decision_path = history_path.parent / "rollout_b_decision.json"
    decision_path.write_text(json.dumps(decision, indent=2), encoding="utf-8")
    print(
        json.dumps(
            {
                "status": report["decision"],
                "report": str(report_path),
                "history": str(history_path),
                "rollout_decision": str(decision_path),
            },
            indent=2,
        )
    )
    return 0 if report["decision"] == "GO_WINDOW" else 2


if __name__ == "__main__":
    raise SystemExit(main())

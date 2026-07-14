"""Snapshot builders and workspace path helpers for monitoring endpoints."""

from __future__ import annotations

import json
import os
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


def metric_value(snapshot: dict[str, Any], key: str, default: float = 0.0) -> float:
    entry = snapshot.get(key) or {}
    try:
        return float(entry.get("value", default))
    except (TypeError, ValueError, AttributeError):
        return float(default)


def find_metric_entry(snapshot: dict[str, Any], prefix: str, **labels: str) -> dict[str, Any]:
    for key, entry in snapshot.items():
        if key == "_meta" or not key.startswith(prefix):
            continue
        entry_labels = entry.get("labels") if isinstance(entry, dict) else None
        if not isinstance(entry_labels, dict):
            continue
        if all(str(entry_labels.get(name)) == value for name, value in labels.items()):
            return entry
    return {}


def extract_regime_summary(snapshot: dict[str, Any]) -> dict[str, Any]:
    current_label = "UNKNOWN"
    current_risk_state = "UNKNOWN"
    current_active = find_metric_entry(snapshot, "lumina_regime_current")
    if current_active:
        labels = current_active.get("labels") or {}
        current_label = str(labels.get("regime", "UNKNOWN"))
        current_risk_state = str(labels.get("risk_state", "UNKNOWN"))

    regime_confidence = 0.0
    if current_label != "UNKNOWN":
        regime_confidence = metric_value(
            snapshot,
            f'lumina_regime_confidence{{regime="{current_label}"}}',
            0.0,
        )

    fast_path_weight = 0.0
    if current_label != "UNKNOWN":
        fast_path_weight = metric_value(
            snapshot,
            f'lumina_regime_fast_path_weight{{regime="{current_label}"}}',
            0.0,
        )

    high_risk_override_count = 0
    if current_label != "UNKNOWN":
        override_entry = find_metric_entry(
            snapshot,
            "lumina_regime_high_risk_overrides_total",
            regime=current_label,
        )
        try:
            high_risk_override_count = int(float((override_entry or {}).get("value", 0.0)))
        except (TypeError, ValueError):
            high_risk_override_count = 0

    return {
        "current_regime": current_label,
        "regime_risk_state": current_risk_state,
        "regime_confidence": regime_confidence,
        "fast_path_weight": fast_path_weight,
        "high_risk_override_count": high_risk_override_count,
    }


def repo_state_dir() -> Path:
    raw = os.getenv("LUMINA_STATE_DIR", "").strip()
    if raw:
        return Path(raw)
    return Path(__file__).resolve().parents[2] / "state"


def load_jsonl_file(path: Path, *, limit: int = 50) -> list[dict[str, Any]]:
    if not path.is_file():
        return []
    rows: list[dict[str, Any]] = []
    try:
        with path.open("r", encoding="utf-8") as fh:
            for raw in fh:
                line = raw.strip()
                if not line:
                    continue
                try:
                    parsed = json.loads(line)
                except json.JSONDecodeError:
                    continue
                if isinstance(parsed, dict):
                    rows.append(parsed)
    except OSError:
        return []
    return rows[-limit:]


def parse_iso(value: Any) -> datetime | None:
    if value is None:
        return None
    text = str(value).strip()
    if not text:
        return None
    try:
        if text.endswith("Z"):
            text = text[:-1] + "+00:00"
        return datetime.fromisoformat(text)
    except ValueError:
        return None


def load_json_file(path: Path) -> dict[str, Any] | None:
    if not path.is_file():
        return None
    try:
        parsed = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return None
    return parsed if isinstance(parsed, dict) else None


def journal_sim_dir() -> Path:
    repo = Path(__file__).resolve().parents[2]
    raw = os.getenv("LUMINA_JOURNAL_SIM_DIR", "").strip()
    if raw:
        return Path(raw)
    return repo / "journal" / "sim"


def latest_training_reports(*, limit: int = 10) -> list[dict[str, Any]]:
    journal_sim_dir_path = journal_sim_dir()
    reports: list[dict[str, Any]] = []
    if not journal_sim_dir_path.is_dir():
        return reports
    for path in sorted(
        list(journal_sim_dir_path.glob("lumina_birth_training_*.json"))
        + list(journal_sim_dir_path.glob("first_boot_training_*.json"))
    ):
        payload = load_json_file(path)
        if payload:
            payload["_run_type"] = "Background"
            payload["_path"] = str(path)
            reports.append(payload)
    for path in sorted(journal_sim_dir_path.glob("nightly_sim_*.json")):
        payload = load_json_file(path)
        if payload:
            ts = parse_iso(payload.get("timestamp"))
            run_type = "Weekend" if ts is not None and ts.weekday() >= 5 else "Daily Maintenance"
            payload["_run_type"] = run_type
            payload["_path"] = str(path)
            reports.append(payload)
    reports.sort(
        key=lambda row: parse_iso(row.get("timestamp"))
        or datetime.min.replace(tzinfo=timezone.utc),
        reverse=True,
    )
    return reports[:limit]


def monitoring_paths() -> dict[str, str]:
    """Resolve workspace paths used by Streamlit monitoring_dashboard parity."""
    repo = Path(__file__).resolve().parents[2]
    state = repo_state_dir()
    logs = repo / "logs"
    return {
        "workspace_root": str(repo),
        "state_dir": str(state),
        "logs_dir": str(logs),
        "structured_errors": str(logs / "structured_errors.jsonl"),
        "reasoning_latency": str(state / "monitoring_reasoning_latency.jsonl"),
        "model_load_times": str(state / "monitoring_model_load_times.jsonl"),
        "twin_training": str(state / "monitoring_twin_training.jsonl"),
        "twin_accuracy": str(state / "monitoring_twin_training.jsonl"),  # includes twin_steve_agreement_pct
        "autonomy_metrics": str(state / "monitoring_autonomy_metrics.jsonl"),
        "shadow_twin_alignment": str(state / "monitoring_shadow_twin_alignment.jsonl"),
        "first_boot_progress": str(state / "lumina_birth_progress.json"),
        "runtime_metrics": str(state / "monitoring_runtime_metrics.json"),
        "config_yaml": str(repo / "config.yaml"),
        "full_log": str(logs / "lumina_full_log.csv"),
    }
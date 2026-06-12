"""Headless evolution metrics loaders (no Streamlit)."""

from __future__ import annotations

import json
import logging
from pathlib import Path
from typing import Any

METRICS_PATH = Path("logs/evolution_metrics.jsonl")
SHADOW_STATE_PATH = Path("state/evolution_shadow_runs.json")
GENERATED_BIBLE_PATH = Path("state/lumina_bible_generated_strategies.jsonl")
ROLLOUT_HISTORY_PATH = Path("state/evolution_rollout_history.jsonl")


def load_evolution_metrics(path: Path = METRICS_PATH) -> list[dict[str, Any]]:
    if not path.exists():
        return []
    rows: list[dict[str, Any]] = []
    with path.open("r", encoding="utf-8") as handle:
        for raw in handle:
            raw = raw.strip()
            if not raw:
                continue
            try:
                parsed = json.loads(raw)
            except Exception:
                logging.exception("Failed parsing evolution metrics row")
                continue
            if isinstance(parsed, dict) and parsed.get("status") == "complete":
                rows.append(parsed)
    return rows


def load_shadow_runs(path: Path = SHADOW_STATE_PATH) -> dict[str, Any]:
    if not path.exists():
        return {}
    try:
        with path.open("r", encoding="utf-8") as handle:
            data = json.load(handle)
            return data if isinstance(data, dict) else {}
    except Exception:
        logging.exception("Failed loading shadow runs")
        return {}


def load_generated_strategies(path: Path = GENERATED_BIBLE_PATH) -> list[dict[str, Any]]:
    if not path.exists():
        return []
    rows: list[dict[str, Any]] = []
    with path.open("r", encoding="utf-8") as handle:
        for raw in handle:
            raw = raw.strip()
            if not raw:
                continue
            try:
                parsed = json.loads(raw)
            except Exception:
                logging.exception("Failed parsing generated strategy row")
                continue
            if isinstance(parsed, dict) and parsed.get("entry_type") == "generated_strategy_rule":
                rows.append(parsed)
    return rows


def load_rollout_history(path: Path = ROLLOUT_HISTORY_PATH) -> list[dict[str, Any]]:
    if not path.exists():
        return []
    rows: list[dict[str, Any]] = []
    with path.open("r", encoding="utf-8") as handle:
        for raw in handle:
            raw = raw.strip()
            if not raw:
                continue
            try:
                parsed = json.loads(raw)
            except Exception:
                logging.exception("Failed parsing rollout history row")
                continue
            if isinstance(parsed, dict) and parsed.get("event") == "rollout_decision":
                rows.append(parsed)
    return rows

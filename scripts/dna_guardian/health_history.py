"""DNA Guardian — health history, trends, and degradation detection."""

from __future__ import annotations

import json
from datetime import datetime, timezone

from structure import DNA_ROOT

def get_previous_health_score() -> float | None:
    """
    Finds the most recent previous DNA Guardian report and extracts its Health Score.
    Returns None if no previous report is found.
    """
    log_dir = DNA_ROOT / "evolution" / "log"
    if not log_dir.exists():
        return None

    # Find all guardian report files, sorted newest first
    reports = sorted(
        log_dir.glob("*-dna-guardian*.md"),
        key=lambda p: p.stat().st_mtime,
        reverse=True
    )

    for report_file in reports:
        try:
            content = report_file.read_text(encoding="utf-8")
            # Look for the DNA Health Score line
            for line in content.splitlines():
                if "DNA Health Score:" in line:
                    # Example: **DNA Health Score: 8.91/10**
                    import re
                    match = re.search(r"DNA Health Score:\s*([\d.]+)", line)
                    if match:
                        return float(match.group(1))
        except Exception:
            continue

    return None

HEALTH_HISTORY_FILE = DNA_ROOT / "evolution" / "dna_health_history.json"
MAX_HISTORY_ENTRIES = 20  # Keep last 20 scans for trend visualization


def update_health_history(current_score: float, truth_density_results: dict = None) -> list[dict]:
    """
    Appends the current Health Score (and optionally per-file scores) to the history.
    Returns the recent history.
    """
    history = []
    if HEALTH_HISTORY_FILE.exists():
        try:
            history = json.loads(HEALTH_HISTORY_FILE.read_text(encoding="utf-8"))
        except Exception:
            history = []

    entry = {
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "score": round(current_score, 2)
    }

    # New in v0.13.0: store per-file scores for degradation analysis
    if truth_density_results:
        entry["per_file"] = {
            path: round(data["score"], 2)
            for path, data in truth_density_results.items()
        }

    history.append(entry)

    # Keep only the most recent entries
    history = history[-MAX_HISTORY_ENTRIES:]

    # Ensure directory exists
    HEALTH_HISTORY_FILE.parent.mkdir(parents=True, exist_ok=True)
    HEALTH_HISTORY_FILE.write_text(json.dumps(history, indent=2), encoding="utf-8")

    return history


def get_short_trend_line(history: list[dict]) -> str:
    """
    Returns a compact trend string from the last few scores, e.g.:
    "8.2 → 8.5 → 8.7 → 8.9 → 8.91 (↑)"
    """
    if not history:
        return "No history yet"

    recent = history[-5:]  # Last 5 scans
    scores = [str(h["score"]) for h in recent]

    if len(recent) >= 2:
        last = recent[-1]["score"]
        prev = recent[-2]["score"]
        if last > prev + 0.05:
            arrow = "↑"
        elif last < prev - 0.05:
            arrow = "↓"
        else:
            arrow = "→"
    else:
        arrow = ""

    return " → ".join(scores) + (f" ({arrow})" if arrow else "")


def get_longer_trend_summary(history: list[dict]) -> str:
    """
    Returns a longer-term trend summary sentence.
    Example: "Health Score has a slightly declining trend over the last 8 scans (-0.4 total)."
    """
    if len(history) < 3:
        return "Not enough history for long-term trend yet."

    # Use up to last 8 scans for the summary
    recent = history[-8:]
    first_score = recent[0]["score"]
    last_score = recent[-1]["score"]
    total_change = round(last_score - first_score, 2)

    num_scans = len(recent)

    if abs(total_change) < 0.15:
        trend_word = "stable"
    elif total_change > 0:
        trend_word = "improving"
    else:
        trend_word = "declining"

    direction_word = "slightly " if abs(total_change) < 0.4 else ""
    if trend_word == "declining":
        direction_word = "slightly " if abs(total_change) > -0.4 else ""

    change_str = f"+{total_change}" if total_change > 0 else str(total_change)

    return f"Health Score has a {direction_word}{trend_word} trend over the last {num_scans} scans ({change_str} total)."

def detect_per_file_degradation(history: list[dict]) -> list[str]:
    """
    Detects files that have been the weakest (lowest Truth Density score)
    for multiple consecutive scans.
    Returns a list of warnings (e.g. "current-reality/evolutionary-debt.md was weakest for 4 consecutive scans").
    """
    if len(history) < 3:
        return []

    warnings = []
    recent = history[-5:]  # Look at last 5 scans

    # Count how often each file was the weakest in the recent window
    weakness_count = {}

    for entry in recent:
        per_file = entry.get("per_file", {})
        if not per_file:
            continue
        weakest = min(per_file.items(), key=lambda x: x[1])[0]
        weakness_count[weakest] = weakness_count.get(weakest, 0) + 1

    for file, count in weakness_count.items():
        if count >= 3:
            warnings.append(f"`{file}` was the weakest for {count} consecutive scans")

    return warnings


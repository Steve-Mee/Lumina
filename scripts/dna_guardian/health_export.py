"""DNA Guardian — recommendations, summaries, and health JSON export."""

from __future__ import annotations

import json
from typing import Any

from structure import DNA_ROOT

def generate_recommendation(report: dict[str, Any]) -> str:
    """
    Generates a short, actionable recommendation based on current results and trend.
    - Always points to the current lowest-scoring file.
    - Adds urgency language if the overall Health Score is declining.
    """
    td = report.get("truth_density", {})
    trend = report.get("trend")
    status = report.get("overall_status")

    if not td:
        return "No Truth Density data available for recommendations."

    # Find the file with the lowest Truth Density score
    lowest_file = min(td.items(), key=lambda x: x[1]["score"])
    lowest_path, lowest_result = lowest_file

    base_rec = f"Primary focus: Improve `{lowest_path}` (currently lowest at {lowest_result['score']}/10)."

    if trend and trend.get("direction") == "down":
        return f"Attention: DNA Health Score is declining. {base_rec}"
    elif status != "PASS":
        return f"Structural issues detected. {base_rec}"
    else:
        return base_rec


def generate_health_summary(report: dict[str, Any]) -> str:
    """
    Creates a very compact one-line summary for agent context.
    Format: "8.91/10 (Stable) — Focus: current-reality/evolutionary-debt.md (7.0)"
    Now also includes short historical trend when available (v0.11.0).
    """
    health = report.get("dna_health_score", {})
    trend = report.get("trend", {})
    rec = report.get("recommendation", "")

    score = health.get("score", "N/A")
    direction = trend.get("direction", "unknown") if trend else "unknown"

    # Extract the filename from the recommendation if possible
    focus_file = "N/A"
    if "Improve `" in rec:
        try:
            focus_file = rec.split("Improve `")[1].split("`")[0]
            # Shorten if needed
            if focus_file.count("/") > 1:
                focus_file = focus_file.split("/")[-1]
        except Exception:
            pass

    # Get the score of the focus file if available
    focus_score = ""
    if focus_file != "N/A":
        for path, data in report.get("truth_density", {}).items():
            if focus_file in path or path.endswith(focus_file):
                focus_score = f" ({data['score']})"
                break

    trend_str = {
        "up": "↑",
        "down": "↓",
        "stable": "→"
    }.get(direction, "?")

    base = f"{score}/10 ({trend_str}) — Focus: {focus_file}{focus_score}"

    # Add short historical trend line if available (new in v0.11.0)
    trend_line = report.get("health_trend_line")
    if trend_line:
        base = f"{base} | Trend: {trend_line}"

    # Add longer-term summary if available (new in v0.12.0)
    longer = report.get("longer_trend_summary")
    if longer:
        base = f"{base} | {longer}"

    return base


def generate_structured_health(report: dict[str, Any]) -> dict[str, Any]:
    """
    Produces a compact, versioned, machine-readable health payload
    for embedding in agent-context.md (v0.15.0).
    Deliberately minimal — only the fields an agent needs for decision making.
    """
    health = report.get("dna_health_score", {})
    trend = report.get("trend", {}) or {}
    rec = report.get("recommendation", "")

    # Extract focus file from recommendation (same logic as generate_health_summary)
    focus_file = None
    focus_score = None
    if "Improve `" in rec:
        try:
            focus_file = rec.split("Improve `")[1].split("`")[0]
            for path, data in report.get("truth_density", {}).items():
                if focus_file in path or path.endswith(focus_file):
                    focus_score = data.get("score")
                    break
        except Exception:
            pass

    payload = {
        "schema": "dna-health-v1",
        "last_updated": report.get("timestamp", "")[:19],
        "health_score": health.get("score"),
        "structural_health": health.get("components", {}).get("structural_health"),
        "truth_density_avg": health.get("components", {}).get("truth_density_avg"),
        "trend": {
            "direction": trend.get("direction", "unknown"),
            "delta": trend.get("delta", 0.0),
            "short_line": report.get("health_trend_line"),
        },
        "degradation_warnings": report.get("degradation_warnings", []),
        "focus": {
            "file": focus_file,
            "score": focus_score,
        },
        "overall_status": report.get("overall_status"),
    }
    return payload


def write_dna_health_latest(report: dict[str, Any]) -> str:
    """
    Writes a standalone, machine-readable snapshot of current DNA health
    to interfaces/export/dna_health_latest.json.
    This is the second slice of Increment 5 (v0.15 continuation).
    Agents and tools can load this file directly for structured data
    without parsing markdown.
    """
    export_dir = DNA_ROOT / "interfaces" / "export"
    export_dir.mkdir(parents=True, exist_ok=True)

    payload = {
        "schema": "dna-health-latest-v2-aperture",
        "generated_at": report.get("timestamp"),
        "tool_version": report.get("tool_version"),
        "dna_version": report.get("dna_version"),
        "health": generate_structured_health(report),
        "recommendation": report.get("recommendation"),
        "longer_trend_summary": report.get("longer_trend_summary"),
        "overall_status": report.get("overall_status"),
        "llm_review": report.get("llm_review"),  # experimental, may be absent
        "aperture": {
            "integrity": report.get("aperture_integrity"),
            "d5_capital_aperture": report.get("d5_capital_aperture"),
            "phase3_aperture_panel": report.get("phase3_aperture_panel"),
            "guardian_self_score": report.get("guardian_self_score"),
        },
    }

    target = export_dir / "dna_health_latest.json"
    target.write_text(json.dumps(payload, indent=2), encoding="utf-8")
    return str(target)


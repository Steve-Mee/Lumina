"""DNA Guardian — agent-context.md updater."""

from __future__ import annotations

import json
from typing import Any

from health_export import generate_health_summary, generate_structured_health
from structure import DNA_ROOT

def update_agent_context(report: dict[str, Any]) -> str:
    """
    Updates the 'Current DNA Health' section in interfaces/export/agent-context.md
    with the latest health data + a compact one-line summary at the top.
    As of v0.15.0 also appends a machine-readable structured JSON block
    (for agent-native consumption) while keeping the human text intact.
    """
    agent_context_path = DNA_ROOT / "interfaces" / "export" / "agent-context.md"
    if not agent_context_path.exists():
        return "agent-context.md not found — skipping update."

    content = agent_context_path.read_text(encoding="utf-8")

    health = report.get("dna_health_score", {})
    trend = report.get("trend", {})
    rec = report.get("recommendation", "No recommendation available.")

    health_score = f"{health.get('score', 'N/A')}/10"
    trend_info = "N/A"
    if trend:
        direction = trend.get("direction", "")
        delta = trend.get("delta", 0)
        if direction == "up":
            trend_info = f"↑ +{delta} (improving)"
        elif direction == "down":
            trend_info = f"↓ {delta} (declining — attention needed)"
        else:
            trend_info = "Stable"

    date_str = report["timestamp"][:10]

    # Generate the compact one-line summary (new in v0.10.0)
    summary = generate_health_summary(report)

    # Human-readable section (unchanged behavior)
    new_section = f"""## Current DNA Health (auto-updated by Guardian)
**Summary**: {summary}
**Health Score**: {health_score} (as of {date_str})
**Trend**: {trend_info}
**Recommended Focus**: {rec}"""

    # v0.15.0: machine-readable structured block (embedded for single-file agent loading)
    structured = generate_structured_health(report)
    structured_block = "## DNA Health (structured)\n```json\n" + json.dumps(structured, indent=2) + "\n```\n"

    # Marker-based replacement (human section + new structured section)
    start_marker = "## Current DNA Health (auto-updated by Guardian)"
    end_marker = "---\n\n**Einde compacte context.**"

    if start_marker in content and end_marker in content:
        before = content.split(start_marker)[0]
        after = content.split(end_marker)[1]
        new_content = before + new_section + "\n\n" + structured_block + "\n" + end_marker + after
        agent_context_path.write_text(new_content, encoding="utf-8")
        return str(agent_context_path)
    else:
        return "Could not find markers in agent-context.md — manual update needed."


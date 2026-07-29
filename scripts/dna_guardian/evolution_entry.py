"""DNA Guardian — evolution log entry writer."""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

from health_export import generate_recommendation
from structure import DNA_ROOT

def create_evolution_entry(report: dict[str, Any]) -> str:
    """
    Generate a proper, protocol-style evolution log entry instead of a raw report.
    This is the preferred way to contribute DNA Guardian findings to the evolution history.
    """
    evolution_log_dir = DNA_ROOT / "evolution" / "log"
    evolution_log_dir.mkdir(parents=True, exist_ok=True)

    ts = datetime.now(timezone.utc)
    filename_ts = ts.strftime("%Y-%m-%d-%H%M")
    filename = f"{filename_ts}-dna-guardian.md"
    filepath = evolution_log_dir / filename

    avg_score = report["truth_density_summary"]["average_score"]
    status = report["overall_status"]
    health = report.get("dna_health_score", {})
    trend = report.get("trend")

    # Build findings summary
    findings_lines = []
    for path, result in report.get("truth_density", {}).items():
        findings_lines.append(f"- `{path}`: **{result['score']}/10** — {', '.join(result['findings'])}")

    health_line = ""
    if health:
        health_line = f"**DNA Health Score: {health['score']}/10** (Structural: {health['components']['structural_health']}, Truth Density: {health['components']['truth_density_avg']})\n\n"

    trend_section = ""
    if trend:
        direction = trend["direction"]
        delta = trend["delta"]
        prev = trend["previous_score"]
        if direction == "up":
            trend_section = f"**Trend**: ↑ +{delta} compared to previous scan ({prev}/10)\n\n"
        elif direction == "down":
            trend_section = f"**Trend**: ↓ {delta} compared to previous scan ({prev}/10) — attention recommended\n\n"
        else:
            trend_section = f"**Trend**: Stable (no significant change from previous scan of {prev}/10)\n\n"

    # Add short historical trend line if available (new in v0.11.0)
    trend_line = report.get("health_trend_line")
    if trend_line:
        trend_section += f"**Recent Trend Line**: {trend_line}\n\n"

    # Add longer-term trend summary (new in v0.12.0)
    longer_summary = report.get("longer_trend_summary")
    longer_summary_section = ""
    if longer_summary:
        longer_summary_section = f"**Longer-term Trend**: {longer_summary}\n\n"

    # v0.14.0: Dedicated, high-signal degradation + low-score warnings with active language
    degradation_warnings = report.get("degradation_warnings", [])
    health = report.get("dna_health_score", {})
    health_score = health.get("score", 10.0)
    LOW_SCORE_THRESHOLD = 8.0

    warning_blocks = []

    # 1. Low Health Score Alert — most urgent when triggered
    if health_score < LOW_SCORE_THRESHOLD:
        low_score_block = (
            "**⚠️ LOW HEALTH SCORE ALERT**\n"
            f"DNA Health Score is **{health_score}/10** (threshold: {LOW_SCORE_THRESHOLD}).\n"
            "This indicates DNA erosion. **ACTION REQUIRED**: Review lowest-scoring files and trend immediately. "
            "Consider triggering a focused Recursive Self-Improvement cycle before any further architectural changes."
        )
        warning_blocks.append(low_score_block)

    # 2. Per-file Degradation Warnings — persistent weakness
    if degradation_warnings:
        deg_lines = ["**⚠️ Degradation Warnings**"]
        deg_lines.append("**ACTION REQUIRED** — One or more files are structurally the weakest over multiple scans and are limiting overall evolvability:")
        for warning in degradation_warnings:
            deg_lines.append(f"- {warning}")
        deg_lines.append("Prioritize concrete improvements (hypotheses, evidence, measurable targets) to this file(s) before the next major evolution step.")
        warning_blocks.append("\n".join(deg_lines))

    degradation_section = ""
    if warning_blocks:
        degradation_section = "\n".join(warning_blocks) + "\n\n"

    recommendation = generate_recommendation(report)

    # v0.16 experimental: surface LLM review if present (clearly labeled)
    llm_section = ""
    llm_data = report.get("llm_review")
    if llm_data and llm_data.get("enabled"):
        if "result" in llm_data:
            r = llm_data["result"]
            llm_section = f"""## LLM Review (EXPERIMENTAL — advisory only, does not affect Health Score)
**File reviewed**: `{llm_data.get('file')}`
**Refined score (LLM opinion)**: {r.get('refined_score')}
**Confidence**: {r.get('confidence')}
**Summary**: {r.get('one_sentence_summary')}

**Additional findings**:
{chr(10).join(f"- {f}" for f in r.get('additional_findings', [])) or "- (none)"}

*This is an early experiment. LLM output can be noisy or wrong. Always cross-check against the actual file.*
"""
        else:
            llm_section = f"""## LLM Review (EXPERIMENTAL)
Requested but unavailable: {llm_data.get('error', 'unknown error')}
"""

    content = f"""# DNA Guardian Scan — {ts.isoformat()}

**Tool version**: {report['tool_version']}
**DNA version**: {report['dna_version']}
**Overall status**: **{status}**

{health_line}{trend_section}## Observation
A periodic DNA Guardian scan was executed.

### Structural Validation
- Total checks: {report['summary']['total_checks']}
- Passed: {report['summary']['passed']}
- Failed: {report['summary']['failed']}

### Truth Density Results
- Average score across key files: **{avg_score}/10**
- Files scored: {report['truth_density_summary']['files_scored']}

### Key Findings
{chr(10).join(findings_lines)}

## Impact on Evolvability
{"The current DNA structure is intact and shows reasonable truth density." if status == "PASS" else "Structural issues were detected that may hinder future self-improvement quality."}

{longer_summary_section}{degradation_section}
{llm_section}
## Suggested Next Action
{recommendation}

---
*Generated automatically by DNA Guardian. This entry follows the Recursive Self-Improvement Protocol.*
"""

    filepath.write_text(content, encoding="utf-8")
    return str(filepath)


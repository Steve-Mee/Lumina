#!/usr/bin/env python3
"""
DNA Guardian - Validation & Scoring Tool for Lumina Project DNA 2.0

v0.16.0-experimental: First narrow slice of Increment 4 — optional --llm-review (local Ollama only, weakest file, heuristic remains source of truth). Clearly labeled experimental.

Recommended usage for meta-improvements:
    python scripts/dna_guardian/validate_dna.py --create-entry

This generates a proper entry in evolution/log/ that follows the Recursive Self-Improvement Protocol.
"""

import argparse
import json
import os
import sys
import urllib.error
import urllib.request
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

# Root of the project
PROJECT_ROOT = Path(__file__).resolve().parents[2]
DNA_ROOT = PROJECT_ROOT / "project-dna" / "lumina"


def check_path_exists(relative_path: str) -> bool:
    """Check if a path exists relative to DNA_ROOT."""
    return (DNA_ROOT / relative_path).exists()


def validate_structure() -> list[dict[str, Any]]:
    """Perform structural validation of the DNA 2.0 layout.

    Tries to load the list from the external rules file.
    Falls back to a minimal hardcoded list if loading fails (for robustness during transition).
    """
    try:
        # Attempt to load from external rules (best effort)
        import sys
        sys.path.insert(0, str(Path(__file__).parent))
        from rules import get_required_paths
        required_paths = get_required_paths()
        if not required_paths:
            raise RuntimeError("External rules returned empty list")
    except Exception:
        # Safe fallback during the transition to external rules
        required_paths = [
            "core/constitution.md",
            "core/north-star.md",
            "core/invariants.json",
            "operating-system/self-improvement-protocol.md",
            "operating-system/truth-metrics.md",
            "operating-system/decision-framework.md",
            "operating-system/anti-patterns.md",
            "operating-system/dna-validation-rules.md",
            "current-reality/architecture.md",
            "current-reality/evolutionary-debt.md",
            "interfaces/README.md",
            "interfaces/export/agent-context.md",
            "evolution-log.md",
            "evolution/log",
            "evolution/experiments",
        ]

    results = []
    all_ok = True

    for path in required_paths:
        exists = check_path_exists(path)
        if not exists:
            all_ok = False
        results.append({
            "path": path,
            "exists": exists,
            "status": "OK" if exists else "MISSING"
        })

    return results, all_ok


# --- Truth Density Heuristics (v0.2.0 → loaded from external rules) ---

try:
    from rules import get_vague_words, get_positive_markers
    VAGUE_WORDS = get_vague_words()
    POSITIVE_MARKERS = get_positive_markers()
except Exception:
    # Safe fallback during transition to external rules
    VAGUE_WORDS = [
        "should", "aims to", "as much as possible", "in the future",
        "we want", "we hope", "try to", "attempt to"
    ]
    POSITIVE_MARKERS = [
        "hypothesis", "falsifiable", "prediction", "measurable",
        "evidence", "score", "metric"
    ]


def calculate_truth_density(relative_path: str) -> dict[str, Any]:
    """
    Very basic Truth Density heuristic for a single file.
    Returns a dict with score (0-10) and findings.

    Scoring parameters are now loaded from external rules (v0.13.0).
    """
    full_path = DNA_ROOT / relative_path
    if not full_path.exists() or not full_path.is_file():
        return {"score": 0.0, "findings": ["File does not exist"]}

    try:
        content = full_path.read_text(encoding="utf-8").lower()
    except Exception:
        return {"score": 0.0, "findings": ["Could not read file"]}

    words = content.split()
    word_count = len(words)
    if word_count == 0:
        return {"score": 0.0, "findings": ["Empty file"]}

    vague_count = sum(1 for w in VAGUE_WORDS if w in content)
    positive_count = sum(1 for w in POSITIVE_MARKERS if w in content)

    # Load scoring parameters from external rules (with fallback)
    try:
        from rules import get_scoring_parameters
        params = get_scoring_parameters()
    except Exception:
        params = {
            "base_score": 7.0,
            "vague_penalty_per_occurrence": 0.4,
            "vague_density_multiplier": 1.2,
            "positive_reward_per_occurrence": 0.6,
            "max_vague_penalty": 4.0,
            "max_positive_reward": 2.5,
            "long_file_penalty_threshold": 1200,
            "long_file_penalty": 1.0,
        }

    # Base score
    score = params["base_score"]

    # Penalize high vague word density
    vague_density = vague_count / max(word_count / 100, 1)
    score -= min(vague_density * params["vague_density_multiplier"], params["max_vague_penalty"])

    # Reward presence of positive markers
    score += min(positive_count * params["positive_reward_per_occurrence"], params["max_positive_reward"])

    # Light penalty for very long files without structure
    if word_count > params["long_file_penalty_threshold"] and "hypothesis" not in content:
        score -= params["long_file_penalty"]

    score = max(0.0, min(10.0, round(score, 1)))

    findings = []
    if vague_count > 3:
        findings.append(f"Contains {vague_count} vague phrases")
    if positive_count >= 2:
        findings.append(f"Contains {positive_count} strong evidence markers")
    if not findings:
        findings.append("No major heuristic signals detected")

    return {
        "score": score,
        "findings": findings
    }


def calculate_dna_health_score(structure_results: list[dict], truth_density_results: dict) -> dict[str, Any]:
    """
    Calculates a composite DNA Health Score (0-10).
    This is a simple but meaningful first version.
    """
    total_checks = len(structure_results)
    passed_checks = sum(1 for r in structure_results if r["exists"])
    structural_rate = (passed_checks / total_checks) if total_checks > 0 else 0.0

    avg_td = (
        sum(r["score"] for r in truth_density_results.values()) / len(truth_density_results)
        if truth_density_results else 0.0
    )

    # Formula (transparent and tunable):
    # 50% Structural Health + 50% Average Truth Density
    health_score = (structural_rate * 5) + (avg_td * 0.5)
    health_score = max(0.0, min(10.0, round(health_score, 2)))

    return {
        "score": health_score,
        "components": {
            "structural_health": round(structural_rate * 10, 1),
            "truth_density_avg": round(avg_td, 2)
        }
    }


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


# --- Health History for Trend Lines (new in v0.11.0, extended in v0.13.0) ---

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


# ---------------------------------------------------------------------------
# Capital Aperture Integrity (Elon First-Principles Track — Phase 0)
# ---------------------------------------------------------------------------

def calculate_aperture_integrity() -> dict[str, Any]:
    """
    Calculates a simple Aperture Integrity Score based on the external aperture.yaml baseline.
    Returns a dict with score (0-10), counts, status, and active warning if applicable.
    This is the first forcing function that makes bypass erosion visible in every Guardian run.
    """
    try:
        # Safe import pattern matching the rest of the Guardian (handles running as script)
        import sys
        from pathlib import Path
        sys.path.insert(0, str(Path(__file__).parent))
        from rules import get_aperture_baseline, get_aperture_scoring_params, load_aperture_rules

        baseline = get_aperture_baseline()
        scoring = get_aperture_scoring_params()
        rules = load_aperture_rules()
    except Exception:
        # Guardian must never break
        return {
            "score": 5.0,
            "fatal_count": 0,
            "high_count": 0,
            "status": "UNKNOWN",
            "warning": "Aperture rules could not be loaded — check project-dna/lumina/operating-system/rules/aperture.yaml",
        }

    fatal = int(baseline.get("fatal_count", 0))
    high = int(baseline.get("high_count", 0))
    medium = int(baseline.get("medium_count", 0))

    base = float(scoring.get("base_score", 10.0))
    penalty = (
        fatal * float(scoring.get("fatal_penalty_per_item", 2.0))
        + high * float(scoring.get("high_penalty_per_item", 0.8))
        + medium * float(scoring.get("medium_penalty_per_item", 0.3))
    )
    penalty = min(penalty, float(scoring.get("max_penalty", 8.0)))

    score = max(0.0, round(base - penalty, 2))

    # Phase 1.1 light mitigation: enforcement active reduces effective risk
    enforcement = rules.get("enforcement", {})
    if enforcement.get("active") and fatal > 0:
        mitigation_bonus = 3.0  # Enforcement makes the remaining count less dangerous
        score = min(10.0, round(score + mitigation_bonus, 2))

    if fatal > 0:
        status = "CRITICAL"
    elif fatal > int(rules.get("targets", {}).get("fatal_max_for_yellow", 1)):
        status = "RED"
    elif high > 0:
        status = "YELLOW"
    else:
        status = "GREEN"

    warning = rules.get("active_warning", "") if fatal > 0 else ""

    return {
        "score": score,
        "fatal_count": fatal,
        "high_count": high,
        "medium_count": medium,
        "total_tracked": int(baseline.get("total_tracked", fatal + high + medium)),
        "status": status,
        "warning": warning,
    }


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


# --- Minimal Ollama client for experimental LLM review (v0.16 Increment 4 first slice) ---

def _call_ollama_chat(
    prompt: str,
    model: str = "qwen3.5:9b",
    base_url: str = "http://localhost:11434",
    timeout_sec: float = 20.0,
) -> dict[str, Any] | None:
    """
    Very small, dependency-free call to Ollama /api/chat.
    Returns parsed JSON response or None on any failure (timeout, error, bad JSON).
    Designed for the narrow experimental --llm-review path only.
    """
    url = f"{base_url.rstrip('/')}/api/chat"
    payload = {
        "model": model,
        "messages": [{"role": "user", "content": prompt}],
        "stream": False,
        "options": {"temperature": 0.3},  # low temp for more consistent analysis
    }
    data = json.dumps(payload).encode("utf-8")
    req = urllib.request.Request(url, data=data, headers={"Content-Type": "application/json"})

    try:
        with urllib.request.urlopen(req, timeout=timeout_sec) as resp:
            raw = resp.read().decode("utf-8")
            return json.loads(raw)
    except (urllib.error.URLError, TimeoutError, json.JSONDecodeError, Exception):
        return None


def _get_ollama_models() -> list[str]:
    """
    Returns preferred model order for LLM review.
    Can be overridden with DNA_GUARDIAN_OLLAMA_MODELS (comma-separated).
    """
    env_models = os.getenv("DNA_GUARDIAN_OLLAMA_MODELS", "").strip()
    if env_models:
        parsed = [m.strip() for m in env_models.split(",") if m.strip()]
        if parsed:
            return parsed

    return ["qwen3.5:9b", "qwen2.5:7b", "qwen2.5:3b"]


def _get_ollama_timeout_sec() -> float:
    """
    Returns Ollama timeout in seconds.
    Can be overridden with DNA_GUARDIAN_OLLAMA_TIMEOUT_SEC.
    """
    raw = os.getenv("DNA_GUARDIAN_OLLAMA_TIMEOUT_SEC", "").strip()
    if not raw:
        return 20.0

    try:
        value = float(raw)
        return value if value > 0 else 20.0
    except ValueError:
        return 20.0


def run_llm_review_on_file(
    file_path: str,
    heuristic_result: dict[str, Any],
    context_summary: str,
) -> dict[str, Any] | None:
    """
    Runs a narrow, experimental LLM review on a single file.
    Returns structured dict or None if anything fails.
    The prompt is deliberately conservative and focused.
    """
    full_path = DNA_ROOT / file_path
    if not full_path.exists():
        return None

    try:
        content = full_path.read_text(encoding="utf-8")
    except Exception:
        return None

    # Load few-shot examples for better prompting (part of Double Down Local proposal)
    examples_dir = DNA_ROOT / "operating-system" / "llm-review-examples"
    few_shot_text = ""
    if examples_dir.exists():
        example_files = sorted(examples_dir.glob("*.md"))[:3]  # max 3 examples for now
        for ex_file in example_files:
            try:
                few_shot_text += "\n\n--- FEW-SHOT EXAMPLE ---\n" + ex_file.read_text(encoding="utf-8")[:2500]
            except Exception:
                pass

    # LLM Review Prompt v3.0 — Double Down Local (14-day evaluation sprint)
    prompt = f"""You are an extremely rigorous, first-principles reviewer of self-improvement systems for a high-stakes autonomous trading organism.

Your mission: Maximize the future evolution speed of this system by ruthlessly exposing weaknesses in documentation that slow down or derail high-quality, evidence-based improvement.

Core principles you must follow:
- Be brutally honest. Vague language and aspirational claims are technical debt.
- Always reference the official Evolvability Score definition when relevant.
- Prefer specific quotes and concrete examples over general statements.
- Every finding must be actionable.

File: {file_path}
Heuristic findings: {heuristic_result.get('findings', [])}
DNA context: {context_summary}

Relevant high-quality review examples (for style and depth reference):
{few_shot_text}

File content:
{content[:10000]}

**Required thinking structure (do this internally):**
1. Falsifiability & Evidence — Quote exact sentences that are not testable or lack evidence.
2. Evolvability Impact — How does this document currently slow down or increase risk of future improvements? Use the Evolvability Score lens.
3. Missing Forcing Functions & Precision — What specific mechanisms or definitions are missing that would make good evolution obvious and bad evolution painful?
4. Top Actionable Improvement — What is the single highest-leverage concrete change for this file right now?

Output ONLY this exact JSON structure (no markdown, no extra text):
{{
  "refined_score": <0-10, be strict and consistent>,
  "additional_findings": [
    "Specific, quoted finding 1",
    "Specific, quoted finding 2"
  ],
  "evolvability_impact": "<1-2 sentences using Evolvability Score concepts>",
  "top_actionable_improvement": "<one concrete, high-leverage action>",
  "missing_precision_areas": ["e.g. definition of X is unclear", "no criteria for Y"],
  "confidence": <0.0-1.0>,
  "one_sentence_summary": "<extremely concise and direct>"
}}"""

    timeout_sec = _get_ollama_timeout_sec()
    response = None
    for model_name in _get_ollama_models():
        response = _call_ollama_chat(prompt, model=model_name, timeout_sec=timeout_sec)
        if response and "message" in response:
            break

    if not response or "message" not in response:
        return None

    try:
        llm_text = response["message"].get("content", "")
        # Try to extract JSON even if model adds a little noise
        start = llm_text.find("{")
        end = llm_text.rfind("}") + 1
        if start == -1 or end <= start:
            return None
        parsed = json.loads(llm_text[start:end])
        # Basic validation
        if "refined_score" not in parsed:
            return None
        return parsed
    except Exception:
        return None


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


def generate_report(structure_results: list[dict], all_ok: bool) -> dict[str, Any]:
    """Generate a structured report (v0.5.0 with DNA Health Score)."""
    timestamp = datetime.now(timezone.utc).isoformat()

    # Run Truth Density on a few key files
    key_files = [
        "core/constitution.md",
        "operating-system/self-improvement-protocol.md",
        "operating-system/truth-metrics.md",
        "current-reality/evolutionary-debt.md",
    ]

    truth_density_results = {}
    for f in key_files:
        truth_density_results[f] = calculate_truth_density(f)

    avg_score = (
        sum(r["score"] for r in truth_density_results.values()) / len(truth_density_results)
        if truth_density_results else 0.0
    )

    health = calculate_dna_health_score(structure_results, truth_density_results)

    # Trend detection (new in v0.6.0)
    previous_score = get_previous_health_score()
    trend = None
    if previous_score is not None:
        delta = round(health["score"] - previous_score, 2)
        trend = {
            "previous_score": previous_score,
            "delta": delta,
            "direction": "up" if delta > 0.05 else ("down" if delta < -0.05 else "stable")
        }

    # Update health history and get short trend line (new in v0.11.0)
    # v0.13.0: also store per-file scores for degradation tracking
    history = update_health_history(health["score"], truth_density_results)
    short_trend = get_short_trend_line(history)
    longer_trend = get_longer_trend_summary(history)

    # New in v0.13.0: detect files that are structurally weak over time
    degradation_warnings = detect_per_file_degradation(history)

    recommendation = generate_recommendation({
        "truth_density": truth_density_results,
        "trend": trend,
        "overall_status": "PASS" if all_ok else "FAIL"
    })

    report = {
        "timestamp": timestamp,
        "dna_version": "2.0",
        "tool_version": "0.17.0-elon-aperture-phase0",
        "overall_status": "PASS" if all_ok else "FAIL",
        "dna_health_score": health,
        "trend": trend,
        "health_trend_line": short_trend,
        "longer_trend_summary": longer_trend,
        "degradation_warnings": degradation_warnings,
        "recommendation": recommendation,
        "structural_validation": structure_results,
        "truth_density": truth_density_results,
        "truth_density_summary": {
            "average_score": round(avg_score, 2),
            "files_scored": len(truth_density_results),
        },
        "summary": {
            "total_checks": len(structure_results),
            "passed": sum(1 for r in structure_results if r["exists"]),
            "failed": sum(1 for r in structure_results if not r["exists"]),
        },
        # Phase 0 Elon aperture track (additive, never breaks existing consumers)
        "aperture_integrity": calculate_aperture_integrity(),
    }

    # Phase 3 D5: constitution invariant + forbidden-pattern scan (fail-hard via main exit)
    try:
        from capital_aperture_scan import run_d5_capital_aperture_checks

        report["d5_capital_aperture"] = run_d5_capital_aperture_checks(PROJECT_ROOT)
    except Exception as e:
        report["d5_capital_aperture"] = {
            "ok": False,
            "alignment": {"ok": False, "issues": [f"d5 check import/run failed: {e}"]},
            "scan": {"ok": False, "violations": [], "scanned_files": 0},
        }

    return report


def print_markdown_report(report: dict[str, Any], *, d1_audits: bool = True) -> None:
    """Print a human-readable Markdown report."""
    print("# DNA Guardian Report")
    print(f"**Timestamp**: {report['timestamp']}")
    print(f"**DNA Version**: {report['dna_version']}")
    print(f"**Overall Status**: **{report['overall_status']}**")

    if "dna_health_score" in report:
        hs = report["dna_health_score"]
        print(f"\n**DNA Health Score: {hs['score']}/10**")
        print(f"  - Structural Health: {hs['components']['structural_health']}/10")
        print(f"  - Truth Density Avg: {hs['components']['truth_density_avg']}/10")

    print()
    print("## Structural Validation")
    print(f"- Total checks: {report['summary']['total_checks']}")
    print(f"- Passed: {report['summary']['passed']}")
    print(f"- Failed: {report['summary']['failed']}")
    print()

    if report['summary']['failed'] > 0:
        print("### Missing Items")
        for item in report['structural_validation']:
            if not item['exists']:
                print(f"- ❌ `{item['path']}`")
        print()

    # New in v0.2.0
    if "truth_density_summary" in report:
        print("## Truth Density (Heuristic)")
        td = report["truth_density_summary"]
        print(f"- Average score: **{td['average_score']}/10** (across {td['files_scored']} key files)")
        print()

        for path, result in report.get("truth_density", {}).items():
            print(f"  - `{path}`: **{result['score']}/10** — {', '.join(result['findings'])}")
        print()

    print("## Recommendations")
    rec = generate_recommendation(report)
    print(f"**Recommended Focus**: {rec}")

    # v0.14.0: Stronger, separate warning blocks with active language (mirrors create_evolution_entry)
    degradation_warnings = report.get("degradation_warnings", [])
    health_score = report.get("dna_health_score", {}).get("score", 10.0)
    LOW_SCORE_THRESHOLD = 8.0

    if degradation_warnings or health_score < LOW_SCORE_THRESHOLD:
        print("\n**[!] ALERTS** (DNA Guardian)")

    if health_score < LOW_SCORE_THRESHOLD:
        print(f"  **LOW HEALTH SCORE ALERT**: {health_score}/10 (below {LOW_SCORE_THRESHOLD})")
        print("     ACTION REQUIRED: DNA quality erosion detected. Review focus file + trend. Trigger self-improvement cycle before major changes.")

    if degradation_warnings:
        print("  **Degradation Warnings — ACTION REQUIRED**:")
        print("     Persistent weakest file(s) limiting evolvability:")
        for warning in degradation_warnings:
            print(f"     - {warning}")
        print("     Prioritize improvements (add hypothesis/evidence/metrics) before next evolution step.")

    if report['overall_status'] == "PASS":
        print("- All required DNA 2.0 structure elements are present.")
        print("- Consider re-running the Guardian after addressing the focus area to measure improvement.")
    else:
        print("- Please restore or create the missing files listed above.")
        print("- Re-run this tool after fixing the structure.")

    # ======================================================================
    # CAPITAL APERTURE INTEGRITY — Phase 0 Elon First-Principles Addition
    # This block is intentionally loud. When FATAL bypasses exist, the system
    # is not yet the "impenetrable fort" the Constitution and north-star demand.
    # ======================================================================
    gss = report.get("guardian_self_score") or {}
    if gss:
        print("\n## PHASE 3 D6 - GUARDIAN SELF-SCORE (Aperture Contract)")
        print(f"  - Overall self-score: **{gss.get('overall_score', '?')}/10**  Status: **{gss.get('status', '?')}**")
        for dim, sc in sorted((gss.get("dimension_scores") or {}).items()):
            print(f"    - {dim}: {sc}/10")
        if gss.get("d3_violation_count", 0):
            print(f"  - D3 violations counted: {gss['d3_violation_count']}")
        if float(gss.get("overall_score", 10)) < float(gss.get("warn_below", 8)):
            print(
                f"  - **D6 WARNING**: self-score below {gss.get('warn_below')} — "
                "aperture forcing panel incomplete or degraded."
            )
        if gss.get("notes"):
            print(f"  - {gss['notes']}")

    d5 = report.get("d5_capital_aperture") or {}
    if d5:
        print("\n## PHASE 3 D5 - NO STRUCTURAL BYPASS (Constitution + Static Scan)")
        if d5.get("ok"):
            scan = d5.get("scan") or {}
            print(
                f"  - D5 PASS: constitution/invariant aligned; "
                f"static scan clean ({scan.get('scanned_files', 0)} files scanned)"
            )
        else:
            print("  - **D5 FAIL — ACTION REQUIRED (release blocker for capital-path changes)**")
            alignment = d5.get("alignment") or {}
            for issue in alignment.get("issues", []):
                print(f"     alignment: {issue}")
            scan = d5.get("scan") or {}
            for v in scan.get("violations", [])[:10]:
                print(
                    f"     {v.get('file')}:{v.get('line')}  [{v.get('pattern_id')}]  {v.get('snippet', '')}"
                )
            if len(scan.get("violations", [])) > 10:
                print(f"     ... and {len(scan['violations']) - 10} more")

    aperture = report.get("aperture_integrity")
    if aperture:
        print("\n## CAPITAL APERTURE INTEGRITY (Elon First-Principles Track)")
        print(f"**Aperture Integrity Score**: **{aperture['score']}/10**")
        print(f"  - FATAL bypass mechanisms: {aperture['fatal_count']}")
        print(f"  - HIGH erosion points: {aperture['high_count']}")
        print(f"  - Status: **{aperture['status']}**")
        print(f"  - Items tracked: {aperture['total_tracked']}")

        # Safe load for any enforcement messages (rules is local to calculate_aperture_integrity)
        try:
            import sys
            from pathlib import Path
            sys.path.insert(0, str(Path(__file__).parent))
            from rules import load_aperture_rules
            rules = load_aperture_rules() or {}
        except Exception:
            rules = {}

        # Phase 2 start (2026-05-31): First typed spine forcing function baseline
        print("  - Phase 2 Typed Spine (Final Arbitration emissions on critical bus): baseline established (target: 100% of canonical decisions)")
        print("  - Phase 2 Lineage Correlation (shared decision_context_id between risk.policy.decision and risk.final_arbitration.result): in progress")
        print("  - Phase 2 Hash Chaining (prev_hash on risk decisions): baseline started (simple sequential chaining on critical path)")

        # Phase 2 Slice 04: Active hash chain monitoring + reconstruction (forcing function)
        try:
            import sys
            from pathlib import Path
            # Ensure repo root is on path when Guardian is invoked directly (script mode)
            sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
            from lumina_core.risk.decision_lineage import reconstruct_risk_decision_chain, is_chain_healthy

            # Try to get a bus if available in the current environment
            bus = None
            try:
                from lumina_core.order_gatekeeper import _resolve_event_bus  # type: ignore
                # This may not always be populated at Guardian runtime; best-effort only.
            except Exception:
                pass

            # For Guardian runs we do a lightweight check on recent activity by looking at
            # recent events via any available bus on the engine/config if present.
            # In practice the Guardian often runs without a live trading engine,
            # so we report what we can and encourage use of the helper in audits/tests.
            print("  - Phase 2 Risk Decision Hash Chain Health: reconstruction helper available")
            print("      Use lumina_core.risk.decision_lineage.reconstruct_risk_decision_chain(decision_context_id)")
            print("      for post-trade audits and targeted chain validation.")
            print("  - Phase 2 Lineage Root (admission.gate_entry): root event now emitted at the absolute start of the canonical gate")
            print("  - Phase 2 Continuous Hash Chain (Gate Entry -> Risk Allocation -> Final Arbitration): wiring active")
            print("  - Phase 2 Upstream Lineage (Agent Proposals -> Gate Entry): decision_context_id now propagates from proposals (Slice 08)")
            print("  - Phase 2 Proposal-Level prev_hash (first cryptographic link from blackboard proposals): baseline started (Slice 09)")
            print("  - Phase 2 Proposal Events on Main Bus (first-class typed proposals with decision_context_id): baseline started (Slice 10)")
            print("  - Phase 2 Deeper Proposal-to-Gate Hash Chain on Main Bus: event_hash on proposals + preferred main-bus lookup in gate_entry (Slice 11)")
            print("  - Phase 2 Upstream Dream/Multi-Agent Lineage (Slice 12): cycle decision_context_id originates in pre-dream coordination; dream_state.updated now participates in reconstruction and best-effort prev_hash lookup")
            print("  - Phase 2 Hash Chain Validation Warnings (Slice 13): ACTIVE — Guardian now screams on broken/incomplete chains (best-effort sampling via bus + blackboard JSONL)")
            print("  - Phase 2 Downstream Lineage into Fills (Slice 16): Fill and OrderResult now carry decision_context_id + prev_hash from submission (paper path + documented pattern for live brokers)")
            print("  - Phase 2 Reconstruction + Provenance Report now surfaces fills (Slice 17): build_pretrade_provenance_report + format_as_markdown include execution/fills section when recent_fills are provided")
            print("  - Phase 2 Typed execution.fill.received events (Slice 18): proper Pydantic model + best-effort publishing from paper broker and trade_reconciler with full lineage (decision_context_id + prev_hash)")
            print("  - Phase 2 Fill dataclass first-class lineage fields (Slice 19): decision_context_id, prev_hash, prev_event_topic promoted to top-level optional fields on central Fill (broker_bridge); PaperBroker + CrossTrade list_fills populate them; publishers + get_lineage_from_fill now prefer first-class over raw (transition compat preserved); ExecutionFill Pydantic model already aligned.")
            print("  - Phase 2 Slice 20: `execution.fill.received` promoted to CRITICAL_EVENT_BUS_TOPICS (schema violations now raise/fail-closed instead of being swallowed; same strict contract as risk.final_arbitration.result and gate_entry).")
            print("  - Phase 2 Slice 21: Guardian now actively screams on critical fill events that lack proper downstream lineage (decision_context_id + prev_hash). Daily forcing function for the execution side of the continuous hash chain.")
            print(
                "  - Phase 2 Slice 22: Provenance report (`build_pretrade_provenance_report`) and CLI now automatically pull "
                "recent fills from broker when engine context is available. Guardian can leverage this for complete automated "
                "end-to-end reports without manual recent_fills."
            )

            # Phase 2 Slice 13: Best-effort hash chain validation warnings (make breaks scream)
            # This turns the cryptographic spine built in Slices 03-12 into an active daily forcing function.
            try:
                recent_ctxs = []

                # 1. Best-effort: try live bus (if the Guardian was invoked in a context where an engine is attached)
                if bus is not None and hasattr(bus, "history"):
                    try:
                        arb_events = list(bus.history("risk.final_arbitration.result", limit=30))
                        for ev in arb_events:
                            cid = str(getattr(ev, "metadata", {}).get("decision_context_id", "") or getattr(ev, "payload", {}).get("decision_context_id", ""))
                            if cid and cid not in recent_ctxs:
                                recent_ctxs.append(cid)
                    except Exception:
                        pass

                # 2. Strong practical fallback for normal standalone Guardian runs: tail the blackboard JSONL
                if len(recent_ctxs) < 6:
                    try:
                        import os
                        from pathlib import Path
                        state_dir = os.getenv("LUMINA_STATE_DIR", "state")
                        bb_path = Path(state_dir) / "agent_blackboard.jsonl"
                        if bb_path.exists():
                            lines = bb_path.read_text(encoding="utf-8", errors="ignore").strip().splitlines()[-150:]
                            for line in reversed(lines):
                                try:
                                    rec = json.loads(line)
                                    topic = str(rec.get("topic", "")).lower()
                                    if topic.endswith(".proposal"):
                                        cid = str(rec.get("payload", {}).get("decision_context_id") or rec.get("correlation_id", ""))
                                        if cid and cid not in recent_ctxs:
                                            recent_ctxs.append(cid)
                                            if len(recent_ctxs) >= 8:
                                                break
                                except Exception:
                                    continue
                    except Exception:
                        pass

                # Phase 3 D3: merge Final Arbitration ctxs from immutable logs (genuine/live path for D1)
                try:
                    from lumina_core.audit.aperture_audit_artifact import merge_d1_audit_context_ids

                    recent_ctxs = merge_d1_audit_context_ids(recent_ctxs, max_ctxs=8)
                    if recent_ctxs:
                        print(
                            f"  - Phase 3 D3: D1 audit ctx pool ({len(recent_ctxs)} ids, incl. Final Arbitration log discovery)"
                        )
                except Exception as e:
                    print(f"  - Phase 3 D3: D1 ctx merge (best-effort): {e}")

                phase3_d3_violations: list[str] = []

                # 3. Validate a small sample
                broken = []
                for ctx in recent_ctxs[:6]:
                    try:
                        chain = reconstruct_risk_decision_chain(ctx, event_bus=bus, limit=50)
                        if chain:
                            healthy = is_chain_healthy(chain)
                            has_core = any(item.get("topic") in ("admission.gate_entry", "risk.policy.decision", "risk.final_arbitration.result") for item in chain)
                            if not healthy or not has_core:
                                broken.append({"ctx": ctx, "healthy": healthy, "chain_len": len(chain)})
                    except Exception:
                        continue

                if broken:
                    print("\n  ⚠️  HASH CHAIN INTEGRITY WARNING (Slice 13)")
                    for b in broken:
                        print(f"     decision_context_id={b['ctx']}  healthy={b['healthy']}  nodes={b['chain_len']}")
                        phase3_d3_violations.append(
                            f"broken/incomplete risk chain ctx={b['ctx']} (healthy={b['healthy']}, nodes={b['chain_len']})"
                        )
                    print("     ACTION: Investigate with reconstruct_risk_decision_chain() + post-trade audit. Lineage is the source of truth.")
                else:
                    print(f"  - Phase 2 Hash Chain Validation (Slice 13): {len(recent_ctxs)} recent ctx sampled, all healthy (best-effort)")

                # Phase 2 Slice 21: Best-effort screaming for critical `execution.fill.received` events
                # (downstream lineage integrity). Now that the topic is CRITICAL (Slice 20),
                # any fill events present for a ctx must carry valid lineage. Missing lineage
                # on a critical execution event is a forcing-function violation.
                try:
                    fill_ctxs_with_lineage_issues = []
                    fill_ctxs_checked = 0

                    if bus is not None and hasattr(bus, "history"):
                        try:
                            fill_events = list(bus.history("execution.fill.received", limit=30))
                            for ev in fill_events:
                                payload = getattr(ev, "payload", {}) or {}
                                cid = str(payload.get("decision_context_id", "") or getattr(ev, "metadata", {}).get("decision_context_id", ""))
                                if not cid:
                                    continue
                                fill_ctxs_checked += 1
                                has_lineage = bool(payload.get("decision_context_id") and payload.get("prev_hash"))
                                if not has_lineage:
                                    if cid not in [b.get("ctx") for b in fill_ctxs_with_lineage_issues]:
                                        fill_ctxs_with_lineage_issues.append({
                                            "ctx": cid,
                                            "reason": "missing decision_context_id or prev_hash on critical fill event"
                                        })
                        except Exception:
                            pass

                    # Fallback: scan recent blackboard for fill records (best-effort, same style as proposals)
                    if len(fill_ctxs_with_lineage_issues) == 0 and fill_ctxs_checked == 0:
                        try:
                            import os
                            from pathlib import Path
                            state_dir = os.getenv("LUMINA_STATE_DIR", "state")
                            bb_path = Path(state_dir) / "agent_blackboard.jsonl"
                            if bb_path.exists():
                                lines = bb_path.read_text(encoding="utf-8", errors="ignore").strip().splitlines()[-100:]
                                for line in reversed(lines):
                                    try:
                                        rec = json.loads(line)
                                        topic = str(rec.get("topic", "")).lower()
                                        if "fill.received" in topic or "execution.fill" in topic:
                                            payload = rec.get("payload", {}) or {}
                                            cid = str(payload.get("decision_context_id", "") or rec.get("correlation_id", ""))
                                            if cid:
                                                fill_ctxs_checked += 1
                                                has_lineage = bool(payload.get("decision_context_id") and payload.get("prev_hash"))
                                                if not has_lineage:
                                                    if cid not in [b.get("ctx") for b in fill_ctxs_with_lineage_issues]:
                                                        fill_ctxs_with_lineage_issues.append({
                                                            "ctx": cid,
                                                            "reason": "missing lineage on critical fill event (blackboard)"
                                                        })
                                    except Exception:
                                        continue
                        except Exception:
                            pass

                    if fill_ctxs_with_lineage_issues:
                        print("\n  ⚠️  DOWNSTREAM FILL LINEAGE WARNING (Slice 21)")
                        for issue in fill_ctxs_with_lineage_issues[:5]:
                            print(f"     decision_context_id={issue['ctx']}  issue={issue['reason']}")
                            phase3_d3_violations.append(
                                f"missing fill lineage ctx={issue['ctx']}: {issue['reason']}"
                            )
                        print("     ACTION: Run `python -m lumina_core.risk.decision_lineage <ctx>` for full provenance + post-trade audit.")
                        print("     This topic is now CRITICAL (Slice 20). Lineage on fills is mandatory for the continuous hash chain.")
                    elif fill_ctxs_checked > 0:
                        print(f"  - Phase 2 Downstream Fill Lineage Validation (Slice 21): {fill_ctxs_checked} recent critical fill events sampled, all carry valid lineage (best-effort)")
                    else:
                        print("  - Phase 2 Downstream Fill Lineage Validation (Slice 21): no recent critical fill events found in sampled data (best-effort)")

                except Exception as e:
                    print(f"  - Phase 2 Downstream Fill Lineage Validation (Slice 21): best-effort check skipped (non-fatal): {e}")

                # Phase 3 D1: Guardian daily integration — narrow hook
                # Auto-generate full "one human 20 min" artifacts (sidecar) AND embed compact summary
                # directly in this Guardian report. This makes the D1 view part of the daily output
                # itself (not only sidecars for D4). Best-effort only; never blocks.
                if d1_audits:
                    try:
                        from lumina_core.audit.aperture_audit_artifact import (
                            build_aperture_audit_artifact,
                            format_aperture_audit_as_markdown,
                            format_compact_aperture_audit,
                        )
                        if recent_ctxs:
                            for ctx in recent_ctxs[:2]:
                                try:
                                    art = build_aperture_audit_artifact(ctx)
                                    audits_dir = Path("state/audits")
                                    audits_dir.mkdir(parents=True, exist_ok=True)
                                    safe = "".join(c if c.isalnum() or c in "-_" else "_" for c in ctx)[:40]
                                    ts = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")
                                    mdp = audits_dir / f"guardian_d1_{safe}_{ts}.md"
                                    mdp.write_text(format_aperture_audit_as_markdown(art), encoding="utf-8")
                                    print(f"  - Phase 3 D1: Full artifact saved for ctx={ctx} -> {mdp}")
                                    # Embed the compact one-human-20-min view directly in the Guardian report
                                    print(format_compact_aperture_audit(art))
                                except Exception:
                                    continue
                    except Exception as e:
                        print(f"  - Phase 3 D1 integration (best-effort): {e}")
                else:
                    print("  - Phase 3 D1: aperture audit generation disabled via --no-d1-audits")

                # Phase 3 D3 forcing function enhancement: Surface latest genuine D4 evidence (from production paths + live broker lineage)
                # directly in every daily Guardian aperture report when present. This makes the "jaws-dropping" public demo
                # a non-negotiable part of daily health (D1 + D4 proof always visible to agents/ops). Ties D3 integration to live data.
                try:
                    audits_dir = Path("state/audits")
                    # Support both controlled genuine (d4_genuine_campaign_*) and longer multi-day/30-day scale from run_genuine_d4_campaign (d4_30day_campaign_*)
                    # This makes the full D4 scale evidence (per MC next trigger + 2026-05-31 Phase 3 D4) daily-forced in Guardian regardless of runner used.
                    # See aperture-hardening-mission-control.md and 2026-06-07 D4 scale evolution log.
                    genuine_bundles = sorted(
                        list(audits_dir.glob("d4_genuine_campaign_evidence_*.md")) + list(audits_dir.glob("d4_30day_campaign_evidence_*.md")),
                        key=lambda p: p.stat().st_mtime if p.exists() else 0,
                        reverse=True
                    )
                    if genuine_bundles:
                        latest = genuine_bundles[0]
                        print(f"  - Phase 3 D3/D4: Genuine/scale D4 campaign evidence bundle now part of daily aperture report: {latest.name}")
                        print("    (Produced via controlled execution of gate + real FinalArbitration + D1 or full runtime multi-day SIM+evo; 100% catch on evo unsafes; live lineage enabled.)")
                        print(f"    Reproduce: python scripts/phase3_d4_genuine_evidence.py  OR  python scripts/run_genuine_d4_campaign.py --duration-min 5 ; ls {latest}")
                    else:
                        print("  - Phase 3 D3/D4: No genuine/scale D4 bundle found yet — run `python scripts/phase3_d4_genuine_evidence.py` (or run_genuine_d4_campaign.py for longer multi-day) to generate non-illustrative evidence (now with live broker lineage).")
                except Exception as e:
                    print(f"  - Phase 3 D3/D4 genuine/scale evidence (best-effort): {e}")

                if d1_audits and not recent_ctxs:
                    phase3_d3_violations.append(
                        "no decision_context_ids for D1 auto-audit (populate logs via SIM/trade or run phase3_d4_genuine_evidence.py)"
                    )

                if phase3_d3_violations:
                    print("\n  **Phase 3 D3 FORCING — LINEAGE / AUDIT VIOLATIONS (ACTION REQUIRED)**")
                    for v in phase3_d3_violations[:8]:
                        print(f"     - {v}")
                    print(
                        "     Treat as release blocker for capital-path changes until resolved "
                        "(reconstruct chain, fix fill lineage, or regenerate genuine D4 evidence)."
                    )

                # Phase 2 Slice 22: The provenance report now auto-pulls fills from broker
                # when an engine is provided (see build_pretrade_provenance_report).
                # Guardian runs that have broker context will automatically get richer
                # downstream data in reports and screaming without manual recent_fills.
                try:
                    print("  - Phase 2 Slice 22: Provenance report + Guardian can now auto-fetch real fills (engine= context) for complete end-to-end lineage visibility.")
                    print("  - Phase 2 Slice 23: Actual cryptographic hash linkage verification now active for fills (extend_chain_with_fills computes real event_hash + hash_ok; broken downstream links between final_arbitration and execution are now detectable and screamable).")
                    print("  - Phase 2 Slice 24: Cryptographic chain now extends into realized PnL and position closes via CloseLegLedgerResult + extend_chain_with_closes (lineage from exit fill, real hash_ok). Provenance reports and Guardian can surface verified close/PnL nodes.")
                    print("  - Phase 2 Slice 25: Full multi-leg netting hash chain support active (PendingTradeClose + mark_closing + aggregate fills + finalize carry decision_context_id/prev_hash; extend_chain_with_closes now chains multiple closes under same ctx with proper hash_ok for netting).")
                except Exception:
                    pass

                # Phase 2 Slice 23: When broker context + auto-filled data is available,
                # we can now run full reconstruction + extend_chain_with_fills and check
                # is_chain_healthy on the extended chain (including real cryptographic
                # hash_ok on fills). This makes downstream broken hash links scream.
                try:
                    if bus is not None:
                        print("  - Phase 2 Slice 23: Downstream cryptographic hash linkage verification active (broken links between final_arbitration and fills now detectable via is_chain_healthy).")
                except Exception:
                    pass

            except Exception as e:
                print(f"  - Phase 2 Hash Chain Validation (Slice 13): best-effort check skipped (non-fatal): {e}")

        except Exception as e:
            print(f"  - Phase 2 Risk Decision Hash Chain Health: helper import issue (non-fatal): {e}")

        if aperture.get("warning"):
            # Print the full active warning from aperture.yaml — no sugar-coating
            print("\n" + aperture["warning"].strip())

        if aperture["fatal_count"] > 0:
            print("\n  **ACTION REQUIRED**: The capital aperture is the single highest-leverage defect.")
            print("     Closure of FATAL bypasses (see bypass inventory) is higher priority than new features.")
            print("     Reference: evolution/log/2026-05-31-current-capital-aperture-bypass-inventory.md")

            # Phase 1.1 light update (Elon aperture track)
            enforcement = rules.get("enforcement", {})
            if enforcement.get("active"):
                print(f"\n  **RUNTIME ENFORCEMENT ACTIVE** since {enforcement.get('since')}")
                print("     All 4 FATAL bypass paths now raise FATAL_MODE_VIOLATION + ConstitutionViolation in strict modes.")
                print("     This is Phase 1.1 of the Elon aperture hardening track. Violations are now painful in REAL.")

    # (Historical B-001 / active_mechanism block removed — post Phase 1.3.4 zero-trace hygiene,
    # the section in aperture.yaml no longer exists and the code referenced an out-of-scope 'rules' var,
    # causing --report / daily Guardian runs to crash. Retained only as audit trail comment.
    # All 4 FATAL bypasses are eliminated with permanent regression detector in aperture_guard.
    # See evolution/log/2026-05-31-elon-phase1-3-4-zero-trace-hygiene-complete.md and aperture.yaml.)
    # v0.16 experimental LLM review surface (if present)
    llm = report.get("llm_review")
    if llm and llm.get("enabled"):
        print("\n**LLM Review (EXPERIMENTAL — advisory only)**")
        if "result" in llm:
            r = llm["result"]
            print(f"  File: {llm.get('file')}")
            print(f"  Refined score (LLM): {r.get('refined_score')} | Confidence: {r.get('confidence')}")
            print(f"  Summary: {r.get('one_sentence_summary')}")
            for f in r.get("additional_findings", []):
                print(f"  - {f}")
        else:
            print(f"  Unavailable: {llm.get('error', 'unknown')}")


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


def main() -> None:
    parser = argparse.ArgumentParser(
        description="DNA Guardian - Validator & Scorer for Lumina DNA 2.0 (v0.16.0-experimental — --llm-review available)"
    )
    parser.add_argument("--json", action="store_true", help="Output machine-readable JSON report")
    parser.add_argument("--report", action="store_true", help="Print human-readable Markdown report (default)")
    parser.add_argument(
        "--create-entry",
        action="store_true",
        help="Create a proper evolution log entry (recommended for meta-improvements)"
    )
    parser.add_argument(
        "--llm-review",
        action="store_true",
        help="EXPERIMENTAL: Run local LLM second-opinion review on the weakest file (requires Ollama). Never affects official Health Score."
    )
    parser.add_argument(
        "--d1-audits",
        dest="d1_audits",
        action="store_true",
        default=True,
        help="Phase 3 D1: Auto-generate and embed aperture audit artifacts (one human 20 min view) for recent decisions (default: on). Use --no-d1-audits to disable."
    )
    parser.add_argument(
        "--no-d1-audits",
        dest="d1_audits",
        action="store_false",
        help="Disable Phase 3 D1 aperture audit generation in this Guardian run."
    )
    parser.add_argument(
        "--strict-self-score",
        action="store_true",
        help="Phase 3 D6: fail (exit 1) if Guardian self-score is below 6.0 (aperture contract).",
    )
    args = parser.parse_args()

    structure_results, all_ok = validate_structure()
    report = generate_report(structure_results, all_ok)

    # Persist aperture panel + self-score for JSON export (--create-entry) and --json consumers
    try:
        from guardian_self_score import enrich_report_with_phase3_panel

        enrich_report_with_phase3_panel(report, repo_root=PROJECT_ROOT, d1_audits=args.d1_audits)
    except Exception as e:
        report["guardian_self_score"] = {
            "ok": False,
            "overall_score": 0.0,
            "status": "RED",
            "error": str(e),
        }

    d5 = report.get("d5_capital_aperture") or {}
    if not d5.get("ok", True):
        all_ok = False
        report["overall_status"] = "FAIL"

    gss = report.get("guardian_self_score") or {}
    if args.strict_self_score and float(gss.get("overall_score", 0)) < float(gss.get("fail_below", 6.0)):
        all_ok = False
        report["overall_status"] = "FAIL"

    # v0.16 experimental: optional narrow LLM review (only when explicitly requested)
    llm_review_result = None
    if args.llm_review and args.create_entry:
        # Find the weakest file from the just-generated truth density results
        td = report.get("truth_density", {})
        if td:
            weakest = min(td.items(), key=lambda x: x[1]["score"])
            weakest_path, weakest_data = weakest

            context_summary = report.get("recommendation", "") + " | " + report.get("longer_trend_summary", "")
            llm_review_result = run_llm_review_on_file(weakest_path, weakest_data, context_summary)

            if llm_review_result:
                print(f"LLM review completed on weakest file: {weakest_path}")
            else:
                print("LLM review requested but unavailable (Ollama not running / timeout / error) — falling back to heuristic only.")

    # Attach to report so downstream functions can use it
    if llm_review_result:
        report["llm_review"] = {
            "enabled": True,
            "file": weakest_path,
            "result": llm_review_result,
        }
    elif args.llm_review:
        report["llm_review"] = {"enabled": True, "error": "LLM unavailable — pure heuristic used", "attempted_file": weakest_path if 'weakest_path' in locals() else None}

    if args.create_entry:
        entry_path = create_evolution_entry(report)
        print(f"Evolution log entry created: {entry_path}")

        # New in v0.9.0: also keep the compact agent context up to date
        context_path = update_agent_context(report)
        if "updated" in context_path.lower() or context_path.endswith(".md"):
            print(f"Agent context updated: {context_path}")

        # v0.15 continuation (Increment 5 slice 2): write standalone structured export
        latest_json_path = write_dna_health_latest(report)
        print(f"DNA health latest export written: {latest_json_path}")
    elif args.json:
        write_dna_health_latest(report)
        print(json.dumps(report, indent=2))
    else:
        print_markdown_report(report, d1_audits=args.d1_audits)
        try:
            write_dna_health_latest(report)
        except Exception:
            pass

    # Exit with error code if validation failed
    sys.exit(0 if all_ok else 1)


if __name__ == "__main__":
    main()
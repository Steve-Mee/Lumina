"""Dream Engine – thousands of fast what-if paths before DNA mutation.

Lightweight forward roll of equity shocks around the nightly report to surface
tail drawdowns and emit compact rule hints for evolution / logging.
"""

from __future__ import annotations
import logging

import json
import random
from dataclasses import dataclass
from typing import Any

from lumina_core.config_loader import ConfigLoader


@dataclass(slots=True)
class DreamReport:
    dream_count: int
    breach_count: int
    breach_rate: float
    worst_dd_ratio: float
    median_terminal_equity_delta: float
    rule_hints: tuple[str, ...]


def dream_engine_config() -> tuple[bool, int, int, float]:
    """Returns enabled, dream_count, horizon_days, drawdown_limit_ratio."""
    evolution_cfg = ConfigLoader.section("evolution", default={}) or {}
    de = evolution_cfg.get("dream_engine", {}) if isinstance(evolution_cfg, dict) else {}
    if not isinstance(de, dict):
        return True, 4000, 7, 0.02
    enabled = bool(de.get("enabled", True))
    try:
        n = int(de.get("dream_count", 4000) or 4000)
    except (TypeError, ValueError):
        n = 4000
    n = max(200, min(50_000, n))
    try:
        h = int(de.get("horizon_days", 7) or 7)
    except (TypeError, ValueError):
        h = 7
    h = max(1, min(60, h))
    try:
        ddr = float(de.get("drawdown_limit_ratio", 0.02) or 0.02)
    except (TypeError, ValueError):
        ddr = 0.02
    ddr = max(0.005, min(0.25, ddr))
    return enabled, n, h, ddr


def run_dream_batch(
    nightly_report: dict[str, Any],
    *,
    dream_count: int,
    horizon_days: int,
    seed: int,
    drawdown_limit_ratio: float = 0.02,
) -> DreamReport:
    """Run ``dream_count`` independent fast-forward equity paths (vector-free, CPU-cheap)."""
    rng = random.Random(seed)
    base_eq = max(1.0, float(nightly_report.get("account_equity", 50_000.0) or 50_000.0))
    base_dd = abs(float(nightly_report.get("max_drawdown", 0.0) or 0.0))
    base_pnl = float(nightly_report.get("net_pnl", 0.0) or 0.0)
    vol_scale = max(1.0, base_dd / max(1.0, base_eq * 0.5))

    breaches = 0
    worst_dd = 0.0
    terminal_deltas: list[float] = []

    n = max(1, int(dream_count))
    horizon = max(1, int(horizon_days))

    for _ in range(n):
        peak = base_eq
        equity = base_eq
        max_dd_ratio = 0.0
        for _d in range(horizon):
            noise = rng.gauss(0.0, 0.14 * vol_scale)
            daily_pnl = (base_pnl / float(horizon)) * (1.0 + noise) + rng.gauss(0.0, base_eq * 0.0012 * vol_scale)
            equity += float(daily_pnl)
            peak = max(peak, equity)
            dd_ratio = max(0.0, (peak - equity) / base_eq)
            max_dd_ratio = max(max_dd_ratio, dd_ratio)

        if max_dd_ratio > drawdown_limit_ratio:
            breaches += 1
        worst_dd = max(worst_dd, max_dd_ratio)
        terminal_deltas.append((equity - base_eq) / base_eq)

    terminal_deltas.sort()
    mid = len(terminal_deltas) // 2
    median_delta = float(terminal_deltas[mid]) if terminal_deltas else 0.0
    breach_rate = breaches / float(n)

    hints: list[str] = []
    if breach_rate > 0.12:
        hints.append("strengthen_drawdown_kill_in_whatif_tail")
    if breach_rate > 0.22:
        hints.append("widen_challenger_pool_under_dream_stress")
    if median_delta < -0.015:
        hints.append("bias_regime_gates_toward_defensive")
    if worst_dd > drawdown_limit_ratio * 1.8:
        hints.append("flash_drawdown_escape_and_size_cap")

    return DreamReport(
        dream_count=n,
        breach_count=breaches,
        breach_rate=float(breach_rate),
        worst_dd_ratio=float(worst_dd),
        median_terminal_equity_delta=float(median_delta),
        rule_hints=tuple(hints),
    )


def enrich_nightly_report_with_dream(
    base: dict[str, Any],
    dream_summary: dict[str, Any] | None,
) -> dict[str, Any]:
    """Attach structured dream learnings to the nightly report for fitness, swarm, and sim."""
    out = dict(base)
    if not dream_summary or not dream_summary.get("enabled", True):
        out.pop("dream_engine", None)
        return out
    out["dream_engine"] = {
        "breach_rate": float(dream_summary.get("breach_rate", 0.0) or 0.0),
        "worst_dd_ratio": float(dream_summary.get("worst_dd_ratio", 0.0) or 0.0),
        "median_terminal_equity_delta": float(dream_summary.get("median_terminal_equity_delta", 0.0) or 0.0),
        "rule_hints": [str(x) for x in (dream_summary.get("rule_hints") or []) if str(x).strip()],
        "dream_count": int(dream_summary.get("dream_count", 0) or 0),
    }
    return out


# Per-hint multipliers: (max_risk_mult, drawdown_kill_mult). Values <1 tighten / reduce size & tolerance.
_DREAM_HINT_HYPERPARAM_NUDGE: dict[str, tuple[float, float]] = {
    "strengthen_drawdown_kill_in_whatif_tail": (0.97, 0.94),
    "widen_challenger_pool_under_dream_stress": (0.98, 1.0),
    "bias_regime_gates_toward_defensive": (0.90, 0.93),
    "flash_drawdown_escape_and_size_cap": (0.85, 0.90),
}


def dream_risk_nudge_settings() -> tuple[bool, frozenset[str]]:
    """apply_risk_nudges, allowed evolution modes (default sim+paper, not real)."""
    evolution_cfg = ConfigLoader.section("evolution", default={}) or {}
    de = evolution_cfg.get("dream_engine", {}) if isinstance(evolution_cfg, dict) else {}
    if not isinstance(de, dict):
        return False, frozenset()
    if not bool(de.get("apply_risk_nudges", True)):
        return False, frozenset()
    raw = de.get("risk_nudge_modes", ["sim", "paper"])
    if not isinstance(raw, (list, tuple)):
        raw = ["sim", "paper"]
    modes = {str(x).strip().lower() for x in raw if str(x).strip()}
    if not modes:
        modes = {"sim", "paper"}
    return True, frozenset(modes)


def merge_dream_hyperparam_nudges(
    base_hs: dict[str, float],
    dream_summary: dict[str, Any] | None,
    *,
    evolution_mode: str,
) -> dict[str, Any]:
    """Bounded nudges to max_risk_percent / drawdown_kill_percent from dream hints.

    Returns dict with max_risk_percent, drawdown_kill_percent, and _nudged: bool.
    When disabled or same mode not allowed, returns base values and _nudged False.
    """
    out_mr = float(base_hs.get("max_risk_percent", 1.0) or 1.0)
    out_dk = float(base_hs.get("drawdown_kill_percent", 8.0) or 8.0)
    apply, modes = dream_risk_nudge_settings()
    em = str(evolution_mode or "sim").strip().lower()
    if not apply or em not in modes:
        return {
            "max_risk_percent": out_mr,
            "drawdown_kill_percent": out_dk,
            "_nudged": False,
        }
    if not dream_summary or not dream_summary.get("enabled", True):
        return {
            "max_risk_percent": out_mr,
            "drawdown_kill_percent": out_dk,
            "_nudged": False,
        }
    hints = [str(x) for x in (dream_summary.get("rule_hints") or []) if str(x).strip()]
    br = float(dream_summary.get("breach_rate", 0.0) or 0.0)
    if not hints and br < 0.06:
        return {
            "max_risk_percent": out_mr,
            "drawdown_kill_percent": out_dk,
            "_nudged": False,
        }

    m_mr = 1.0
    m_dk = 1.0
    for h in hints:
        pair = _DREAM_HINT_HYPERPARAM_NUDGE.get(h)
        if pair is None:
            continue
        m_mr *= float(pair[0])
        m_dk *= float(pair[1])
    if br > 0.15:
        m_mr *= 0.97
        m_dk *= 0.98
    if br > 0.25:
        m_mr *= 0.96
        m_dk *= 0.97

    mr2 = max(0.2, min(4.0, out_mr * m_mr))
    dk2 = max(2.0, min(32.0, out_dk * m_dk))
    nudged = abs(mr2 - out_mr) > 1e-6 or abs(dk2 - out_dk) > 1e-6
    return {
        "max_risk_percent": round(mr2, 4),
        "drawdown_kill_percent": round(dk2, 4),
        "_nudged": bool(nudged),
    }


# Hint id → tokens we expect a responsive policy to mention (substring match, lowercase).
_DREAM_HINT_LEXICON: dict[str, tuple[str, ...]] = {
    "strengthen_drawdown_kill_in_whatif_tail": (
        "drawdown",
        "capital",
        "risk",
        "kill",
        "preserve",
        "dd",
    ),
    "widen_challenger_pool_under_dream_stress": (
        "challenger",
        "diversity",
        "explore",
        "pool",
        "variant",
    ),
    "bias_regime_gates_toward_defensive": (
        "defensive",
        "regime",
        "hold",
        "caution",
        "gate",
    ),
    "flash_drawdown_escape_and_size_cap": (
        "size",
        "cap",
        "flash",
        "escape",
        "reduce",
        "exposure",
    ),
}


def _policy_text_for_alignment(content: Any) -> str:
    raw = str(content or "").strip()
    if not raw.startswith("{"):
        return raw.lower()
    try:
        payload = json.loads(raw)
    except Exception:
        logging.exception("Unhandled broad exception fallback in lumina_core/evolution/dream_engine.py:265")
        return raw.lower()
    if not isinstance(payload, dict):
        return raw.lower()
    parts: list[str] = []
    for key in (
        "prompt_tweak",
        "candidate_name",
        "dream_learnings",
        "hyperparam_suggestion",
    ):
        val = payload.get(key)
        if isinstance(val, str):
            parts.append(val)
        elif isinstance(val, dict):
            parts.append(json.dumps(val, ensure_ascii=True))
    return " ".join(parts).lower()


def dream_policy_alignment_bonus(
    content: Any,
    dream_block: dict[str, Any] | None,
    *,
    max_bonus: float = 0.12,
) -> float:
    """Extra fitness when policy text encodes the same concerns as active dream rule hints.

    Scales with breach_rate so under tail stress, alignment matters more to selection.
    """
    if not dream_block or not isinstance(dream_block, dict):
        return 0.0
    hints = [str(h).strip() for h in (dream_block.get("rule_hints") or []) if str(h).strip()]
    if not hints:
        return 0.0
    br = float(dream_block.get("breach_rate", 0.0) or 0.0)
    text = _policy_text_for_alignment(content)
    if not text:
        return 0.0
    matched = 0
    for h in hints:
        tokens = _DREAM_HINT_LEXICON.get(h, (h.replace("_", " "),))
        if any(tok in text for tok in tokens):
            matched += 1
    if matched == 0:
        return 0.0
    # Up to max_bonus when all active hints have lexical support; scale by stress.
    stress = min(1.0, max(0.0, br) * 2.5 + 0.15)
    per = float(max_bonus) / max(1, len(hints))
    return min(float(max_bonus), per * float(matched) * (0.65 + 0.35 * stress))

"""AUDIT / VERDICT markdown for genesis HOLD_COMPARE."""

from __future__ import annotations

import json
from typing import Any

from lumina_core.birth.genesis_hold_compare_tables import HONESTY_PARAGRAPH


def _json(payload: Any) -> str:
    return json.dumps(payload, indent=2, default=str)


def render_audit(
    *,
    gate0: dict[str, Any],
    t0: dict[str, Any],
    t1: dict[str, Any],
    t2_a: dict[str, Any],
    t2_b: dict[str, Any],
    t3: dict[str, Any],
    flags: dict[str, Any],
) -> str:
    lines = [
        "# GENESIS_HOLD_COMPARE_AUDIT",
        "",
        "## Gate 0 live-check",
        "",
        "```json",
        _json(gate0),
        "```",
        "",
        "## T0 identity",
        "",
        "```json",
        _json(t0),
        "```",
        "",
        "## T1 honesty",
        "",
        "```json",
        _json(t1),
        "```",
        "",
        "## T2 hold compare",
        "",
        "### Leg A",
        "",
        "```json",
        _json(t2_a),
        "```",
        "",
        "### Leg B",
        "",
        "```json",
        _json(t2_b),
        "```",
        "",
        "## T3 license",
        "",
        "```json",
        _json(t3),
        "```",
        "",
        "## Honesty",
        "",
        HONESTY_PARAGRAPH,
        "",
        "PR #35 G5 remains GENESIS_EYES_FAIL. n_policy 113/103 restated. Floor 150 stays.",
        "GENESIS_EYES_OK is forbidden. learn() was not called. REAL=no.",
        "",
        "## flags",
        "",
        "```json",
        _json(flags),
        "```",
        "",
    ]
    return "\n".join(lines)


def render_verdict(*, flags: dict[str, Any], t2_a: dict[str, Any], t2_b: dict[str, Any]) -> str:
    lines = [
        "# GENESIS_HOLD_COMPARE_VERDICT",
        "",
        f"**tag:** `{flags.get('tag')}`",
        f"**gate1_tag:** `{flags.get('gate1_tag')}`",
        f"**gate2_tag:** `{flags.get('gate2_tag')}`",
        f"**law:** `{flags.get('law')}`",
        f"**licensed_next_family:** `{flags.get('licensed_next_family')}`",
        f"**GENESIS_EYES_OK:** `{flags.get('GENESIS_EYES_OK')}`",
        f"**learn_called:** `{flags.get('learn_called')}`",
        f"**REAL:** `{flags.get('REAL')}`",
        f"**n_policy_A_child:** `{flags.get('n_policy_A_child')}`",
        f"**n_policy_B_child:** `{flags.get('n_policy_B_child')}`",
        f"**HOLE_MOVED_A:** `{flags.get('HOLE_MOVED_A')}`",
        f"**HOLE_MOVED_B:** `{flags.get('HOLE_MOVED_B')}`",
        "",
        "Cause rule was pinned before looking at numbers. Floor 150 is not met.",
        "",
        f"- Leg A cause `{t2_a.get('cause_tag')}` n_policy birth/child "
        f"{t2_a.get('n_policy_birth')}/{t2_a.get('n_policy_child')} "
        f"bars_held_p50 {t2_a.get('bars_held_p50_birth')}/{t2_a.get('bars_held_p50_child')}",
        f"- Leg B cause `{t2_b.get('cause_tag')}` n_policy birth/child "
        f"{t2_b.get('n_policy_birth')}/{t2_b.get('n_policy_child')} "
        f"bars_held_p50 {t2_b.get('bars_held_p50_birth')}/{t2_b.get('bars_held_p50_child')}",
        "",
        "## Honesty",
        "",
        HONESTY_PARAGRAPH,
        "",
        "VERDICT is from disk flags, not memory.",
        "",
    ]
    return "\n".join(lines)


__all__ = ["render_audit", "render_verdict"]

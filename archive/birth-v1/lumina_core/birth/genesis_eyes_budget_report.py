"""AUDIT / VERDICT markdown for GENESIS_EYES_BUDGET."""

from __future__ import annotations

import json
from typing import Any

from lumina_core.birth.genesis_eyes_budget_tables import HONESTY_PARAGRAPH


def _json(payload: Any) -> str:
    return json.dumps(payload, indent=2, default=str)


def render_audit(
    *,
    gate0: dict[str, Any],
    proto: dict[str, Any],
    t0: dict[str, Any],
    t1: dict[str, Any],
    t2_a: dict[str, Any],
    t2_b: dict[str, Any],
    t3: dict[str, Any],
    flags: dict[str, Any],
    g6: dict[str, Any],
) -> str:
    return "\n".join(
        [
            "# GENESIS_EYES_BUDGET_AUDIT",
            "",
            "## Gate 0 live-check + inspect_budget_protocol",
            "",
            "```json",
            _json(gate0),
            "```",
            "",
            "```json",
            _json(proto),
            "```",
            "",
            "## T0 identity",
            "",
            "```json",
            _json(t0),
            "```",
            "",
            "## T1 honesty / G1 fixture",
            "",
            "```json",
            _json(t1),
            "```",
            "",
            "## T2 evaluate-only (newborn vs child on THIS tape)",
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
            "## G4 REAL door",
            "",
            "```json",
            _json(g6),
            "```",
            "",
            "## Honesty",
            "",
            HONESTY_PARAGRAPH,
            "",
            "G5 genesis half-ledgers were not overwritten. learn() was not called.",
            "GENESIS_EYES_OK is false. REAL=no. Floor 150.",
            "",
            "## flags",
            "",
            "```json",
            _json(flags),
            "```",
            "",
        ]
    )


def render_verdict(*, flags: dict[str, Any], t2_a: dict[str, Any], t2_b: dict[str, Any]) -> str:
    return "\n".join(
        [
            "# GENESIS_EYES_BUDGET_VERDICT",
            "",
            f"**tag:** `{flags.get('tag')}`",
            f"**law:** `{flags.get('law')}`",
            f"**licensed_next_family:** `{flags.get('licensed_next_family')}`",
            f"**GENESIS_EYES_OK:** `{flags.get('GENESIS_EYES_OK')}`",
            f"**learn_called:** `{flags.get('learn_called')}`",
            f"**REAL:** `{flags.get('REAL')}`",
            f"**G6_tag:** `{flags.get('G6_tag')}`",
            f"**fixture_train_hash:** `{flags.get('fixture_train_hash')}`",
            f"**holdout_tick_count:** `{flags.get('holdout_tick_count')}`",
            f"**ticks_per_leg:** `{flags.get('ticks_per_leg')}`",
            f"**HOLE_MOVED_A:** `{flags.get('HOLE_MOVED_A')}`",
            f"**HOLE_MOVED_B:** `{flags.get('HOLE_MOVED_B')}`",
            "",
            f"- Leg A n_policy birth/child {t2_a.get('n_policy_birth')}/{t2_a.get('n_policy_child')} "
            f"n_H {t2_a.get('n_H_birth')}/{t2_a.get('n_H_child')} "
            f"mean_r {t2_a.get('mean_r_birth')}/{t2_a.get('mean_r_child')} "
            f"bars_held_p50 {t2_a.get('bars_held_p50_birth')}/{t2_a.get('bars_held_p50_child')} "
            f"HOLE_MOVED={t2_a.get('HOLE_MOVED')} S_THIN={t2_a.get('S_THIN')}",
            f"- Leg B n_policy birth/child {t2_b.get('n_policy_birth')}/{t2_b.get('n_policy_child')} "
            f"n_H {t2_b.get('n_H_birth')}/{t2_b.get('n_H_child')} "
            f"mean_r {t2_b.get('mean_r_birth')}/{t2_b.get('mean_r_child')} "
            f"bars_held_p50 {t2_b.get('bars_held_p50_birth')}/{t2_b.get('bars_held_p50_child')} "
            f"HOLE_MOVED={t2_b.get('HOLE_MOVED')} S_THIN={t2_b.get('S_THIN')}",
            "",
            "## Honesty",
            "",
            HONESTY_PARAGRAPH,
            "",
            "VERDICT is from disk flags, not memory.",
            "",
        ]
    )


__all__ = ["render_audit", "render_verdict"]

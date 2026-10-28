"""AUDIT / VERDICT markdown for AWAKENING_PHYSICS_TAPE."""

from __future__ import annotations

import json
from typing import Any

from lumina_core.birth.awakening_physics_tables import HONESTY_PARAGRAPH


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
            "# AWAKENING_PHYSICS_TAPE_AUDIT",
            "",
            "## Gate 0 live-check + inspect_physics_protocol",
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
            "## T1 honesty / G1 physics fixture",
            "",
            "```json",
            _json(t1),
            "```",
            "",
            "## T2 G2 a9ffa852 vs G4 scratch V1 child on THIS tape",
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
            "## T3 license vs G2 books",
            "",
            "```json",
            _json(t3),
            "```",
            "",
            "## G6 REAL door",
            "",
            "```json",
            _json(g6),
            "```",
            "",
            "## Honesty",
            "",
            HONESTY_PARAGRAPH,
            "",
            "Origin genesis/budget/polish/v2 artifacts were not overwritten.",
            "GENESIS_EYES_OK is false. used_v2_child is false. REAL=no. Floor 150. Scratch 10k.",
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
            "# AWAKENING_PHYSICS_TAPE_VERDICT",
            "",
            f"**tag:** `{flags.get('tag')}`",
            f"**law:** `{flags.get('law')}`",
            f"**licensed_next_family:** `{flags.get('licensed_next_family')}`",
            f"**GENESIS_EYES_OK:** `{flags.get('GENESIS_EYES_OK')}`",
            f"**world_ok:** `{flags.get('world_ok')}`",
            f"**init_policy:** `{flags.get('init_policy')}`",
            f"**learn_called:** `{flags.get('learn_called')}`",
            f"**actual_timesteps:** `{flags.get('actual_timesteps')}`",
            f"**REAL:** `{flags.get('REAL')}`",
            f"**G6_tag:** `{flags.get('G6_tag')}`",
            f"**fixture_train_hash:** `{flags.get('fixture_train_hash')}`",
            f"**baseline_sha256:** `{str(flags.get('baseline_sha256') or '')[:16]}`",
            f"**child_sha256:** `{str(flags.get('child_sha256') or '')[:16]}`",
            f"**trend_up_frac_holdout:** `{flags.get('trend_up_frac_holdout')}`",
            f"**trend_down_frac_holdout:** `{flags.get('trend_down_frac_holdout')}`",
            f"**MOVED_A:** `{flags.get('MOVED_A')}`",
            f"**MOVED_B:** `{flags.get('MOVED_B')}`",
            "",
            f"- Leg A n_policy base/child {t2_a.get('n_policy_base')}/{t2_a.get('n_policy_child')} "
            f"n_H {t2_a.get('n_H_base')}/{t2_a.get('n_H_child')} "
            f"mean_r {t2_a.get('mean_r_base')}/{t2_a.get('mean_r_child')} "
            f"Δmean_r {t2_a.get('delta_mean_r')} HOLE_OK={t2_a.get('HOLE_OK')} "
            f"MOVED={t2_a.get('MOVED')} S_THIN={t2_a.get('S_THIN')} S_HARM={t2_a.get('S_HARM')}",
            f"- Leg B n_policy base/child {t2_b.get('n_policy_base')}/{t2_b.get('n_policy_child')} "
            f"n_H {t2_b.get('n_H_base')}/{t2_b.get('n_H_child')} "
            f"mean_r {t2_b.get('mean_r_base')}/{t2_b.get('mean_r_child')} "
            f"Δmean_r {t2_b.get('delta_mean_r')} HOLE_OK={t2_b.get('HOLE_OK')} "
            f"MOVED={t2_b.get('MOVED')} S_THIN={t2_b.get('S_THIN')} S_HARM={t2_b.get('S_HARM')}",
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

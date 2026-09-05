"""AUDIT / VERDICT markdown for AWAKENING_GEOMETRY_REWARD."""

from __future__ import annotations

import json
from typing import Any

from lumina_core.birth.awakening_geom_tables import HONESTY_PARAGRAPH


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
    touch: dict[str, Any] | None = None,
) -> str:
    return "\n".join(
        [
            "# AWAKENING_GEOMETRY_REWARD_AUDIT",
            "",
            "## Gate 0 live-check + inspect_geom_protocol",
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
            "## T1 honesty / G1 geom fixture",
            "",
            "```json",
            _json(t1),
            "```",
            "",
            "## G2 first-touch",
            "",
            "```json",
            _json(touch or {}),
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
            "## G5 REAL door",
            "",
            "```json",
            _json(g6),
            "```",
            "",
            "## Honesty",
            "",
            HONESTY_PARAGRAPH,
            "",
            "Origin scale artifacts were not overwritten.",
            "GENESIS_EYES_OK is false. oracle_regime is false. REAL=no. Floor 150.",
            "FORCE_OPEN train-only. 1% guard not patched. Production enricher default remains ±0.15.",
            "DRIFT_RTH used is 8.0e-6. PHYSICS_SLOPE_ABS used is 0.004.",
            "world_engineering_closed is true. First-touch gate 0.10. Policy goal 0.46 is not the gate.",
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
            "# AWAKENING_GEOMETRY_REWARD_VERDICT",
            "",
            f"**tag:** `{flags.get('tag')}`",
            f"**law:** `{flags.get('law')}`",
            f"**licensed_next_family:** `{flags.get('licensed_next_family')}`",
            f"**GENESIS_EYES_OK:** `{flags.get('GENESIS_EYES_OK')}`",
            f"**in_band:** `{flags.get('in_band')}`",
            f"**world_ok:** `{flags.get('world_ok')}`",
            f"**world_engineering_closed:** `{flags.get('world_engineering_closed')}`",
            f"**unhittable:** `{flags.get('unhittable')}`",
            f"**target_frac:** `{flags.get('target_frac')}`",
            f"**stop_frac:** `{flags.get('stop_frac')}`",
            f"**time_frac:** `{flags.get('time_frac')}`",
            f"**target_frac_min:** `{flags.get('target_frac_min')}`",
            f"**geom_win_r:** `{flags.get('geom_win_r')}`",
            f"**geom_loss_r:** `{flags.get('geom_loss_r')}`",
            f"**drift_rth:** `{flags.get('drift_rth')}`",
            f"**phase_blocks:** `{flags.get('phase_blocks')}`",
            f"**seed_used:** `{flags.get('seed_used')}`",
            f"**train_force_open:** `{flags.get('train_force_open')}`",
            f"**eval_force_open:** `{flags.get('eval_force_open')}`",
            f"**slope_abs_used:** `{flags.get('slope_abs_used')}`",
            f"**prod_slope_abs:** `{flags.get('prod_slope_abs')}`",
            f"**floor_waived:** `{flags.get('floor_waived')}`",
            f"**guard_bypassed:** `{flags.get('guard_bypassed')}`",
            f"**init_policy:** `{flags.get('init_policy')}`",
            f"**learn_called:** `{flags.get('learn_called')}`",
            f"**actual_timesteps:** `{flags.get('actual_timesteps')}`",
            f"**REAL:** `{flags.get('REAL')}`",
            f"**G6_tag:** `{flags.get('G6_tag')}`",
            f"**oracle_regime:** `{flags.get('oracle_regime')}`",
            f"**fixture_train_hash:** `{flags.get('fixture_train_hash')}`",
            f"**baseline_sha256:** `{str(flags.get('baseline_sha256') or '')[:16]}`",
            f"**child_sha256:** `{str(flags.get('child_sha256') or '')[:16]}`",
            f"**MOVED_A:** `{flags.get('MOVED_A')}`",
            f"**MOVED_B:** `{flags.get('MOVED_B')}`",
            "",
            f"- attempts={flags.get('attempts')}",
            f"- first-touch target/stop/time={flags.get('target_frac')}/{flags.get('stop_frac')}/{flags.get('time_frac')}",
            f"- Leg A n_policy base/child {t2_a.get('n_policy_base')}/{t2_a.get('n_policy_child')} "
            f"mean_r {t2_a.get('mean_r_base')}/{t2_a.get('mean_r_child')} "
            f"Δmean_r {t2_a.get('delta_mean_r')} HOLE_OK={t2_a.get('HOLE_OK')} "
            f"MOVED={t2_a.get('MOVED')} S_THIN={t2_a.get('S_THIN')} S_HARM={t2_a.get('S_HARM')}",
            f"- Leg B n_policy base/child {t2_b.get('n_policy_base')}/{t2_b.get('n_policy_child')} "
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

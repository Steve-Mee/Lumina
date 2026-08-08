"""Shadow report builder for self-play lab (Phase 0)."""

from __future__ import annotations

from typing import Any, Mapping

from lumina_core.birth.self_play.gates import (
    evaluate_self_play_gate,
    is_champion_freeze_active,
    is_real_like_capital,
)
from lumina_core.birth.self_play.scorer import rank_self_play_variants
from lumina_core.birth.self_play.types import SelfPlayLabConfig, SelfPlayVariantResult

# Offline fixture used by CLI/tests — pure ranking, no market data.
FIXTURE_VARIANTS: list[SelfPlayVariantResult] = [
    SelfPlayVariantResult(
        variant_id="champion",
        trades=100,
        wins=45,
        total_pnl=-2.0,
        label="baseline champion",
    ),
    # Clear lift vs champion above statistical floor (0.5/sqrt(n) at n=100 → 0.05)
    SelfPlayVariantResult(
        variant_id="challenger_a",
        trades=100,
        wins=60,
        total_pnl=20.0,
        label="challenger A",
    ),
    SelfPlayVariantResult(
        variant_id="challenger_b",
        trades=100,
        wins=40,
        total_pnl=-8.0,
        label="challenger B",
    ),
]


def build_self_play_lab_report(
    *,
    config: SelfPlayLabConfig | None = None,
    variants: list[SelfPlayVariantResult] | None = None,
    progress: Mapping[str, Any] | None = None,
    capital_mode: str | None = None,
    champion_score: float | None = None,
    use_fixture: bool = False,
) -> dict[str, Any]:
    """Build schema self_play_lab_v1 — never mutates progress or places orders."""
    cfg = config or SelfPlayLabConfig()
    cap = capital_mode if capital_mode is not None else cfg.capital_mode_hint
    gate = evaluate_self_play_gate(
        config=cfg,
        capital_mode=cap,
        progress=progress,
        for_apply=False,
    )

    results = list(variants or [])
    if use_fixture and not results:
        results = list(FIXTURE_VARIANTS)

    # Ranking is pure and always available for offline fixture even if lab disabled
    # (report still shows gate.allowed=false when disabled).
    champion_baseline = champion_score
    if champion_baseline is None and results:
        # Prefer explicit champion variant id
        for r in results:
            if r.variant_id == "champion":
                from lumina_core.birth.self_play.scorer import score_variant

                champion_baseline = score_variant(r)
                break

    ranked = (
        rank_self_play_variants(
            results,
            champion_score=champion_baseline,
            meaningful_delta=cfg.meaningful_lift_delta,
        )
        if results
        else []
    )

    findings: list[dict[str, Any]] = [
        {
            "id": "gate",
            "ok": gate.allowed,
            "reason": gate.reason,
            "detail": gate.detail,
        },
        {
            "id": "real_capital",
            "ok": not is_real_like_capital(cap),
            "detail": f"capital_mode={cap}",
        },
        {
            "id": "champion_freeze",
            "ok": not is_champion_freeze_active(progress),
            "detail": "freeze inactive" if not is_champion_freeze_active(progress) else "freeze active",
        },
        {
            "id": "apply_path",
            "ok": True,
            "detail": "Phase 0 shadow only — apply deferred",
        },
    ]

    ordered_actions: list[str] = []
    if not cfg.enabled:
        ordered_actions.append(
            "Lab disabled by default — set SelfPlayLabConfig(enabled=True) only in SIM lab"
        )
    if is_real_like_capital(cap):
        ordered_actions.append("Refuse REAL capital — run self-play under sim/birth only")
    if is_champion_freeze_active(progress):
        ordered_actions.append(
            "Champion freeze active — accept_champion or wipe before any training path"
        )
    if gate.allowed and ranked:
        best = ranked[0]
        ordered_actions.append(
            f"Shadow best={best.get('variant_id')} score={best.get('tournament_score')} "
            f"(no apply — report only)"
        )
    if not ordered_actions:
        ordered_actions.append(
            "python scripts/validation/self_play_lab_gate.py --fixture"
        )

    # ok: gate may be false when disabled (soft for CI fixture path)
    # hard fail only on REAL or freeze when enabled
    hard_fail = False
    if is_real_like_capital(cap):
        hard_fail = True
    if cfg.enabled and is_champion_freeze_active(progress):
        hard_fail = True

    return {
        "schema": "self_play_lab_v1",
        "ok": not hard_fail,
        "phase": "0_lab_scaffold",
        "enabled": bool(cfg.enabled),
        "capital_mode": cap,
        "gate": gate.as_dict(),
        "champion_baseline": champion_baseline,
        "variant_count": len(results),
        "ranked": ranked,
        "findings": findings,
        "ordered_actions": ordered_actions,
        "forbidden": [
            "auto_REAL",
            "yaml_twin_full_auto_force",
            "cert_floor_drop",
            "architecture_auto_apply",
            "train_through_champion_freeze",
            "birth_progress_mutation_phase0",
        ],
        "commands": {
            "gate": "python scripts/validation/self_play_lab_gate.py",
            "fixture": "python scripts/validation/self_play_lab_gate.py --fixture",
            "twin_ssot": "python scripts/validation/twin_mode_ssot_audit.py",
            "pb_campaign": "python scripts/validation/perfect_birth_campaign.py",
        },
        "operator_residuals": [
            "OR1 Fabric live SAFE_MODE / HB cancel (NT8)",
            "OR2 aperture ≥95% live samples",
            "OR3 Perfect Birth campaign evidence + declare",
            "OR4 twin promote ladder + SSOT",
            "OR5 live champion freeze accept/wipe",
            "OR6 recovery theater — no ladder spin",
        ],
    }

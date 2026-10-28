"""Pure self-play ranking via tournament_score (no new vanity metric)."""

from __future__ import annotations

from typing import Any

from lumina_core.birth.self_play.types import SelfPlayVariantResult
from lumina_core.birth.starship_swarm_gates import (
    swarm_tournament_lift,
    tournament_score,
)


def score_variant(result: SelfPlayVariantResult) -> float:
    """Tournament score for one variant; empty sample → -1."""
    return tournament_score(
        trades=int(result.trades),
        wins=int(result.wins),
        total_pnl=float(result.total_pnl),
    )


def rank_self_play_variants(
    results: list[SelfPlayVariantResult],
    *,
    champion_score: float | None = None,
    meaningful_delta: float = 0.01,
) -> list[dict[str, Any]]:
    """Rank variants best-first; attach lift vs champion when provided."""
    ranked: list[dict[str, Any]] = []
    for r in results:
        sc = score_variant(r)
        row: dict[str, Any] = {
            **r.as_dict(),
            "tournament_score": sc,
        }
        if champion_score is not None and sc >= 0:
            row["lift_ok"] = swarm_tournament_lift(
                before_score=float(champion_score),
                after_score=float(sc),
                meaningful_delta=float(meaningful_delta),
                trades=int(r.trades),
            )
            row["score_delta"] = float(sc) - float(champion_score)
        else:
            row["lift_ok"] = None
            row["score_delta"] = None
        ranked.append(row)

    # Best score first; stable by variant_id
    ranked.sort(
        key=lambda x: (-float(x.get("tournament_score") or -1.0), str(x.get("variant_id")))
    )
    for i, row in enumerate(ranked):
        row["rank"] = i + 1
    return ranked

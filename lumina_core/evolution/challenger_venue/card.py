"""Daily challenger card for Deck + Telegram (Wave 2)."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from lumina_core.evolution.challenger_venue.dna_namespace import challenger_state_root
from lumina_core.evolution.challenger_venue.journal import load_journal


def build_daily_card(workspace: Path | str, *, champion_expectancy: float = 0.0) -> dict[str, Any]:
    fills = [r for r in load_journal(workspace) if str(r.get("reason") or "") == "fill"]
    pnls = [float(r.get("pnl") or 0.0) for r in fills]
    wins = sum(1 for p in pnls if p > 0)
    trades = len(pnls)
    wr = (wins / trades) if trades else 0.0
    expectancy = (sum(pnls) / trades) if trades else 0.0
    equity = 0.0
    peak = 0.0
    max_dd = 0.0
    for pnl in pnls:
        equity += pnl
        peak = max(peak, equity)
        max_dd = max(max_dd, peak - equity)
    card = {
        "trades": trades,
        "win_rate": wr,
        "expectancy": expectancy,
        "drawdown": max_dd,
        "vs_champion_expectancy": expectancy - float(champion_expectancy),
        "gap_score": None,
    }
    root = challenger_state_root(workspace)
    root.mkdir(parents=True, exist_ok=True)
    path = root / "daily_card.json"
    path.write_text(json.dumps(card, indent=2), encoding="utf-8")
    card["path"] = str(path)
    return card

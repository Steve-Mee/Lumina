"""Rolling winrate helpers for birth plateau detection (Raptor v13)."""
from __future__ import annotations


def rolling_winrate_from_chunks(
    chunks: list[tuple[int, int]] | list[list[int]] | None,
    *,
    window: int = 500,
    lifetime_wr: float = 0.0,
    min_covered_for_partial: int = 200,
    min_covered_for_true: int | None = None,
) -> tuple[float, str, int]:
    """Winrate over the last ``window`` trades from rollout (trades, wins) chunks.

    Returns (winrate, source, covered_trades) where source is one of:
    - true_window: covered >= ~window
    - partial_window: enough recent chunks but < full window
    - lifetime_fallback: not enough chunk history

    Raptor v13: sparse milestones often have no point at trades-window after
    resume → old baseline=0 collapsed rolling to lifetime. Chunks fix that.
    """
    win = max(1, int(window))
    true_need = int(min_covered_for_true) if min_covered_for_true is not None else win
    partial_need = max(1, int(min_covered_for_partial))
    life = float(lifetime_wr)
    if not chunks:
        return life, "lifetime_fallback", 0
    need = win
    covered = 0
    wins_acc = 0.0
    for item in reversed(list(chunks)):
        if covered >= need:
            break
        try:
            t = int(item[0])
            w = int(item[1])
        except (TypeError, ValueError, IndexError):
            continue
        if t <= 0:
            continue
        take = min(t, need - covered)
        # Proportional share if we only need part of the oldest chunk in the window.
        wins_acc += float(w) * (float(take) / float(t))
        covered += take
    if covered <= 0:
        return life, "lifetime_fallback", 0
    wr = float(wins_acc) / float(covered)
    if covered >= true_need:
        return wr, "true_window", covered
    if covered >= partial_need:
        return wr, "partial_window", covered
    return life, "lifetime_fallback", covered


def rolling_winrate_last_n_trades(
    *,
    stage_trades: int,
    stage_wins: int,
    wins_at_trade: dict[int, int],
    window: int = 500,
    chunks: list[tuple[int, int]] | list[list[int]] | None = None,
    return_meta: bool = False,
) -> float | tuple[float, str, int]:
    """Winrate over the last ``window`` stage trades.

    Prefer rollout chunks (Raptor v13). Fall back to milestone snapshots with
    hardened baseline (no silent lifetime collapse when milestones start late).
    """
    trades = int(stage_trades)
    wins = int(stage_wins)
    life = float(wins) / float(trades) if trades > 0 else 0.0
    if trades <= 0:
        return (0.0, "lifetime_fallback", 0) if return_meta else 0.0
    if trades <= window:
        return (life, "true_window", trades) if return_meta else life

    if chunks:
        wr, source, covered = rolling_winrate_from_chunks(
            chunks, window=window, lifetime_wr=life
        )
        if source != "lifetime_fallback":
            return (wr, source, covered) if return_meta else wr

    # Milestone path (hardened).
    boundary = trades - window
    keys = [int(t) for t in (wins_at_trade or {}) if int(t) > 0]
    if not keys:
        return (life, "lifetime_fallback", 0) if return_meta else life
    at_or_before = [t for t in keys if t <= boundary]
    if at_or_before:
        baseline_trades = max(at_or_before)
        baseline_wins = int(wins_at_trade.get(baseline_trades, 0))
        delta_trades = trades - baseline_trades
        if delta_trades <= 0:
            return (life, "lifetime_fallback", 0) if return_meta else life
        wr = float(wins - baseline_wins) / float(delta_trades)
        source = "true_window" if delta_trades >= window * 0.9 else "partial_window"
        return (wr, source, delta_trades) if return_meta else wr

    # No milestone at/before boundary: use earliest milestone (partial window
    # of known history after resume), never baseline=0 → lifetime lie.
    earliest = min(keys)
    if earliest >= trades:
        return (life, "lifetime_fallback", 0) if return_meta else life
    baseline_wins = int(wins_at_trade.get(earliest, 0))
    delta_trades = trades - earliest
    if delta_trades <= 0:
        return (life, "lifetime_fallback", 0) if return_meta else life
    wr = float(wins - baseline_wins) / float(delta_trades)
    source = (
        "true_window"
        if delta_trades >= window * 0.9
        else ("partial_window" if delta_trades >= 200 else "lifetime_fallback")
    )
    if source == "lifetime_fallback":
        return (life, "lifetime_fallback", delta_trades) if return_meta else life
    return (wr, source, delta_trades) if return_meta else wr


def prune_rolling_trade_chunks(
    chunks: list[tuple[int, int]],
    *,
    window: int = 500,
    max_chunks: int = 128,
) -> list[tuple[int, int]]:
    """Keep enough recent chunks to cover ~2× window (and max_chunks)."""
    if not chunks:
        return []
    cleaned: list[tuple[int, int]] = []
    for item in chunks:
        try:
            t, w = int(item[0]), int(item[1])
        except (TypeError, ValueError, IndexError):
            continue
        if t > 0:
            cleaned.append((t, max(0, w)))
    if not cleaned:
        return []
    need = max(1, int(window)) * 2
    kept: list[tuple[int, int]] = []
    total = 0
    for t, w in reversed(cleaned):
        kept.append((t, w))
        total += t
        if total >= need and len(kept) >= 2:
            break
        if len(kept) >= max_chunks:
            break
    kept.reverse()
    return kept

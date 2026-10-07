"""Train-only Awakening reward on tape A. Eval ledgers stay raw process-R.

Plant closes are occupancy airframe and contribute 0. Policy closes keep
realized process-R. Potential shaping γΦ(s')−Φ(s) pulls flat-ratio into the
25–75% exam band without paying per close. After 50 policy closes, a
REGRESS trade-IR on A adds a capped tax.

A capped win bonus nudges tape-A winrate toward the frozen parent's tape-A
winrate plus the Evolution Proof lift. It turns off once that gap is closed.
A path-DD tax, applied by the env after occupancy shaping and not clipped by
the potential cap, charges further policy closes once the USD path has already
reached 20% drawdown and n ≥ 500. Holdout B never enters this module.
"""

from __future__ import annotations

from typing import Any

from lumina_core.birth.certificate_evaluator import max_drawdown_pct
from lumina_core.birth.foundation_metrics import S3_OCCUPANCY_MAX, S3_OCCUPANCY_MIN, s5_holdout_sharpe
from lumina_core.maturity.awakening.clock import REGRESS_SHARPE_LE
from lumina_core.maturity.post_birth_skill_gates import EVOLUTION_PROOF_LIFT_MIN

OCC_SHAPING_CAP_PER_BAR = 0.002
OCC_SHAPING_GAIN = 0.01
# Potential Φ is 0 inside the exam band and at most this far below 0 outside.
# One transition is γΦ(s')−Φ(s), so |shaping| stays ≤ this cap. A 1R loss
# remains larger. Eval ledgers never add this term.
OCC_POTENTIAL_CAP_R = 0.05
OCC_POTENTIAL_GAIN = 0.20
OCC_SHAPING_GAMMA = 0.99
REGRESS_CLOSE_TAX_R = 0.25
REGRESS_TAX_MIN_CLOSES = 50
# Capped add-on for a policy win. Below the regress tax and far below a 1R loss.
LIFT_WIN_BONUS_CAP_R = 0.15
LIFT_WIN_BONUS_MIN_CLOSES = REGRESS_TAX_MIN_CLOSES
# Same 5pp the exam demands. The reference winrate is the frozen parent on A.
LIFT_TARGET = float(EVOLUTION_PROOF_LIFT_MIN)
# Same magnitude as the regress tax. Starts only after the 500-close sample exists
# and the running USD drawdown has already touched 20% (inside the 25% STABLE cap).
PATH_DD_TAX_R = 0.25
PATH_DD_TAX_MIN_CLOSES = 500
PATH_DD_ONSET_PCT = 20.0
PARENT_WR_MIN_CLOSES = LIFT_WIN_BONUS_MIN_CLOSES
PARENT_WR_PROBE_CLOSES = PATH_DD_TAX_MIN_CLOSES


def occupancy_bar_penalty(occupancy: float | None) -> float:
    """0 inside the exam band. Negative outside, capped per bar."""
    if occupancy is None:
        return 0.0
    occ = float(occupancy)
    if occ > float(S3_OCCUPANCY_MAX):
        distance = occ - float(S3_OCCUPANCY_MAX)
    elif occ < float(S3_OCCUPANCY_MIN):
        distance = float(S3_OCCUPANCY_MIN) - occ
    else:
        return 0.0
    if distance <= 0.0:
        return 0.0
    return -min(float(OCC_SHAPING_CAP_PER_BAR), float(OCC_SHAPING_GAIN) * distance)


def occupancy_potential(occupancy: float | None) -> float:
    """0 inside the exam band. Negative outside, bounded by ``OCC_POTENTIAL_CAP_R``."""
    if occupancy is None:
        return 0.0
    occ = float(occupancy)
    if occ > float(S3_OCCUPANCY_MAX):
        distance = occ - float(S3_OCCUPANCY_MAX)
    elif occ < float(S3_OCCUPANCY_MIN):
        distance = float(S3_OCCUPANCY_MIN) - occ
    else:
        return 0.0
    if distance <= 0.0:
        return 0.0
    return -min(float(OCC_POTENTIAL_CAP_R), float(OCC_POTENTIAL_GAIN) * distance)


def occupancy_potential_shaping(
    previous: float | None,
    current: float | None,
    *,
    gamma: float = OCC_SHAPING_GAMMA,
) -> float:
    """γΦ(s')−Φ(s). Zero while both states sit in the band."""
    shaped = float(gamma) * occupancy_potential(current) - occupancy_potential(previous)
    cap = float(OCC_POTENTIAL_CAP_R)
    if shaped > cap:
        return cap
    if shaped < -cap:
        return -cap
    return shaped


def regress_close_tax(*, policy_closes_before: int, train_sharpe: float | None) -> float:
    """Extra tax on the next policy close once tape A is already REGRESS."""
    if int(policy_closes_before) < int(REGRESS_TAX_MIN_CLOSES):
        return 0.0
    if train_sharpe is None:
        return 0.0
    if float(train_sharpe) > float(REGRESS_SHARPE_LE):
        return 0.0
    return -float(REGRESS_CLOSE_TAX_R)


def train_sharpe(policy_rs: list[float]) -> float | None:
    if len(policy_rs) < 5:
        return None
    return s5_holdout_sharpe(policy_rs)


def train_winrate(policy_rs: list[float]) -> float | None:
    """Win share of policy process-R so far. Empty book is unknown, not 0."""
    n = len(policy_rs)
    if n <= 0:
        return None
    wins = sum(1 for r in policy_rs if float(r) > 0.0)
    return float(wins) / float(n)


def lift_win_bonus(
    *,
    process_r: float,
    policy_closes_before: int,
    train_wr: float | None,
    parent_wr: float | None,
) -> float:
    """Capped bonus on a policy win while tape-A WR is still short of parent+lift.

    ``train_wr`` and ``parent_wr`` are both tape A. A missing parent reference
    pays nothing. The bonus is off once the running winrate has cleared the gap,
    and it is never added to a loss.
    """
    if float(process_r) <= 0.0:
        return 0.0
    if int(policy_closes_before) < int(LIFT_WIN_BONUS_MIN_CLOSES):
        return 0.0
    if train_wr is None or parent_wr is None:
        return 0.0
    ceiling = float(parent_wr) + float(LIFT_TARGET)
    if float(train_wr) + 1e-12 >= ceiling:
        return 0.0
    return float(LIFT_WIN_BONUS_CAP_R)


def path_dd_tax(*, policy_closes_before: int, dd_pct: float | None) -> float:
    """Tax the next policy close once the path is already past the onset.

    ``dd_pct`` is the USD drawdown of policy closes before this one, same units
    as ``max_drawdown_pct`` (percent of $50k). Before 500 closes the tax is 0.
    """
    if int(policy_closes_before) < int(PATH_DD_TAX_MIN_CLOSES):
        return 0.0
    if dd_pct is None:
        return 0.0
    if float(dd_pct) + 1e-12 < float(PATH_DD_ONSET_PCT):
        return 0.0
    return -float(PATH_DD_TAX_R)


def policy_path_dd_pct(pnl_usd: list[float]) -> float | None:
    """Exam drawdown on policy USD pnl. An empty book is unknown."""
    if not pnl_usd:
        return None
    return float(max_drawdown_pct(pnl_usd))


def policy_close_pnl_usd(info: dict[str, Any], process_r: float) -> float | None:
    """USD close the exam ledger stores, else process-R times that close's risk.

    Missing both is unknown. The caller leaves it out of the drawdown path.
    """
    if "rl_close_accounting_net_usd" in info and info.get("rl_close_accounting_net_usd") is not None:
        try:
            return float(info["rl_close_accounting_net_usd"])
        except (TypeError, ValueError):
            pass
    risk = info.get("risk_usd")
    try:
        risk_f = float(risk) if risk is not None else 0.0
    except (TypeError, ValueError):
        return None
    if risk_f > 0.0:
        return float(process_r) * risk_f
    return None


# Train-only. Same half-parent rule as the exam. Not a floor change.
# Same magnitude as the path-DD tax. The 0.15R win bonus stays off this path.
MEDIAN_WIN_TAX_MIN_CLOSES = LIFT_WIN_BONUS_MIN_CLOSES
MEDIAN_WIN_TAX_MIN_WINS = 20
MEDIAN_WIN_COLLAPSE_TAX_R = PATH_DD_TAX_R


def median_win_r(policy_rs: list[float]) -> float | None:
    """Median of strictly positive policy process-R. No wins is unknown, not 0."""
    wins = sorted(float(r) for r in policy_rs if float(r) > 0.0)
    n = len(wins)
    if n <= 0:
        return None
    mid = n // 2
    if n % 2 == 1:
        return float(wins[mid])
    return 0.5 * (float(wins[mid - 1]) + float(wins[mid]))


def session_day_key(row: dict[str, Any] | None) -> str | None:
    """Calendar day of a tape bar. Missing timestamp stays undated. No day is invented.

    Same prefix the holdout ledger stores in ``ts_iso`` from the entry bar's
    ``timestamp``. The two clocks share one day key.
    """
    if not isinstance(row, dict):
        return None
    for key in ("day", "ts_iso", "timestamp"):
        raw = row.get(key)
        if isinstance(raw, str) and len(raw.strip()) >= 10:
            return raw.strip()[:10]
    return None


def resolve_entry_day(
    stored: str | None,
    row: dict[str, Any] | None,
    *,
    flat_before: bool,
    opened: bool,
) -> str | None:
    """Day of the entry bar. A same-bar round trip uses this bar. No day is invented."""
    if flat_before and opened:
        return session_day_key(row)
    return stored


def day_mean_residual(trade_r: float, parent_day_mean: float | None) -> float | None:
    """trade_R minus frozen Birth's mean trade_R on that session day.

    ``None`` means the parent day is unknown. The caller leaves the close
    reward unchanged and does not treat the parent as 0. Holdout B is not
    an argument. Eval ledgers never add this term.
    """
    if parent_day_mean is None:
        return None
    return float(trade_r) - float(parent_day_mean)


def median_win_collapse_tax(
    *,
    policy_rs_before: list[float],
    parent_median_win_r: float | None,
) -> float:
    """Tax the next policy close once tape A has already collapsed winner size.

    The book is the closes before this one. A missing parent median pays nothing.
    Fewer than 50 closes or 20 wins is unknown, not a scalp. The predicate is
    ``median_win_collapsed``: child median below half the frozen parent's.
    Eval ledgers never add this term. Holdout B is not an argument.
    """
    from lumina_core.birth.evolution_proof_gate import median_win_collapsed

    if parent_median_win_r is None:
        return 0.0
    book = list(policy_rs_before)
    if len(book) < int(MEDIAN_WIN_TAX_MIN_CLOSES):
        return 0.0
    wins = sum(1 for r in book if float(r) > 0.0)
    if wins < int(MEDIAN_WIN_TAX_MIN_WINS):
        return 0.0
    child = median_win_r(book)
    if not median_win_collapsed(child, parent_median_win_r):
        return 0.0
    return -float(MEDIAN_WIN_COLLAPSE_TAX_R)


def living_close_reward(
    process_r: float,
    *,
    plant: bool,
    occupancy: float | None,
    policy_closes_before: int,
    train_sharpe_value: float | None,
    train_wr: float | None = None,
    parent_wr: float | None = None,
) -> float:
    """Close scalar for the living clock. Plant is 0.

    ``occupancy`` is not added here. Potential shaping is a per-step term on
    tape A. The path-DD tax is also not added here: the env applies it after
    shaping so the 0.05 potential cap cannot clip it. Eval ledgers stay raw process-R.
    """
    del occupancy
    if plant:
        return 0.0
    return (
        float(process_r)
        + regress_close_tax(
            policy_closes_before=policy_closes_before,
            train_sharpe=train_sharpe_value,
        )
        + lift_win_bonus(
            process_r=float(process_r),
            policy_closes_before=policy_closes_before,
            train_wr=train_wr,
            parent_wr=parent_wr,
        )
    )


__all__ = [
    "LIFT_TARGET",
    "LIFT_WIN_BONUS_CAP_R",
    "LIFT_WIN_BONUS_MIN_CLOSES",
    "OCC_POTENTIAL_CAP_R",
    "OCC_POTENTIAL_GAIN",
    "OCC_SHAPING_CAP_PER_BAR",
    "OCC_SHAPING_GAIN",
    "OCC_SHAPING_GAMMA",
    "PARENT_WR_MIN_CLOSES",
    "PARENT_WR_PROBE_CLOSES",
    "PATH_DD_ONSET_PCT",
    "PATH_DD_TAX_MIN_CLOSES",
    "PATH_DD_TAX_R",
    "REGRESS_CLOSE_TAX_R",
    "REGRESS_TAX_MIN_CLOSES",
    "MEDIAN_WIN_COLLAPSE_TAX_R",
    "MEDIAN_WIN_TAX_MIN_CLOSES",
    "MEDIAN_WIN_TAX_MIN_WINS",
    "day_mean_residual",
    "lift_win_bonus",
    "living_close_reward",
    "resolve_entry_day",
    "session_day_key",
    "median_win_collapse_tax",
    "median_win_r",
    "occupancy_bar_penalty",
    "occupancy_potential",
    "occupancy_potential_shaping",
    "path_dd_tax",
    "policy_close_pnl_usd",
    "policy_path_dd_pct",
    "regress_close_tax",
    "train_sharpe",
    "train_winrate",
]

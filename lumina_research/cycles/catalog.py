"""Pre-registered economic templates (12) and parameter variants (24). No free-form LLM."""

from __future__ import annotations

import random
from dataclasses import dataclass

from lumina_core.agent_orchestration.schemas_research import EconomicRationale
from lumina_research.agents.economic_templates import REGISTERED_TEMPLATE_IDS, require_economic_template
from lumina_research.agents.generators import GeneratorError, HypothesisDraft, HypothesisGenerator
from lumina_research.cycles.geometry import require_geometry

N_TEMPLATES = 12
N_HYPOTHESES = 24
# Explicit D6 horizon for every catalog variant. Not oos_size (30) and not a silent 20.
CATALOG_EXPECTED_HORIZON_BARS = 16


@dataclass(frozen=True, slots=True)
class HypothesisSpec:
    config_id: str
    template_id: str
    family: str
    instrument: str
    lookback: int
    threshold: float
    mode: str
    target_ticks: int
    stop_ticks: int
    rationale: EconomicRationale
    is_size: int = 60
    oos_size: int = 30
    session_filter: str = "rth"
    time_stop_bars: int = CATALOG_EXPECTED_HORIZON_BARS
    session_end_flatten: bool = True
    has_fit_step: bool = False
    target_atr: float | None = None
    stop_atr: float | None = None
    atr_n_sessions: int = 14
    disable_brackets: bool = False


def catalog() -> tuple[HypothesisSpec, ...]:
    rows: list[HypothesisSpec] = []
    rows.extend(_mean_reversion())
    rows.extend(_volume_imbalance())
    rows.extend(_regime_momentum())
    rows.extend(_opening_breakout())
    rows.extend(_opening_fade())
    rows.extend(_overnight_gap())
    rows.extend(_vwap_distance())
    rows.extend(_range_compression())
    rows.extend(_close_reversal())
    rows.extend(_time_of_day())
    rows.extend(_trend_pullback())
    rows.extend(_volatility_expansion())
    if len(rows) != N_HYPOTHESES:
        raise RuntimeError(f"catalog must contain {N_HYPOTHESES} hypotheses, got {len(rows)}")
    templates = {item.template_id for item in rows}
    if templates != set(REGISTERED_TEMPLATE_IDS) or len(templates) != N_TEMPLATES:
        raise RuntimeError("catalog templates must be exactly the 12 registered ids")
    for spec in rows:
        require_economic_template(spec.template_id)
        require_geometry(root=spec.instrument, target_ticks=spec.target_ticks, stop_ticks=spec.stop_ticks)
        _require_rationale(spec.rationale)
    return tuple(rows)


class EconomicCatalogGenerator(HypothesisGenerator):
    """Emits the frozen catalog in order. Extra count or free-form ids are refused."""

    def __init__(self, specs: tuple[HypothesisSpec, ...] | None = None) -> None:
        self._specs = specs if specs is not None else catalog()

    @property
    def generator_id(self) -> str:
        return "economic_catalog"

    def drafts(self, *, rng: random.Random, count: int, start_index: int) -> tuple[HypothesisDraft, ...]:
        if count != len(self._specs):
            raise GeneratorError("economic catalog emits every pre-registered hypothesis exactly once")
        if start_index != 0:
            raise GeneratorError("economic catalog must start at index 0")
        items: list[HypothesisDraft] = []
        for spec in self._specs:
            items.append(
                HypothesisDraft(
                    config_id=spec.config_id,
                    generator_id=spec.template_id,
                    kind="economic",
                    instrument=spec.instrument,
                    seed=rng.randint(1, 2_147_483_647),
                    n_obs=360,
                    mu=0.0,
                    sigma=0.01,
                    planted=False,
                    proposed_quantity=1.0,
                    proposed_price=5_000.0,
                    proposed_notional=5_000.0,
                    rationale=spec.rationale,
                    is_size=spec.is_size,
                    oos_size=spec.oos_size,
                    expected_horizon_bars=CATALOG_EXPECTED_HORIZON_BARS,
                )
            )
        return tuple(items)


def _rationale(
    *,
    mechanism: str,
    why: str,
    other: str,
    regime: str,
    holding: str,
    costs: str,
) -> EconomicRationale:
    return EconomicRationale(
        mechanism=mechanism,
        why_edge_exists=why,
        other_side=other,
        expected_regime=regime,
        falsification_criterion=(
            "median OOS after costs <= 0 or share of positive OOS windows < 0.60 "
            "or structural decay or PBO > 0.50 or DSR < 0.95"
        ),
        holding_period=holding,
        survives_costs=costs,
    )


def _require_rationale(rationale: EconomicRationale) -> None:
    fields = (
        rationale.mechanism,
        rationale.why_edge_exists,
        rationale.other_side,
        rationale.expected_regime,
        rationale.falsification_criterion,
        rationale.holding_period,
        rationale.survives_costs,
    )
    if any(len(item.strip()) < 8 for item in fields):
        raise RuntimeError("incomplete economic rationale")


def _mean_reversion() -> tuple[HypothesisSpec, ...]:
    why = "Dealers fade transitory inventory shocks; impatient flow pays the spread to unwind"
    other = "Short-horizon discretionary and CTA flow that must transact immediately"
    costs = "Net target after four-leg costs exceeds 1R at the tick floors so BE win rate is attainable"
    hold = "half-life 10-20 bars; flatten at target/stop the same session"
    return (
        _spec("mr-mes-10-1.5", "mean_reversion", "MES", 10, 1.5, "fade", 16, 8, why, other, hold, costs),
        _spec("mr-es-20-1.5", "mean_reversion", "ES", 20, 1.5, "fade", 8, 4, why, other, hold, costs),
    )


def _volume_imbalance() -> tuple[HypothesisSpec, ...]:
    why = "Signed volume imbalance marks urgent demand; the book replenishes after the burst"
    other = "Aggressive market-takers sweeping depth during a short burst"
    costs = "Fade after the sweep; stop is wider than modeled 1-2.5 micro / 0.5-1.5 full ticks"
    hold = "half-life 5-15 bars after the imbalance prints"
    return (
        _spec("vi-mnq-10-0.55", "volume_imbalance", "MNQ", 10, 0.55, "fade", 16, 8, why, other, hold, costs),
        _spec("vi-nq-20-0.65", "volume_imbalance", "NQ", 20, 0.65, "fade", 12, 4, why, other, hold, costs),
    )


def _regime_momentum() -> tuple[HypothesisSpec, ...]:
    why = "Trend-followers add only when realized vol is contained; crowded unwind is delayed"
    other = "Volatility-targeting funds that are not yet forced to cut"
    costs = "Holds through one roundtrip of four-leg costs; target 2R vs stop after tick floors"
    hold = "holding 10-30 bars in the quiet-vol regime only"
    return (
        _spec("rm-mes-10-0.40", "regime_momentum", "MES", 10, 0.40, "follow", 16, 8, why, other, hold, costs),
        _spec("rm-es-10-0.40", "regime_momentum", "ES", 10, 0.40, "follow", 8, 4, why, other, hold, costs),
    )


def _opening_breakout() -> tuple[HypothesisSpec, ...]:
    why = "The opening auction concentrates overnight inventory; a range break continues that flow"
    other = "Overnight gap traders and cash-index rebalancers at the cash open"
    costs = "Breakout target covers commission, half-spread, vol slippage and sqrt impact"
    hold = "holding the first 30-90 minutes after the opening range"
    return (
        _spec("or-mes-5-bo", "opening_range_breakout", "MES", 5, 0.0, "breakout", 16, 8, why, other, hold, costs),
        _spec("or-es-5-bo", "opening_range_breakout", "ES", 5, 0.0, "breakout", 8, 4, why, other, hold, costs),
    )


def _opening_fade() -> tuple[HypothesisSpec, ...]:
    why = "A failed opening-range break is inventory returning to the auction midpoint"
    other = "Momentum scalpers who chased the first print through the range"
    costs = "Fade target is above modeled one-way ticks so net expectancy can exist after costs"
    hold = "half-life inside the first session hour"
    return (
        _spec("or-mnq-15-fade", "opening_range_fade", "MNQ", 15, 0.0, "fade", 16, 8, why, other, hold, costs),
        _spec("or-nq-15-fade", "opening_range_fade", "NQ", 15, 0.0, "fade", 8, 4, why, other, hold, costs),
    )


def _overnight_gap() -> tuple[HypothesisSpec, ...]:
    why = "Overnight gaps embed uninformed premium; the pit fades gaps once cash depth appears"
    other = "After-hours hedgers who paid for immediacy into the close"
    costs = "Gap fade uses micro 16/8 or full 8/4 floors, larger than 0.5-2.5 tick average costs"
    hold = "half-life the first 10-40 bars after the gap open"
    return (
        _spec("gap-mes-8", "overnight_gap", "MES", 1, 8.0, "fade", 16, 8, why, other, hold, costs),
        _spec("gap-es-4", "overnight_gap", "ES", 1, 4.0, "fade", 8, 4, why, other, hold, costs),
    )


def _vwap_distance() -> tuple[HypothesisSpec, ...]:
    why = "Institutional TWAP/VWAP leaves a residual when price stretches from session VWAP"
    other = "Benchmark-hugging execution algos that must complete a clip"
    costs = "Stretch fade pays four-leg costs once; tick floors keep net target positive"
    hold = "half-life 20-40 bars of the session VWAP clock"
    return (
        _spec("vwap-mes-20-1.5", "vwap_distance", "MES", 20, 1.5, "fade", 16, 8, why, other, hold, costs),
        _spec("vwap-nq-40-2.0", "vwap_distance", "NQ", 40, 2.0, "fade", 8, 4, why, other, hold, costs),
    )


def _range_compression() -> tuple[HypothesisSpec, ...]:
    why = "Range compression is a dealer gamma pocket; a break expands as hedges flip"
    other = "Short-vol overlay that is forced to chase once the pocket breaks"
    costs = "Expansion target is sized to remain > costs after a single stop-out"
    hold = "holding 10-30 bars after the compression break"
    return (
        _spec("rc-mes-20-0.25", "range_compression", "MES", 20, 0.25, "breakout", 16, 8, why, other, hold, costs),
        _spec("rc-es-20-0.25", "range_compression", "ES", 20, 0.25, "breakout", 8, 4, why, other, hold, costs),
    )


def _close_reversal() -> tuple[HypothesisSpec, ...]:
    why = "A streak of directional closes exhausts one-sided inventory; the next print reverts"
    other = "Momentum scalpers who are last into the streak"
    costs = "One-bar reversal still nets positive if win rate clears the contract-type BE"
    hold = "half-life 1-5 bars after the streak"
    return (
        _spec("cr-mes-3", "close_reversal", "MES", 3, 0.0, "fade", 16, 8, why, other, hold, costs),
        _spec("cr-nq-5", "close_reversal", "NQ", 5, 0.0, "fade", 8, 4, why, other, hold, costs),
    )


def _time_of_day() -> tuple[HypothesisSpec, ...]:
    why = "The first-hour extension is often inventory, not information; it mean-reverts later"
    other = "On-open momentum funds completing a cash-open clip"
    costs = "Fade uses the same tick floors; modeled one-way ticks stay below the stop"
    hold = "half-life inside minutes 15-90 of the cash session"
    return (
        _spec("tod-mes-15", "time_of_day_inventory", "MES", 15, 0.0, "fade", 16, 8, why, other, hold, costs),
        _spec("tod-es-15", "time_of_day_inventory", "ES", 15, 0.0, "fade", 8, 4, why, other, hold, costs),
    )


def _trend_pullback() -> tuple[HypothesisSpec, ...]:
    why = "A quiet-vol uptrend pays for a pullback as trend-followers add on dips, not highs"
    other = "Mean-reversion shorts fading the last impulse"
    costs = "Pullback entry with stop below the impulse still clears four-leg costs at 2R"
    hold = "holding 15-40 bars of the pullback-then-resume move"
    return (
        _spec("pb-mnq-20", "trend_pullback", "MNQ", 20, 0.0, "follow", 16, 8, why, other, hold, costs),
        _spec("pb-nq-20", "trend_pullback", "NQ", 20, 0.0, "follow", 8, 4, why, other, hold, costs),
    )


def _volatility_expansion() -> tuple[HypothesisSpec, ...]:
    why = "After a compressed range, the first expansion bar is hedging flow that continues"
    other = "Gamma scalpers fading the first expansion print"
    costs = "Expansion stop sits beyond modeled slippage plus impact; target is 2x stop"
    hold = "holding 8-25 bars of the expansion leg"
    return (
        _spec("vx-mes-20", "volatility_expansion", "MES", 20, 0.75, "breakout", 16, 8, why, other, hold, costs),
        _spec("vx-es-20", "volatility_expansion", "ES", 20, 0.75, "breakout", 8, 4, why, other, hold, costs),
    )


_REGIME: dict[str, str] = {
    "mean_reversion": "mean-reverting quiet vol",
    "volume_imbalance": "two-sided liquidity",
    "regime_momentum": "low-vol trend",
    "opening_range_breakout": "RTH open",
    "opening_range_fade": "RTH open fade",
    "overnight_gap": "gap-open mean reversion",
    "vwap_distance": "session VWAP stretch",
    "range_compression": "low-range expansion",
    "close_reversal": "exhaustion reversal",
    "time_of_day_inventory": "first-hour inventory",
    "trend_pullback": "quiet-vol pullback",
    "volatility_expansion": "vol expansion",
}

_FAMILY: dict[str, str] = {
    "mean_reversion": "mean_reversion",
    "volume_imbalance": "volume_imbalance",
    "regime_momentum": "regime_momentum",
    "opening_range_breakout": "opening_range",
    "opening_range_fade": "opening_range",
    "overnight_gap": "overnight_gap",
    "vwap_distance": "vwap_distance",
    "range_compression": "range_compression",
    "close_reversal": "close_reversal",
    "time_of_day_inventory": "time_of_day",
    "trend_pullback": "trend_pullback",
    "volatility_expansion": "volatility_expansion",
}


def _spec(
    config_id: str,
    template_id: str,
    instrument: str,
    lookback: int,
    threshold: float,
    mode: str,
    target: int,
    stop: int,
    why: str,
    other: str,
    holding: str,
    costs: str,
) -> HypothesisSpec:
    mechanism = f"{template_id} on {instrument}: lookback={lookback} threshold={threshold} mode={mode}"
    return HypothesisSpec(
        config_id=config_id,
        template_id=template_id,
        family=_FAMILY[template_id],
        instrument=instrument,
        lookback=lookback,
        threshold=threshold,
        mode=mode,
        target_ticks=target,
        stop_ticks=stop,
        session_filter="rth",
        time_stop_bars=CATALOG_EXPECTED_HORIZON_BARS,
        session_end_flatten=True,
        has_fit_step=False,
        rationale=_rationale(
            mechanism=mechanism,
            why=why,
            other=other,
            regime=_REGIME[template_id],
            holding=holding,
            costs=costs,
        ),
    )

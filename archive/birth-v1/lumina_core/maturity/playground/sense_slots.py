"""43-dim slot names and the eye-audit verdict.

The verdict is a measurement of the live vector against the exam path.
It is not a pass, and it does not change the policy input.
"""
from __future__ import annotations

from statistics import median

SLOT_NAMES: tuple[str, ...] = (
    "price",
    "trend_regime_strength",
    "volume_delta",
    "avg_volume_delta_10",
    "bid_ask_imbalance",
    "cumulative_delta_10",
    "dream_confidence",
    "dream_confluence",
    "dream_stop",
    "dream_target",
    "fib_0382",
    "fib_05",
    "fib_0618",
    "vix",
    "yield10y",
    "dxy",
    "position",
    "qty",
    "entry_price",
    "equity",
    "drawdown",
    "rolling_sharpe",
    "idx",
    "data_len",
    "bible_confluence",
    "bible_news",
    "bible_session",
    "bible_mtf",
    "dna_0",
    "dna_1",
    "dna_2",
    "dna_3",
    "trend_adx_7",
    "trend_adx_14",
    "trend_adx_21",
    "trend_slope_5",
    "trend_slope_15",
    "trend_slope_30",
    "trend_slope_60",
    "trend_direction",
    "trend_duration_norm",
    "trend_atr_norm",
    "trend_atr_ratio",
)

OBSERVATION_DIM = 43
REFERENCE_MIN = 20
LIVE_MIN_FOR_MATCH = 20


def slot_index(name: str) -> int:
    return SLOT_NAMES.index(name)


def describe_vector(values: list[float]) -> dict[str, float | str | None]:
    """Price, equity, and the slots that sit on zero. A short vector is not described."""
    if len(values) != OBSERVATION_DIM:
        return {"dim": str(len(values)), "price": None, "equity": None, "zeros": ""}
    zeros = [SLOT_NAMES[i] for i, value in enumerate(values) if abs(float(value)) < 1e-8]
    return {
        "dim": str(OBSERVATION_DIM),
        "price": float(values[0]),
        "equity": float(values[slot_index("equity")]),
        "zeros": ",".join(zeros),
    }


def classify_eyes(
    *,
    live: list[list[float]],
    reference_closes: list[float],
    reference_slopes: list[float],
    exam_bible_session: float,
    exam_bible_mtf: float,
) -> str:
    """shifted, matched, blind, thin, or reference_missing.

    blind wins over a missing reference: an exam slot that the live path leaves
    at zero is already a fact. matched requires both samples.
    """
    rows = [row for row in live if len(row) == OBSERVATION_DIM]
    if not rows:
        return "thin"
    if _bible_blind(rows, exam_bible_session, exam_bible_mtf):
        return "blind"
    if len(reference_slopes) < REFERENCE_MIN or len(reference_closes) < REFERENCE_MIN:
        return "reference_missing"
    if _price_scale_shifted(rows, reference_closes):
        return "shifted"
    if _trend_blind(rows, reference_slopes):
        return "blind"
    if len(rows) < LIVE_MIN_FOR_MATCH:
        return "thin"
    return "matched"


def _bible_blind(rows: list[list[float]], exam_session: float, exam_mtf: float) -> bool:
    session_i = slot_index("bible_session")
    mtf_i = slot_index("bible_mtf")
    session_empty = all(abs(float(row[session_i])) < 1e-8 for row in rows)
    mtf_empty = all(abs(float(row[mtf_i])) < 1e-8 for row in rows)
    if session_empty and abs(float(exam_session)) > 1e-8:
        return True
    if mtf_empty and abs(float(exam_mtf)) > 1e-8:
        return True
    return False


def _price_scale_shifted(rows: list[list[float]], reference_closes: list[float]) -> bool:
    live_px = median(float(row[0]) for row in rows)
    ref_px = median(float(px) for px in reference_closes if float(px) > 0.0)
    if ref_px > 1000.0 and live_px < 100.0:
        return True
    if live_px > 1000.0 and ref_px < 100.0:
        return True
    return False


def _trend_blind(rows: list[list[float]], reference_slopes: list[float]) -> bool:
    slope_i = slot_index("trend_slope_60")
    live_dead = all(abs(float(row[slope_i])) < 1e-8 for row in rows)
    ref_alive = median(abs(float(value)) for value in reference_slopes) > 1e-4
    return bool(live_dead and ref_alive)

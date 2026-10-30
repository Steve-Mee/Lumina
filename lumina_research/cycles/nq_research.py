"""NQ research guards after the 2026-10-30 08:15 open.

Single-instrument NQ templates stay closed (`nq_lock.assert_nq_templates_closed`).
NQ is allowed only for relative-value / cross-instrument (ES vs NQ) hypotheses
on pre-holdout data, with the improved null and a positive control, a fresh
pre-register, and no SIM or promotion. This module does not pre-register a
hypothesis and does not run a trial.
"""

from __future__ import annotations

from dataclasses import dataclass

from lumina_research.cycles.null_model import NULL_BUILDER

NQOPEN_ANSWERS_NAME = "ONDERZOEKERS-ANTWOORDEN-NQOPEN-20261030T0815.md"
NQOPEN_ANSWERS_SHA256 = "844843564c0a4f5c8b3e6fa56aaff1ff0a696107a2020de5de9534431ab18c92"
HOLDOUT_PIN_Z = "2026-01-28T23:00:00Z"
HOLDOUT_PIN_OFFSET = "2026-01-28T23:00:00+00:00"
PRE_HOLDOUT_WINDOW = "pre_holdout"
KIND_RELATIVE_VALUE = "relative_value"
KIND_CROSS_INSTRUMENT = "cross_instrument"
ALLOWED_NQ_KINDS: frozenset[str] = frozenset({KIND_RELATIVE_VALUE, KIND_CROSS_INSTRUMENT})
REQUIRED_NQ_INSTRUMENTS: frozenset[str] = frozenset({"ES", "NQ"})
CLOSED_NQ_PREREG_IDS: frozenset[str] = frozenset(
    {
        "vi-nq-20-0.65",
        "or-nq-15-fade",
        "vwap-nq-40-2.0",
        "cr-nq-5",
        "pb-nq-20",
        "p2c-vi-nq-10-0.55",
        "p2c-or-nq-15-fade",
        "p2c-pb-nq-20",
    }
)
NQ_KIND_REFUSED = "NQ is allowed only for relative-value or cross-instrument hypotheses"
NQ_PAIR_REFUSED = "NQ relative-value requires ES vs NQ on pre-holdout data"
NQ_HOLDOUT_REFUSED = "NQ research is pre-holdout only; holdout remains sealed"
NQ_NULL_REFUSED = "NQ research requires the improved null (linear_magnitude)"
NQ_CONTROL_REFUSED = "NQ research requires a positive control"
NQ_REUSE_REFUSED = "NQ research may not reuse a closed NQ pre-register"
NQ_IDS_REFUSED = "NQ research requires a fresh pre-register id"
NQ_SIM_REFUSED = "NQ research may not request SIM or promotion"


class NQResearchRefused(RuntimeError):
    """NQ research request failed a 08:15 open condition."""


@dataclass(frozen=True, slots=True)
class NQResearchRequest:
    hypothesis_kind: str
    instruments: tuple[str, ...]
    tape_window: str
    holdout_opened: bool
    holdout_pin: str
    null_builder: str
    positive_control_included: bool
    config_ids: tuple[str, ...]
    reuses_prereg_ids: tuple[str, ...]
    sim_requested: bool
    promotion_requested: bool


def assert_nq_research_allowed(request: NQResearchRequest) -> None:
    if "NQ" not in request.instruments:
        raise NQResearchRefused("NQ research request has no NQ instrument")
    if request.hypothesis_kind not in ALLOWED_NQ_KINDS:
        raise NQResearchRefused(NQ_KIND_REFUSED)
    if frozenset(request.instruments) != REQUIRED_NQ_INSTRUMENTS:
        raise NQResearchRefused(NQ_PAIR_REFUSED)
    if request.tape_window != PRE_HOLDOUT_WINDOW or request.holdout_opened:
        raise NQResearchRefused(NQ_HOLDOUT_REFUSED)
    if request.holdout_pin not in {HOLDOUT_PIN_Z, HOLDOUT_PIN_OFFSET}:
        raise NQResearchRefused(NQ_HOLDOUT_REFUSED)
    if request.null_builder != NULL_BUILDER:
        raise NQResearchRefused(NQ_NULL_REFUSED)
    if request.positive_control_included is not True:
        raise NQResearchRefused(NQ_CONTROL_REFUSED)
    if not request.config_ids:
        raise NQResearchRefused(NQ_IDS_REFUSED)
    used = set(request.config_ids) | set(request.reuses_prereg_ids)
    if used & CLOSED_NQ_PREREG_IDS or request.reuses_prereg_ids:
        raise NQResearchRefused(NQ_REUSE_REFUSED)
    if request.sim_requested or request.promotion_requested:
        raise NQResearchRefused(NQ_SIM_REFUSED)

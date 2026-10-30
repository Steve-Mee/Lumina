"""NQ-open 08:15 guards: relative-value only, no SIM/promotion, no old prereg."""

from __future__ import annotations

import hashlib
from pathlib import Path

import pytest

from lumina_research.cycles.catalog import catalog
from lumina_research.cycles.four_instrument import ES_NQ_TRANSLATIONS
from lumina_research.cycles.nq_lock import NQTemplatesClosed, assert_nq_templates_closed
from lumina_research.cycles.nq_research import (
    CLOSED_NQ_PREREG_IDS,
    KIND_CROSS_INSTRUMENT,
    KIND_RELATIVE_VALUE,
    NQ_CONTROL_REFUSED,
    NQ_HOLDOUT_REFUSED,
    NQ_KIND_REFUSED,
    NQ_PAIR_REFUSED,
    NQ_REUSE_REFUSED,
    NQ_SIM_REFUSED,
    NQOPEN_ANSWERS_NAME,
    NQOPEN_ANSWERS_SHA256,
    NQResearchRefused,
    NQResearchRequest,
    assert_nq_research_allowed,
)
from lumina_research.cycles.null_model import NULL_BUILDER


def _request(**overrides: object) -> NQResearchRequest:
    payload: dict[str, object] = {
        "hypothesis_kind": KIND_RELATIVE_VALUE,
        "instruments": ("ES", "NQ"),
        "tape_window": "pre_holdout",
        "holdout_opened": False,
        "holdout_pin": "2026-01-28T23:00:00Z",
        "null_builder": NULL_BUILDER,
        "positive_control_included": True,
        "config_ids": ("p2rv-es-nq-guard-test",),
        "reuses_prereg_ids": (),
        "sim_requested": False,
        "promotion_requested": False,
    }
    payload.update(overrides)
    return NQResearchRequest(**payload)  # type: ignore[arg-type]


@pytest.mark.unit
def test_nqopen_answers_sha_is_frozen() -> None:
    path = Path("docs/research") / NQOPEN_ANSWERS_NAME
    digest = hashlib.sha256(path.read_bytes()).hexdigest()
    assert digest == NQOPEN_ANSWERS_SHA256
    assert digest.startswith("84484356")


@pytest.mark.unit
def test_single_instrument_nq_templates_stay_closed() -> None:
    with pytest.raises(NQTemplatesClosed, match="pre-register"):
        assert_nq_templates_closed(("NQ",))
    with pytest.raises(NQResearchRefused, match=NQ_KIND_REFUSED):
        assert_nq_research_allowed(_request(hypothesis_kind="single_instrument"))


@pytest.mark.unit
def test_relative_value_nq_is_allowed_when_all_conditions_hold() -> None:
    assert_nq_research_allowed(_request())
    assert_nq_research_allowed(_request(hypothesis_kind=KIND_CROSS_INSTRUMENT))


@pytest.mark.unit
def test_nq_requires_es_vs_nq_pre_holdout_improved_null_and_control() -> None:
    with pytest.raises(NQResearchRefused, match=NQ_PAIR_REFUSED):
        assert_nq_research_allowed(_request(instruments=("NQ",)))
    with pytest.raises(NQResearchRefused, match=NQ_HOLDOUT_REFUSED):
        assert_nq_research_allowed(_request(tape_window="holdout"))
    with pytest.raises(NQResearchRefused, match=NQ_HOLDOUT_REFUSED):
        assert_nq_research_allowed(_request(holdout_opened=True))
    with pytest.raises(NQResearchRefused, match=NQ_HOLDOUT_REFUSED):
        assert_nq_research_allowed(_request(holdout_pin="2026-01-29T00:00:00Z"))
    with pytest.raises(NQResearchRefused, match="linear_magnitude"):
        assert_nq_research_allowed(_request(null_builder="mean_shuffle"))
    with pytest.raises(NQResearchRefused, match=NQ_CONTROL_REFUSED):
        assert_nq_research_allowed(_request(positive_control_included=False))


@pytest.mark.unit
def test_nq_refuses_old_prereg_and_sim_promotion() -> None:
    with pytest.raises(NQResearchRefused, match=NQ_REUSE_REFUSED):
        assert_nq_research_allowed(_request(config_ids=("p2c-vi-nq-10-0.55",)))
    with pytest.raises(NQResearchRefused, match=NQ_REUSE_REFUSED):
        assert_nq_research_allowed(_request(reuses_prereg_ids=("or-nq-15-fade",)))
    with pytest.raises(NQResearchRefused, match=NQ_SIM_REFUSED):
        assert_nq_research_allowed(_request(sim_requested=True))
    with pytest.raises(NQResearchRefused, match=NQ_SIM_REFUSED):
        assert_nq_research_allowed(_request(promotion_requested=True))


@pytest.mark.unit
def test_closed_nq_prereg_ids_cover_catalog_and_four_instrument() -> None:
    catalog_nq = {item.config_id for item in catalog() if item.instrument == "NQ"}
    translated = {dst for _src, dst, root in ES_NQ_TRANSLATIONS if root == "NQ"}
    assert catalog_nq <= CLOSED_NQ_PREREG_IDS
    assert translated <= CLOSED_NQ_PREREG_IDS
    assert NULL_BUILDER == "linear_magnitude"

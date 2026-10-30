"""New book opens only after an explicit search-space pre-register."""

from __future__ import annotations

from dataclasses import replace
from pathlib import Path

import pytest

from lumina_research.cycles.nq_research import KIND_RELATIVE_VALUE, NQResearchRequest
from lumina_research.cycles.null_model import NULL_BUILDER
from lumina_research.cycles.search_space import (
    SEARCH_SPACE_REFUSED_CONTROL,
    SEARCH_SPACE_REFUSED_HORIZON,
    SEARCH_SPACE_REFUSED_MISSING,
    SEARCH_SPACE_REFUSED_NQ,
    SEARCH_SPACE_REFUSED_RV,
    SEARCH_SPACE_REFUSED_SAME_SPACE,
    SEARCH_SPACE_REFUSED_TURNOVER,
    SearchSpacePrereg,
    SearchSpaceRefused,
    assert_search_space_prereg_opens_book,
)


def _nq() -> NQResearchRequest:
    return NQResearchRequest(
        hypothesis_kind=KIND_RELATIVE_VALUE,
        instruments=("ES", "NQ"),
        tape_window="pre_holdout",
        holdout_opened=False,
        holdout_pin="2026-01-28T23:00:00Z",
        null_builder=NULL_BUILDER,
        positive_control_included=True,
        config_ids=("p2rv-es-nq-guard-test",),
        reuses_prereg_ids=(),
        sim_requested=False,
        promotion_requested=False,
    )


def _prereg(path: Path) -> SearchSpacePrereg:
    path.write_text("# fixture search-space prereg\n", encoding="utf-8")
    return SearchSpacePrereg(
        lower_turnover=True,
        longer_horizon=True,
        relative_value_config_ids=("p2rv-es-nq-guard-test",),
        null_builder=NULL_BUILDER,
        positive_control_included=True,
        committed_path=path,
        same_space_short_horizon=False,
        nq_request=_nq(),
    )


@pytest.mark.unit
def test_valid_search_space_prereg_opens_book(tmp_path: Path) -> None:
    assert_search_space_prereg_opens_book(_prereg(tmp_path / "space.md"))


@pytest.mark.unit
def test_search_space_prereg_requires_turnover_horizon_and_relative_value(
    tmp_path: Path,
) -> None:
    base = _prereg(tmp_path / "space.md")
    with pytest.raises(SearchSpaceRefused, match=SEARCH_SPACE_REFUSED_TURNOVER):
        assert_search_space_prereg_opens_book(replace(base, lower_turnover=False))
    with pytest.raises(SearchSpaceRefused, match=SEARCH_SPACE_REFUSED_HORIZON):
        assert_search_space_prereg_opens_book(replace(base, longer_horizon=False))
    with pytest.raises(SearchSpaceRefused, match=SEARCH_SPACE_REFUSED_RV):
        assert_search_space_prereg_opens_book(replace(base, relative_value_config_ids=()))
    with pytest.raises(SearchSpaceRefused, match=SEARCH_SPACE_REFUSED_SAME_SPACE):
        assert_search_space_prereg_opens_book(replace(base, same_space_short_horizon=True))
    with pytest.raises(SearchSpaceRefused, match=SEARCH_SPACE_REFUSED_MISSING):
        assert_search_space_prereg_opens_book(replace(base, committed_path=tmp_path / "missing.md"))


@pytest.mark.unit
def test_search_space_prereg_requires_improved_null_control_and_nqopen(
    tmp_path: Path,
) -> None:
    base = _prereg(tmp_path / "space.md")
    with pytest.raises(SearchSpaceRefused, match="linear_magnitude"):
        assert_search_space_prereg_opens_book(replace(base, null_builder="mean_shuffle"))
    with pytest.raises(SearchSpaceRefused, match=SEARCH_SPACE_REFUSED_CONTROL):
        assert_search_space_prereg_opens_book(replace(base, positive_control_included=False))
    with pytest.raises(SearchSpaceRefused, match=SEARCH_SPACE_REFUSED_NQ):
        assert_search_space_prereg_opens_book(replace(base, nq_request=replace(_nq(), sim_requested=True)))
    with pytest.raises(SearchSpaceRefused, match=SEARCH_SPACE_REFUSED_NQ):
        assert_search_space_prereg_opens_book(
            replace(base, nq_request=replace(_nq(), hypothesis_kind="single_instrument"))
        )
    with pytest.raises(SearchSpaceRefused, match=SEARCH_SPACE_REFUSED_NQ):
        assert_search_space_prereg_opens_book(
            replace(
                base,
                relative_value_config_ids=("p2c-vi-nq-10-0.55",),
                nq_request=replace(_nq(), config_ids=("p2c-vi-nq-10-0.55",)),
            )
        )

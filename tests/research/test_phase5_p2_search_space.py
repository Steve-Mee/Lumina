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
    SEARCH_SPACE_REFUSED_COUNT,
    SEARCH_SPACE_REFUSED_TURNOVER,
    NEW_BOOK_HYPOTHESIS_CAP,
    NEW_BOOK_MAX_CYCLES,
    SearchSpacePrereg,
    SearchSpaceRefused,
    assert_search_space_prereg_opens_book,
    search_space_prereg_from_mapping,
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
        n_hypotheses=1,
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
    with pytest.raises(SearchSpaceRefused, match=SEARCH_SPACE_REFUSED_COUNT):
        assert_search_space_prereg_opens_book(replace(base, n_hypotheses=0))
    with pytest.raises(SearchSpaceRefused, match=SEARCH_SPACE_REFUSED_COUNT):
        assert_search_space_prereg_opens_book(replace(base, n_hypotheses=NEW_BOOK_HYPOTHESIS_CAP + 1))
    with pytest.raises(SearchSpaceRefused, match=SEARCH_SPACE_REFUSED_COUNT):
        assert_search_space_prereg_opens_book(
            replace(base, n_hypotheses=1, relative_value_config_ids=("p2rv-a", "p2rv-b"))
        )
    assert NEW_BOOK_MAX_CYCLES == 1
    assert NEW_BOOK_HYPOTHESIS_CAP == 25
    assert_search_space_prereg_opens_book(replace(base, n_hypotheses=20))
    assert_search_space_prereg_opens_book(replace(base, n_hypotheses=25))


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


def _mapping(path: Path) -> dict[str, object]:
    path.write_text("# fixture search-space prereg\n", encoding="utf-8")
    return {
        "lower_turnover": True,
        "longer_horizon": True,
        "relative_value_config_ids": ["p2rv-es-nq-guard-test"],
        "n_hypotheses": 1,
        "null_builder": NULL_BUILDER,
        "positive_control_included": True,
        "committed_path": str(path),
        "same_space_short_horizon": False,
        "nq_request": {
            "hypothesis_kind": KIND_RELATIVE_VALUE,
            "instruments": ["ES", "NQ"],
            "tape_window": "pre_holdout",
            "holdout_opened": False,
            "holdout_pin": "2026-01-28T23:00:00Z",
            "null_builder": NULL_BUILDER,
            "positive_control_included": True,
            "config_ids": ["p2rv-es-nq-guard-test"],
            "reuses_prereg_ids": [],
            "sim_requested": False,
            "promotion_requested": False,
        },
    }


@pytest.mark.unit
def test_search_space_mapping_requires_stated_hypothesis_count(tmp_path: Path) -> None:
    raw = _mapping(tmp_path / "space.md")
    parsed = search_space_prereg_from_mapping(raw, repo_root=tmp_path)
    assert parsed.n_hypotheses == 1
    missing = dict(raw)
    missing.pop("n_hypotheses")
    with pytest.raises(SearchSpaceRefused, match=SEARCH_SPACE_REFUSED_COUNT):
        search_space_prereg_from_mapping(missing, repo_root=tmp_path)
    as_bool = dict(raw)
    as_bool["n_hypotheses"] = True
    with pytest.raises(SearchSpaceRefused, match=SEARCH_SPACE_REFUSED_COUNT):
        search_space_prereg_from_mapping(as_bool, repo_root=tmp_path)
    over_cap = dict(raw)
    over_cap["n_hypotheses"] = NEW_BOOK_HYPOTHESIS_CAP + 1
    with pytest.raises(SearchSpaceRefused, match=SEARCH_SPACE_REFUSED_COUNT):
        search_space_prereg_from_mapping(over_cap, repo_root=tmp_path)

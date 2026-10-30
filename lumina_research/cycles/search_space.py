"""New-book open conditions after the 08:33 book split.

A new DSR/PBO book may open only after an explicit search-space pre-register:
lower turnover, longer horizon, at least one relative-value idea. NQ only
under NQOPEN guards. Improved null and a positive control are required.
This module does not pre-register a hypothesis and does not run a trial.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Mapping

from lumina_research.cycles.nq_research import (
    NQResearchRefused,
    NQResearchRequest,
    assert_nq_research_allowed,
)
from lumina_research.cycles.null_model import NULL_BUILDER

SEARCH_SPACE_REFUSED_MISSING = "new book requires a committed search-space prereg"
SEARCH_SPACE_REFUSED_TURNOVER = "new book requires lower turnover in the search-space prereg"
SEARCH_SPACE_REFUSED_HORIZON = "new book requires longer horizon in the search-space prereg"
SEARCH_SPACE_REFUSED_RV = "new book requires at least 1 relative-value idea"
SEARCH_SPACE_REFUSED_NULL = "new book requires the improved null (linear_magnitude)"
SEARCH_SPACE_REFUSED_CONTROL = "new book requires a positive control"
SEARCH_SPACE_REFUSED_SAME_SPACE = "new book cannot reuse the 1m short-horizon search space"
SEARCH_SPACE_REFUSED_NQ = "NQ in the new book must pass NQOPEN guards"


class SearchSpaceRefused(RuntimeError):
    """Search-space pre-register is missing or does not open a new book."""


@dataclass(frozen=True, slots=True)
class SearchSpacePrereg:
    lower_turnover: bool
    longer_horizon: bool
    relative_value_config_ids: tuple[str, ...]
    null_builder: str
    positive_control_included: bool
    committed_path: Path
    same_space_short_horizon: bool
    nq_request: NQResearchRequest


def assert_search_space_prereg_opens_book(prereg: SearchSpacePrereg) -> None:
    if not prereg.committed_path.is_file():
        raise SearchSpaceRefused(SEARCH_SPACE_REFUSED_MISSING)
    if prereg.lower_turnover is not True:
        raise SearchSpaceRefused(SEARCH_SPACE_REFUSED_TURNOVER)
    if prereg.longer_horizon is not True:
        raise SearchSpaceRefused(SEARCH_SPACE_REFUSED_HORIZON)
    if prereg.same_space_short_horizon is not False:
        raise SearchSpaceRefused(SEARCH_SPACE_REFUSED_SAME_SPACE)
    if len(prereg.relative_value_config_ids) < 1:
        raise SearchSpaceRefused(SEARCH_SPACE_REFUSED_RV)
    if prereg.null_builder != NULL_BUILDER:
        raise SearchSpaceRefused(SEARCH_SPACE_REFUSED_NULL)
    if prereg.positive_control_included is not True:
        raise SearchSpaceRefused(SEARCH_SPACE_REFUSED_CONTROL)
    if set(prereg.relative_value_config_ids) - set(prereg.nq_request.config_ids):
        raise SearchSpaceRefused(SEARCH_SPACE_REFUSED_RV)
    try:
        assert_nq_research_allowed(prereg.nq_request)
    except NQResearchRefused as exc:
        raise SearchSpaceRefused(f"{SEARCH_SPACE_REFUSED_NQ}: {exc}") from exc


def search_space_prereg_from_mapping(
    raw: Mapping[str, object],
    *,
    repo_root: Path,
) -> SearchSpacePrereg:
    path_value = raw.get("committed_path")
    if not isinstance(path_value, str) or not path_value.strip():
        raise SearchSpaceRefused(SEARCH_SPACE_REFUSED_MISSING)
    candidate = Path(path_value)
    committed = candidate if candidate.is_absolute() else repo_root / candidate
    nq_raw = raw.get("nq_request")
    if not isinstance(nq_raw, dict):
        raise SearchSpaceRefused(SEARCH_SPACE_REFUSED_NQ)
    nq_typed: dict[str, object] = {}
    for key, item in nq_raw.items():
        if not isinstance(key, str):
            raise SearchSpaceRefused(SEARCH_SPACE_REFUSED_NQ)
        nq_typed[key] = item
    ids = raw.get("relative_value_config_ids")
    if not isinstance(ids, list) or not ids:
        raise SearchSpaceRefused(SEARCH_SPACE_REFUSED_RV)
    rv_ids = tuple(str(item) for item in ids)
    return SearchSpacePrereg(
        lower_turnover=_as_bool(raw.get("lower_turnover"), field="lower_turnover"),
        longer_horizon=_as_bool(raw.get("longer_horizon"), field="longer_horizon"),
        relative_value_config_ids=rv_ids,
        null_builder=_as_str(raw.get("null_builder"), field="null_builder"),
        positive_control_included=_as_bool(
            raw.get("positive_control_included"),
            field="positive_control_included",
        ),
        committed_path=committed,
        same_space_short_horizon=_as_bool(
            raw.get("same_space_short_horizon"),
            field="same_space_short_horizon",
        ),
        nq_request=_nq_request_from_mapping(nq_typed),
    )


def _nq_request_from_mapping(raw: Mapping[str, object]) -> NQResearchRequest:
    instruments = raw.get("instruments")
    config_ids = raw.get("config_ids")
    reuses = raw.get("reuses_prereg_ids")
    if not isinstance(instruments, list) or not isinstance(config_ids, list):
        raise SearchSpaceRefused(SEARCH_SPACE_REFUSED_NQ)
    reuse_ids: tuple[str, ...]
    if reuses is None:
        reuse_ids = ()
    elif isinstance(reuses, list):
        reuse_ids = tuple(str(item) for item in reuses)
    else:
        raise SearchSpaceRefused(SEARCH_SPACE_REFUSED_NQ)
    return NQResearchRequest(
        hypothesis_kind=_as_str(raw.get("hypothesis_kind"), field="hypothesis_kind"),
        instruments=tuple(str(item) for item in instruments),
        tape_window=_as_str(raw.get("tape_window"), field="tape_window"),
        holdout_opened=_as_bool(raw.get("holdout_opened"), field="holdout_opened"),
        holdout_pin=_as_str(raw.get("holdout_pin"), field="holdout_pin"),
        null_builder=_as_str(raw.get("null_builder"), field="null_builder"),
        positive_control_included=_as_bool(
            raw.get("positive_control_included"),
            field="positive_control_included",
        ),
        config_ids=tuple(str(item) for item in config_ids),
        reuses_prereg_ids=reuse_ids,
        sim_requested=_as_bool(raw.get("sim_requested"), field="sim_requested"),
        promotion_requested=_as_bool(
            raw.get("promotion_requested"),
            field="promotion_requested",
        ),
    )


def _as_bool(value: object, *, field: str) -> bool:
    if isinstance(value, bool):
        return value
    raise SearchSpaceRefused(f"search-space prereg {field} must be a boolean")


def _as_str(value: object, *, field: str) -> str:
    if isinstance(value, str) and value.strip():
        return value
    raise SearchSpaceRefused(f"search-space prereg {field} must be a string")

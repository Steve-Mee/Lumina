"""Pre-registration lock: detector-fix seeds were committed before verify."""

from __future__ import annotations

from lumina_research.monitoring.campaign import DEFAULT_CAMPAIGN_SEEDS
from lumina_research.proof.independent import HOLDOUT_SEEDS, INDEPENDENT_SEEDS
from tests.research.phase5_audit_campaign import AUDIT_SEEDS
from tests.research.phase5_detector_seeds import DETECTOR_FIX_SEEDS, assert_detector_fix_seeds


def test_detector_fix_seeds_are_pre_registered_and_unseen() -> None:
    assert_detector_fix_seeds()
    assert len(DETECTOR_FIX_SEEDS) == 10
    assert set(DETECTOR_FIX_SEEDS).isdisjoint(set(DEFAULT_CAMPAIGN_SEEDS))
    assert set(DETECTOR_FIX_SEEDS).isdisjoint(set(INDEPENDENT_SEEDS))
    assert set(DETECTOR_FIX_SEEDS).isdisjoint(set(HOLDOUT_SEEDS))
    assert set(DETECTOR_FIX_SEEDS).isdisjoint(set(AUDIT_SEEDS))

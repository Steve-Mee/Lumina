"""Meta-milestone engine tests."""

from __future__ import annotations

from pathlib import Path

import pytest
import yaml

from lumina_core.evolution.meta_milestones import (
    dynamic_stage_specs,
    load_meta_milestones,
    propose_next_milestone,
)


@pytest.mark.unit
def test_propose_next_milestone_respects_floor(tmp_path: Path) -> None:
    (tmp_path / "config.yaml").write_text(
        yaml.safe_dump(
            {
                "birth_v2": {
                    "certificate_thresholds": {"min_oos_winrate": 0.48},
                }
            }
        ),
        encoding="utf-8",
    )
    milestone = propose_next_milestone(
        tmp_path,
        generation=0,
        current_winrate=0.50,
        current_sharpe=0.40,
        regime_coverage=3,
    )
    assert milestone is not None
    assert milestone.milestone_id == "M16"
    assert milestone.target_value >= 0.48
    loaded = load_meta_milestones(tmp_path)
    assert len(loaded) == 1
    specs = dynamic_stage_specs(tmp_path)
    assert specs[0]["stage_id"] == "meta_m16"
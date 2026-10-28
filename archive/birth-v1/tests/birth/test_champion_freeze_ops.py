"""Champion freeze decision card + CLI status (OR5 ops surface)."""

from __future__ import annotations

import importlib.util
import json
from pathlib import Path

import pytest

from lumina_core.birth.champion_freeze_ops import build_champion_freeze_decision_card

_REPO = Path(__file__).resolve().parents[2]
_OPS_PATH = _REPO / "scripts" / "validation" / "champion_freeze_ops.py"


def _load_ops_module():
    spec = importlib.util.spec_from_file_location("champion_freeze_ops_cli", _OPS_PATH)
    assert spec is not None and spec.loader is not None
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


@pytest.mark.unit
def test_decision_card_freeze_open() -> None:
    card = build_champion_freeze_decision_card(
        progress={
            "phase": "swarm_reject_hard_stop",
            "sub_phase": "swarm_reject_hard_stop",
            "swarm_rejected_no_lift": True,
            "swarm_champion_accepted": False,
            "needs_attention": True,
            "stage_blocker_metric": "position_flat",
            "stage_blocker_value": 0.956,
            "volume_gate_status": "PASSED",
            "stages_passed": ["stage1_trend"],
            "cumulative_trades": 1224,
            "autonomous_recovery_successes": 3,
            "plateau_active": True,
            "plateau_evolution_step": 4,
        }
    )
    assert card["schema"] == "champion_freeze_decision_card_v1"
    assert card["freeze_active"] is True
    assert card["decision"] == "accept_champion_or_wipe"
    assert card["stage1_certified_receipt"] is True
    assert "accept" in card["commands"]
    assert "checklist" in card["commands"]
    assert "train_through_freeze" in card["forbidden"]


@pytest.mark.unit
def test_decision_card_no_freeze() -> None:
    card = build_champion_freeze_decision_card(
        progress={"phase": "curriculum_learning", "swarm_rejected_no_lift": False}
    )
    assert card["freeze_active"] is False
    assert card["decision"] == "no_freeze"


@pytest.mark.unit
def test_decision_card_accepted() -> None:
    card = build_champion_freeze_decision_card(
        progress={
            "swarm_rejected_no_lift": True,
            "swarm_champion_accepted": True,
        }
    )
    assert card["freeze_active"] is False
    assert card["decision"] == "freeze_resolved_accepted"


@pytest.mark.unit
def test_cli_status_exit_codes(tmp_path: Path) -> None:
    state = tmp_path / "state"
    state.mkdir()
    (state / "lumina_birth_progress.json").write_text(
        json.dumps(
            {
                "phase": "swarm_reject_hard_stop",
                "swarm_rejected_no_lift": True,
                "needs_attention": True,
            }
        ),
        encoding="utf-8",
    )
    ops = _load_ops_module()
    rc = ops.main(["--workspace", str(tmp_path), "status"])
    assert rc == 2

    (state / "lumina_birth_progress.json").write_text(
        json.dumps({"phase": "curriculum_learning"}),
        encoding="utf-8",
    )
    rc2 = ops.main(["--workspace", str(tmp_path), "status"])
    assert rc2 == 0


@pytest.mark.unit
def test_cli_accept_requires_confirm(tmp_path: Path) -> None:
    state = tmp_path / "state"
    state.mkdir()
    (state / "lumina_birth_progress.json").write_text(
        json.dumps(
            {
                "phase": "swarm_reject_hard_stop",
                "swarm_rejected_no_lift": True,
            }
        ),
        encoding="utf-8",
    )
    ops = _load_ops_module()
    rc = ops.main(["--workspace", str(tmp_path), "accept"])
    assert rc == 1


@pytest.mark.unit
def test_cli_wipe_requires_confirm_and_freeze(tmp_path: Path) -> None:
    state = tmp_path / "state"
    state.mkdir()
    (state / "lumina_birth_progress.json").write_text(
        json.dumps({"phase": "curriculum_learning"}),
        encoding="utf-8",
    )
    ops = _load_ops_module()
    rc = ops.main(["--workspace", str(tmp_path), "wipe", "--confirm"])
    assert rc == 1  # no freeze without --force

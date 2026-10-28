"""Genesis first-life protocol: new seed, refuse old body, REAL door locked."""

from __future__ import annotations

from pathlib import Path

import pytest

from lumina_core.birth.awakening_mark_eyes import TRAIN_SEED
from lumina_core.birth.awakening_path_exit_k3 import PATH_EXIT_K3_SHADOW
from lumina_core.birth.awakening_path_shape_k3_dead import PATH_SHAPE_K3_SHADOW
from lumina_core.birth.genesis_cloud_const import (
    FORBIDDEN_TICKS_SHA16,
    G6_TAG,
    GENESIS_FIXTURE_SEED,
    GENESIS_START_ET_ISO,
)
from lumina_core.birth.genesis_cloud_protocol import (
    GenesisProtocolError,
    assert_genesis_seed,
    assert_real_not_yes_on_synthetic,
    compose_genesis_flags,
    locked_g6_tag,
    real_flag_for_source,
    refuse_old_parent_as_input,
    refuse_old_ticks_sha,
)
from lumina_core.birth.genesis_mark_eyes_train import GENESIS_TRAIN_SEED
from lumina_core.rl.observation_builder import OBSERVATION_DIM


@pytest.mark.unit
def test_genesis_seed_is_20260904() -> None:
    assert GENESIS_FIXTURE_SEED == 20260904
    assert GENESIS_TRAIN_SEED == 20260904
    assert GENESIS_START_ET_ISO.startswith("2026-06-08")
    assert assert_genesis_seed(20260904) == 20260904
    with pytest.raises(GenesisProtocolError):
        assert_genesis_seed(20260901)
    with pytest.raises(GenesisProtocolError):
        assert_genesis_seed(20260902)
    assert TRAIN_SEED == 20260901


@pytest.mark.unit
def test_refuses_old_parent_zip_name_as_input(tmp_path: Path) -> None:
    with pytest.raises(GenesisProtocolError, match="old parent zip"):
        refuse_old_parent_as_input(tmp_path / "birth_exit_pi_star.zip")
    with pytest.raises(GenesisProtocolError, match="old parent zip"):
        refuse_old_parent_as_input("awakening_mark_eyes_pi_star.zip")
    with pytest.raises(GenesisProtocolError, match="old parent zip|birth_cloud_run"):
        refuse_old_parent_as_input(Path("reports/birth_cloud_run/artifacts/awakening_select_pi_star.zip"))
    with pytest.raises(GenesisProtocolError, match="birth_cloud_run"):
        refuse_old_parent_as_input(Path("reports/birth_cloud_run/artifacts/other_policy.zip"))
    refuse_old_parent_as_input(tmp_path / "genesis_birth_exit_pi_star.zip")


@pytest.mark.unit
def test_refuses_ticks_sha_7e86c2bb_as_this_tape() -> None:
    assert FORBIDDEN_TICKS_SHA16 == "7e86c2bb1c71d514"
    with pytest.raises(GenesisProtocolError, match="7e86c2bb"):
        refuse_old_ticks_sha("7e86c2bb1c71d514")
    with pytest.raises(GenesisProtocolError, match="7e86c2bb"):
        refuse_old_ticks_sha("7e86c2bbdeadbeef")
    assert refuse_old_ticks_sha("abc123") == "abc123"


@pytest.mark.unit
def test_real_flag_cannot_be_yes_when_source_synthetic() -> None:
    assert real_flag_for_source(source="synthetic_cloud_fixture", real_data_pct=0.0) == "no"
    flags = compose_genesis_flags({"source": "synthetic_cloud_fixture", "real_data_pct": 0.0, "REAL": "no"})
    assert flags["REAL"] == "no"
    with pytest.raises(GenesisProtocolError, match="protocol crime"):
        assert_real_not_yes_on_synthetic({"source": "synthetic_cloud_fixture", "real_data_pct": 0.0, "REAL": "yes"})


@pytest.mark.unit
def test_g6_tag_locked() -> None:
    assert locked_g6_tag() == "REAL_DOOR_LOCKED"
    assert G6_TAG == "REAL_DOOR_LOCKED"
    flags = compose_genesis_flags({"G6_tag": "OPEN"})
    assert flags["G6_tag"] == "REAL_DOOR_LOCKED"


@pytest.mark.unit
def test_observation_dim_still_43() -> None:
    assert OBSERVATION_DIM == 43
    src = Path("lumina_core/rl/observation_builder.py").read_text(encoding="utf-8")
    assert "OBSERVATION_DIM = 43" in src


@pytest.mark.unit
def test_hooks_default_false() -> None:
    assert PATH_EXIT_K3_SHADOW.get() is False
    assert PATH_SHAPE_K3_SHADOW.get() is False
    src_exit = Path("lumina_core/birth/awakening_path_exit_k3.py").read_text(encoding="utf-8")
    src_shape = Path("lumina_core/birth/awakening_path_shape_k3_dead.py").read_text(encoding="utf-8")
    assert "default=False" in src_exit
    assert "default=False" in src_shape

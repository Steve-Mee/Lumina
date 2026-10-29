"""D2: synthetic ValidationResult cannot count as an S3 survivor."""

from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path

import pytest

from lumina_core.research_bridge.sim_gate import evaluate
from lumina_research.agents.promotion import PromotionAgent
from lumina_research.agents.validation_agent import ValidationAgent
from lumina_research.risk_core.config import load_default_config
from lumina_research.risk_core.engine import RiskCore
from lumina_research.validation.nt_tape import fixture_closed_mes_bars, materializer_from_rows
from tests.research.phase2_harness import make_agents
from tests.research_bridge.s3_helpers import passing_context, survivor


@pytest.mark.unit
def test_default_validation_agent_stamps_synthetic(tmp_path: Path) -> None:
    _bus, _reg, _auth, hyp, validation, _promo = make_agents(tmp_path)
    hyp.generate(seed=7, counts=(1, 1))
    results = validation.flush()
    assert results
    assert all(item.tape_kind == "synthetic" for item in results)
    ctx = passing_context(
        survivors=(
            survivor(tag="syn", family="trend", tape_kind="synthetic"),
            survivor(tag="syn2", family="meanrev", tape_kind="synthetic"),
        )
    )
    ok, reason = evaluate(ctx)
    assert ok is False
    assert reason in {"survivors_not_nt_pit", "survivors_insufficient"}


@pytest.mark.unit
def test_nt_pit_materializer_stamps_nt_pit(tmp_path: Path) -> None:
    now = datetime(2025, 12, 31, 21, 0, tzinfo=timezone.utc)
    rows = fixture_closed_mes_bars(now=now)
    materializer = materializer_from_rows(rows, now=now, purpose="gate")
    bus, registry, authority, hyp, _default, _promo = make_agents(tmp_path)
    validation = ValidationAgent(
        bus=bus,
        registry=registry,
        authority=authority,
        experiment_log_path=tmp_path / "exp-nt.jsonl",
        materializer=materializer,
        audit_path=tmp_path / "audit-nt.jsonl",
    )
    hyp.generate(seed=11, counts=(1, 0))
    results = validation.flush()
    assert results
    assert results[0].tape_kind == "nt_pit"


@pytest.mark.unit
def test_admit_for_sim_refuses_synthetic_promotions(tmp_path: Path) -> None:
    bus, registry, authority, hyp, validation, _old = make_agents(tmp_path)
    del registry
    core = RiskCore(load_default_config(), equity=100_000.0)
    promo = PromotionAgent(
        bus=bus,
        core=core,
        authority=authority,
        experiment_log_path=tmp_path / "exp-sim.jsonl",
        admit_for_sim=True,
    )
    hyp.generate(seed=7, counts=(2, 2))
    validation.flush()
    assert promo.issued() == ()

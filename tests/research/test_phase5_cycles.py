"""P2 templates, fills, cost bands, data discovery, kill-rate diagnostic."""

from __future__ import annotations

import json
import random
import struct
from datetime import datetime, timezone
from pathlib import Path

import pytest

from lumina_core.agent_orchestration.schemas_research import EconomicRationale, HypothesisProposed
from lumina_research.agents.economic_templates import REGISTERED_TEMPLATE_IDS, TemplateRefused, require_economic_template
from lumina_research.agents.hypothesis import HypothesisRefused
from lumina_research.agents.synthetic import MaterializeRefused, materialize
from lumina_research.cycles.catalog import (
    CATALOG_EXPECTED_HORIZON_BARS,
    N_HYPOTHESES,
    N_TEMPLATES,
    EconomicCatalogGenerator,
    catalog,
)
from lumina_research.cycles.cost_bands import ES_ONE_WAY_USD, MES_ONE_WAY_USD, band_for, report_band
from lumina_research.cycles.data import DataRefused, ResearchBar, discover_data, tape_for
from lumina_research.cycles.first_cycle import FIRST_CYCLE_CONFIG_IDS, first_cycle_specs
from lumina_research.cycles.fills import FillRefused, fill_probability, trade_through_fill
from lumina_research.cycles.geometry import GeometryRefused, floors_for, require_geometry
from lumina_research.cycles.kill_rate import diagnose_kill_rate
from lumina_research.cycles.runner import run_research_cycles
from lumina_research.cycles.sim_plan import SIM_MIN_SURVIVORS, SIM_MIN_TRADES, SIM_MIN_TRADING_DAYS, write_sim_plan
from lumina_research.cycles.strategies import StrategyRefused, simulate
from tests.research.test_phase2_coverage import _rationale


def _bars(n: int = 241, seed: int = 1) -> tuple[ResearchBar, ...]:
    rng = random.Random(seed)
    px = 5000.0
    rows: list[ResearchBar] = []
    for index in range(n):
        px += rng.gauss(0.0, 0.75)
        ts = 1_700_000_000_000_000_000 + index * 60_000_000_000
        rows.append(
            ResearchBar(ts_ns=ts, open=px, high=px + 0.75, low=px - 0.75, close=px, volume=1_000.0 + index)
        )
    return tuple(rows)


def _write_csv(path: Path, bars: tuple[ResearchBar, ...]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    lines = ["timestamp,open,high,low,close,volume"]
    for bar in bars:
        stamp = datetime.fromtimestamp(bar.ts_ns / 1_000_000_000, tz=timezone.utc).isoformat()
        lines.append(f"{stamp},{bar.open},{bar.high},{bar.low},{bar.close},{bar.volume}")
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


@pytest.mark.unit
def test_catalog_is_twelve_templates_twenty_four_variants() -> None:
    specs = catalog()
    assert len(specs) == N_HYPOTHESES == 24
    templates = {item.template_id for item in specs}
    assert templates == set(REGISTERED_TEMPLATE_IDS)
    assert len(templates) == N_TEMPLATES == 12
    for spec in specs:
        assert spec.rationale.holding_period.strip()
        assert spec.rationale.survives_costs.strip()
        assert spec.rationale.falsification_criterion.strip()
    drafts = EconomicCatalogGenerator(specs).drafts(rng=random.Random(1), count=N_HYPOTHESES, start_index=0)
    assert CATALOG_EXPECTED_HORIZON_BARS >= 1
    assert CATALOG_EXPECTED_HORIZON_BARS not in {20, 30}
    assert all(item.expected_horizon_bars == CATALOG_EXPECTED_HORIZON_BARS for item in drafts)


@pytest.mark.unit
def test_freeform_economic_template_is_refused() -> None:
    with pytest.raises(TemplateRefused, match="registered template"):
        require_economic_template("llm_freeform")
    generator = EconomicCatalogGenerator()
    with pytest.raises(Exception):
        generator.drafts(rng=random.Random(1), count=1, start_index=0)


@pytest.mark.unit
def test_tick_floors_and_geometry_bands() -> None:
    assert floors_for("ES") == (8, 4)
    assert floors_for("MES") == (16, 8)
    small = require_geometry(root="ES", target_ticks=7, stop_ticks=4)
    assert small.target_ticks == 7 and small.stop_ticks == 4
    with pytest.raises(GeometryRefused):
        require_geometry(root="ES", target_ticks=0, stop_ticks=4)
    geo = require_geometry(root="MES", target_ticks=16, stop_ticks=8)
    assert 0.0 < geo.break_even_win_rate < 1.0
    assert band_for("ES") == ES_ONE_WAY_USD
    assert band_for("MES") == MES_ONE_WAY_USD
    band = report_band("ES")
    assert band.modeled_one_way_ticks > 0.0


@pytest.mark.unit
def test_limit_fill_requires_trade_through_and_volume() -> None:
    bar = ResearchBar(ts_ns=1, open=10.0, high=10.5, low=9.5, close=10.0, volume=100.0)
    assert trade_through_fill(side=1.0, limit=9.4, bar=bar, average_volume=50.0) is False
    assert trade_through_fill(side=1.0, limit=9.6, bar=bar, average_volume=50.0) is True
    assert trade_through_fill(side=1.0, limit=9.6, bar=bar, average_volume=500.0) is False
    assert fill_probability(side=-1.0, limit=10.4, bar=bar, average_volume=200.0) == 0.5
    assert fill_probability(side=0.0, limit=10.0, bar=bar, average_volume=50.0) == 0.0
    with pytest.raises(FillRefused):
        trade_through_fill(side=1.0, limit=9.6, bar=bar, average_volume=0.0)


@pytest.mark.unit
def test_all_families_run_on_labeled_fixture_bars() -> None:
    bars = _bars()
    geo = require_geometry(root="MES", target_ticks=16, stop_ticks=8)
    families = (
        ("mean_reversion", 10, 1.5, "fade"),
        ("volume_imbalance", 10, 0.55, "fade"),
        ("regime_momentum", 10, 0.4, "follow"),
        ("opening_range", 5, 0.0, "breakout"),
        ("opening_range", 15, 0.0, "fade"),
        ("overnight_gap", 1, 8.0, "fade"),
        ("vwap_distance", 20, 1.5, "fade"),
        ("range_compression", 20, 0.25, "breakout"),
        ("close_reversal", 3, 0.0, "fade"),
        ("time_of_day", 15, 0.0, "fade"),
        ("trend_pullback", 20, 0.0, "follow"),
        ("volatility_expansion", 20, 0.25, "breakout"),
    )
    for family, lookback, threshold, mode in families:
        gross, positions, markets = simulate(
            family=family, bars=bars, geometry=geo, lookback=lookback, threshold=threshold, mode=mode
        )
        assert len(gross) == len(positions) == len(markets) == 241
    with pytest.raises(StrategyRefused, match="unknown"):
        simulate(family="freeform", bars=bars, geometry=geo, lookback=5, threshold=1.0, mode="fade")


@pytest.mark.unit
def test_discover_data_stops_without_real_bars(tmp_path: Path) -> None:
    status = discover_data(repo_root=tmp_path)
    assert status.usable is False
    assert "ES" in status.missing
    with pytest.raises(DataRefused):
        tape_for(status, "ES")
    csv_dir = tmp_path / "data" / "research" / "MES" / "1m"
    _write_csv(csv_dir / "mes.csv", _bars())
    loaded = discover_data(repo_root=tmp_path)
    assert loaded.usable is True
    tape = tape_for(loaded, "MES")
    assert len(tape.bars) >= 241


@pytest.mark.unit
def test_jsonl_and_binary_loaders(tmp_path: Path) -> None:
    bars = _bars()
    jsonl = tmp_path / "data" / "research" / "ES" / "1m" / "es.jsonl"
    jsonl.parent.mkdir(parents=True, exist_ok=True)
    lines = []
    for bar in bars:
        stamp = datetime.fromtimestamp(bar.ts_ns / 1_000_000_000, tz=timezone.utc).isoformat()
        lines.append(
            json.dumps(
                {
                    "timestamp": stamp,
                    "open": bar.open,
                    "high": bar.high,
                    "low": bar.low,
                    "close": bar.close,
                    "volume": bar.volume,
                }
            )
        )
    jsonl.write_text("\n".join(lines) + "\n", encoding="utf-8")
    status = discover_data(repo_root=tmp_path)
    assert status.usable is True
    record = struct.Struct("<q4iI")
    blob = tmp_path / "reports" / "playground_bar_archive" / "NQ.bars"
    blob.parent.mkdir(parents=True, exist_ok=True)
    payload = b"".join(record.pack(bar.ts_ns, 20000, 20004, 19996, 20000, 1000) for bar in bars)
    blob.write_bytes(payload)
    both = discover_data(repo_root=tmp_path)
    roots = {item.instrument for item in both.tapes}
    assert "ES" in roots
    assert "NQ" in roots
    blob.write_bytes(b"nope")
    with pytest.raises(DataRefused):
        discover_data(repo_root=tmp_path)


@pytest.mark.unit
def test_kill_rate_is_diagnostic_not_a_hard_stop() -> None:
    assert diagnose_kill_rate(kill_rate=None, n_hypotheses=0, n_survivors=0) == "not_tested"
    assert diagnose_kill_rate(kill_rate=0.5, n_hypotheses=24, n_survivors=12).startswith("flag_")
    assert diagnose_kill_rate(kill_rate=0.75, n_hypotheses=24, n_survivors=6) == "flag_structurally_low"
    assert diagnose_kill_rate(kill_rate=0.99, n_hypotheses=24, n_survivors=0) == "flag_all_dead_check_known_good_synthetics"
    assert diagnose_kill_rate(kill_rate=0.95, n_hypotheses=24, n_survivors=1) == "expected_high_kill"
    assert diagnose_kill_rate(kill_rate=0.85, n_hypotheses=24, n_survivors=4) == "within_expectation"


@pytest.mark.unit
def test_research_cycles_stop_without_real_data(tmp_path: Path) -> None:
    result = run_research_cycles(
        work_dir=tmp_path / "work",
        report_dir=tmp_path / "reports",
        evolution_log_dir=tmp_path / "evo",
        repo_root=tmp_path,
    )
    assert result.data.usable is False
    assert result.kill_rate is None
    assert result.kill_rate_flag == "not_tested"
    assert result.report.n_hypotheses == 12
    assert (tmp_path / "reports" / "phase5_first_cycle_preregister.md").is_file()
    assert (tmp_path / "reports" / "phase5_p2_data_spec.md").is_file()
    assert all(item.death_reason == "not_tested_no_real_data" for item in result.report.rows)
    assert (tmp_path / "reports" / "phase5_research_cycles.json").is_file()
    assert (tmp_path / "reports" / "phase5_sim_plan.md").is_file()
    plan = (tmp_path / "reports" / "phase5_sim_plan.md").read_text(encoding="utf-8")
    assert str(SIM_MIN_SURVIVORS) in plan
    assert str(SIM_MIN_TRADING_DAYS) in plan
    assert str(SIM_MIN_TRADES) in plan
    assert "do not start" in plan.lower() or "Do not start" in plan


def _calendar_bars(n: int = 400, seed: int = 1) -> tuple[ResearchBar, ...]:
    rng = random.Random(seed)
    px = 5000.0
    start = datetime(2023, 10, 28, tzinfo=timezone.utc)
    end = datetime(2026, 10, 28, tzinfo=timezone.utc)
    step = (end - start).total_seconds() / float(max(n - 1, 1))
    rows: list[ResearchBar] = []
    for index in range(n):
        px += rng.gauss(0.0, 0.75)
        ts_ns = int((start.timestamp() + float(index) * step) * 1_000_000_000)
        rows.append(
            ResearchBar(ts_ns=ts_ns, open=px, high=px + 0.75, low=px - 0.75, close=px, volume=1_000.0 + index)
        )
    return tuple(rows)


@pytest.mark.unit
def test_first_cycle_is_twelve_mes_mnq_variants() -> None:
    selected = first_cycle_specs()
    assert 10 <= len(selected) <= 15
    assert len(selected) == 12
    assert {item.config_id for item in selected} == set(FIRST_CYCLE_CONFIG_IDS)
    assert {item.instrument for item in selected} <= {"MES", "MNQ"}
    assert {item.template_id for item in selected} == {item.template_id for item in catalog()}
    vx = next(item for item in selected if item.config_id == "vx-mes-20")
    assert vx.threshold == 0.75
    assert vx.session_filter == "rth"
    assert vx.session_end_flatten is True
    assert vx.has_fit_step is False


@pytest.mark.unit
def test_research_cycles_on_labeled_fixture_runs_gate(tmp_path: Path) -> None:
    _write_csv(tmp_path / "data" / "research" / "MES" / "1m" / "mes.csv", _calendar_bars(n=400))
    spec = catalog()[0]
    result = run_research_cycles(
        work_dir=tmp_path / "work",
        report_dir=tmp_path / "reports",
        evolution_log_dir=tmp_path / "evo",
        repo_root=tmp_path,
        specs=(spec,),
    )
    assert result.data.usable is True
    assert result.report.n_tested == 1
    assert result.report.rows[0].pre_registered is True
    assert result.report.rows[0].tested is True
    assert result.report.rows[0].n_oos_windows is not None
    assert result.report.kill_rate_flag != "not_tested"


@pytest.mark.unit
def test_synthetic_materialize_refuses_economic() -> None:
    hyp = HypothesisProposed(
        hypothesis_id="hyp-e",
        config_id="e0",
        trial_id=1,
        agent_id="hypothesis_agent",
        generator_id="mean_reversion",
        kind="economic",
        instrument="MES",
        seed=1,
        n_obs=241,
        mu=0.0,
        sigma=0.01,
        planted=False,
        proposed_quantity=1.0,
        proposed_price=5000.0,
        proposed_notional=5000.0,
        expected_horizon_bars=8,
        rationale=_rationale(),
    )
    with pytest.raises(MaterializeRefused, match="real-data"):
        materialize(hyp)


@pytest.mark.unit
def test_hypothesis_agent_refuses_unregistered_economic(tmp_path: Path) -> None:
    from lumina_core.agent_orchestration.event_bus import EventBus
    from lumina_research.agents.generators import HypothesisDraft, HypothesisGenerator
    from lumina_research.agents.hypothesis import HypothesisAgent
    from lumina_research.validation.trial_registry import TrialRegistry

    class _Free(HypothesisGenerator):
        @property
        def generator_id(self) -> str:
            return "llm"

        def drafts(self, *, rng: object, count: int, start_index: int) -> tuple[HypothesisDraft, ...]:
            del rng, count, start_index
            return (
                HypothesisDraft(
                    config_id="free",
                    generator_id="llm_freeform",
                    kind="economic",
                    instrument="MES",
                    seed=1,
                    n_obs=360,
                    mu=0.0,
                    sigma=0.01,
                    planted=False,
                    proposed_quantity=1.0,
                    proposed_price=5000.0,
                    proposed_notional=5000.0,
                    rationale=EconomicRationale(
                        mechanism="A free-form LLM story about an edge xx",
                        why_edge_exists="The model liked the backtest curve a lot",
                        other_side="Unspecified residual flow in the tape xx",
                        expected_regime="any regime the prompt mentioned xx",
                        falsification_criterion="never falsified by construction xx",
                    ),
                ),
            )

    agent = HypothesisAgent(
        bus=EventBus(),
        registry=TrialRegistry(tmp_path / "a.jsonl"),
        generators=(_Free(),),
        experiment_log_path=tmp_path / "e.jsonl",
    )
    with pytest.raises(HypothesisRefused, match="registered template"):
        agent.generate(seed=1, counts=(1,))


@pytest.mark.unit
def test_write_sim_plan_does_not_claim_orders(tmp_path: Path) -> None:
    path = write_sim_plan(tmp_path)
    text = path.read_text(encoding="utf-8")
    assert "No SIM session" in text
    assert "Forbidden" in text

"""Independent PR #63 zero-gap audit: holdout/SimSafety attacks, DD-only high-vol, pre-reg."""

from __future__ import annotations

import ast
import json
import struct
from datetime import datetime, timezone
from pathlib import Path

import pytest

from lumina_research.cycles import first_cycle as first_cycle_mod
from lumina_research.cycles import runner as runner_mod
from lumina_research.cycles.data import LoadedTape, ResearchBar, discover_data
from lumina_research.cycles.first_cycle import FIRST_CYCLE_CONFIG_IDS, first_cycle_specs
from lumina_research.cycles.holdout import (
    EVAL_PURPOSES,
    HOLDOUT_MONTHS_MAX,
    HOLDOUT_MONTHS_MIN,
    LOCKED_PURPOSES,
    HoldoutLocked,
    access_bars,
    assert_not_holdout,
    holdout_start_ns,
    split_holdout,
)
from lumina_research.monitoring.acceptance import (
    DETECTION_RATE_MIN,
    FAR_HEALTHY_MAX,
    FAR_HIGH_VOL_MAX,
    HIGH_VOL_VIX,
    MATERIAL_DD_MULT,
    TTD_MAX_TRADING_DAYS,
)
from lumina_research.monitoring.config import load_default_config
from lumina_research.monitoring.horizons import combined_assessment
from lumina_research.monitoring.material import _max_drawdown, assess_material
from lumina_research.monitoring.synthetic import oos_stats
from lumina_research.ports.sim_safety import SimSafetyConfig, SimSafetyGate, SimSafetyRefused
from lumina_research.proof.independent import HOLDOUT_SEEDS, INDEPENDENT_OOS, INDEPENDENT_SEEDS
from tests.research.phase4_harness import admit_signal, make_runtime
from tests.research.phase4_mutants import PHASE5_CHANGE_FILES, iter_mutants
from tests.research.phase5_audit_campaign import AUDIT_SEEDS, assert_audit_seeds

ROOT = Path(__file__).resolve().parents[2]
BANNED_IMPORTS = (
    "lumina_core.risk",
    "lumina_core.trading_engine",
    "lumina_core.broker",
    "lumina_core.evolution.promotion_gate",
    "grpc",
)
ORDER_CALLS = frozenset({"place_order", "submit_order", "connect_fabric", "flatten"})
ALLOWED_ORDER_DEF_FILES = frozenset(
    {
        "lumina_research/ports/shadow.py",
        "lumina_research/ports/fills.py",
    }
)


def _calendar_bars(n: int = 400) -> tuple[ResearchBar, ...]:
    px = 5000.0
    start = datetime(2023, 10, 28, tzinfo=timezone.utc)
    end = datetime(2026, 10, 28, tzinfo=timezone.utc)
    step = (end - start).total_seconds() / float(max(n - 1, 1))
    rows: list[ResearchBar] = []
    for index in range(n):
        ts_ns = int((start.timestamp() + float(index) * step) * 1_000_000_000)
        rows.append(ResearchBar(ts_ns=ts_ns, open=px, high=px + 0.5, low=px - 0.5, close=px, volume=100.0))
    return tuple(rows)


def _bar_json(bar: ResearchBar) -> str:
    stamp = datetime.fromtimestamp(bar.ts_ns / 1_000_000_000, tz=timezone.utc).isoformat()
    return json.dumps(
        {
            "timestamp": stamp,
            "open": bar.open,
            "high": bar.high,
            "low": bar.low,
            "close": bar.close,
            "volume": bar.volume,
        }
    )


def _dd_only_series(*, oos_mean: float, n: int = 70, decay_start: int = 25, depth: float = 0.40) -> tuple[float, ...]:
    peak = oos_mean + 0.35
    rows: list[float] = []
    for index in range(n):
        if index == decay_start:
            rows.append(peak - depth)
        else:
            rows.append(peak)
    return tuple(rows)


def _module_from_import(node: ast.AST) -> str:
    if isinstance(node, ast.ImportFrom):
        return node.module or ""
    if isinstance(node, ast.Import):
        return node.names[0].name
    return ""


@pytest.mark.unit
def test_audit_seeds_never_seen() -> None:
    assert_audit_seeds()
    assert set(AUDIT_SEEDS).isdisjoint(set(HOLDOUT_SEEDS))
    assert set(AUDIT_SEEDS).isdisjoint(set(INDEPENDENT_SEEDS))


@pytest.mark.unit
def test_holdout_attacks_purpose_tricks_and_timestamp_edges(tmp_path: Path) -> None:
    bars = _calendar_bars()
    tape = LoadedTape(instrument="MES", bar_size="1m", path=tmp_path / "mes.csv", bars=bars)
    train, locked, start = split_holdout(bars)
    assert train[-1].ts_ns < start <= locked[0].ts_ns
    for purpose in sorted(LOCKED_PURPOSES):
        got = access_bars(tape, purpose=purpose)
        assert got == train
        assert all(item.ts_ns < start for item in got)
        access_bars(tape, purpose=f" {purpose.upper()} ")
    for purpose in sorted(EVAL_PURPOSES):
        assert access_bars(tape, purpose=purpose) == locked
    for purpose in ("eval", "oos", "train", "tune", "gate/../evaluation", "validation", "discover", "", "gаte"):
        with pytest.raises(HoldoutLocked, match="unknown"):
            access_bars(tape, purpose=purpose)
    with pytest.raises(HoldoutLocked, match="unknown"):
        assert_not_holdout(start - 1, holdout_start=start, purpose="tune")
    assert_not_holdout(start - 1, holdout_start=start, purpose="gate")
    with pytest.raises(HoldoutLocked, match="refused"):
        assert_not_holdout(start, holdout_start=start, purpose="gate")
    with pytest.raises(HoldoutLocked, match="refused"):
        assert_not_holdout(locked[-1].ts_ns, holdout_start=start, purpose="selection")
    holdout_start_ns(bars, months=HOLDOUT_MONTHS_MIN)
    holdout_start_ns(bars, months=HOLDOUT_MONTHS_MAX)
    shuffled = (bars[-1],) + bars[:-1]
    with pytest.raises(HoldoutLocked, match="strictly increasing"):
        split_holdout(shuffled)
    duplicated = bars[:10] + (bars[9],) + bars[10:]
    with pytest.raises(HoldoutLocked, match="strictly increasing"):
        split_holdout(duplicated)


@pytest.mark.unit
def test_holdout_lock_survives_csv_jsonl_binary_and_env_loader(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    bars = _calendar_bars()
    csv_dir = tmp_path / "data" / "research" / "MES" / "1m"
    csv_dir.mkdir(parents=True)
    csv_path = csv_dir / "mes.csv"
    csv_path.write_text(
        "timestamp,open,high,low,close,volume\n"
        + "\n".join(
            f"{datetime.fromtimestamp(bar.ts_ns / 1_000_000_000, tz=timezone.utc).isoformat()},"
            f"{bar.open},{bar.high},{bar.low},{bar.close},{bar.volume}"
            for bar in bars
        )
        + "\n",
        encoding="utf-8",
    )
    jsonl = tmp_path / "data" / "research" / "MNQ" / "1m" / "mnq.jsonl"
    jsonl.parent.mkdir(parents=True)
    jsonl.write_text("\n".join(_bar_json(bar) for bar in bars) + "\n", encoding="utf-8")
    blob = tmp_path / "data" / "research" / "ES.bars"
    record = struct.Struct("<q4iI")
    blob.write_bytes(b"".join(record.pack(bar.ts_ns, 20000, 20004, 19996, 20000, 1000) for bar in bars))
    monkeypatch.setenv("LUMINA_RESEARCH_DATA_DIR", str(tmp_path / "data" / "research"))
    status = discover_data(repo_root=tmp_path / "unused-root")
    by_root = {item.instrument: item for item in status.tapes}
    assert {"MES", "MNQ", "ES"} <= set(by_root)
    for tape in by_root.values():
        _train, _locked, start = split_holdout(tape.bars)
        gate = access_bars(tape, purpose="gate")
        assert all(item.ts_ns < start for item in gate)
        assert any(item.ts_ns >= start for item in tape.bars)
        with pytest.raises(HoldoutLocked, match="unknown"):
            access_bars(tape, purpose="calibration_holdout")
    monkeypatch.setenv("LUMINA_RESEARCH_DATA_DIR", str(tmp_path / "env-root"))
    missing = discover_data(repo_root=tmp_path / "no-repo-data")
    assert missing.usable is False


@pytest.mark.unit
def test_sim_safety_attacks_empty_whitelist_and_live_release() -> None:
    gate = SimSafetyGate()
    assert gate.config.sim_whitelist == frozenset()
    assert gate.config.live_release is False
    gate.admit(mode="shadow", account_id="anything")
    with pytest.raises(SimSafetyRefused, match="whitelist"):
        gate.admit(mode="sim", account_id="SIM1")
    with pytest.raises(SimSafetyRefused, match="whitelist"):
        gate.admit(mode="sim", account_id="")
    with pytest.raises(SimSafetyRefused, match="LIVE_RELEASE"):
        gate.admit(mode="live", account_id="REAL1")
    with pytest.raises(SimSafetyRefused, match="LIVE_RELEASE cannot be enabled"):
        SimSafetyConfig(live_release=True)
    with pytest.raises(SimSafetyRefused, match="LIVE_RELEASE ADR"):
        SimSafetyConfig(live_adr_path="docs/adr/9999-live.md")
    with pytest.raises(SimSafetyRefused, match="shadow mode only"):
        SimSafetyConfig(allowed_modes=frozenset({"shadow", "sim"}))
    with pytest.raises(SimSafetyRefused, match="whitelist"):
        SimSafetyConfig.from_mapping({"sim_whitelist": ["SIM1"]})
    with pytest.raises(SimSafetyRefused, match="LIVE_RELEASE cannot be enabled"):
        SimSafetyConfig.from_mapping({"live_release": True, "live_adr_path": ""})
    with pytest.raises(SimSafetyRefused, match="cannot mutate"):
        gate.set_whitelist(("SIM1",))
    with pytest.raises(SimSafetyRefused, match="cannot mutate"):
        gate.add_account("SIM1")
    with pytest.raises(SimSafetyRefused, match="LIVE_RELEASE"):
        gate.set_live_release(True)
    with pytest.raises(SimSafetyRefused, match="dedicated ADR"):
        gate.apply_live_release(review={"ok": True}, adr_path="docs/adr/x.md")


@pytest.mark.unit
def test_lumina_research_has_no_live_order_or_fabric_imports() -> None:
    hits: list[str] = []
    call_hits: list[str] = []
    for path in sorted((ROOT / "lumina_research").rglob("*.py")):
        rel = path.relative_to(ROOT).as_posix()
        source = path.read_text(encoding="utf-8")
        tree = ast.parse(source)
        for node in ast.walk(tree):
            if isinstance(node, (ast.Import, ast.ImportFrom)):
                module = _module_from_import(node)
                for banned in BANNED_IMPORTS:
                    if module == banned or module.startswith(banned + "."):
                        hits.append(f"{rel}:{node.lineno}:{module}")
            if isinstance(node, ast.Call):
                func = node.func
                name = func.attr if isinstance(func, ast.Attribute) else func.id if isinstance(func, ast.Name) else ""
                if name in ORDER_CALLS and rel not in ALLOWED_ORDER_DEF_FILES:
                    call_hits.append(f"{rel}:{node.lineno}:{name}")
    assert hits == [], "lumina_research imported a live/order surface:\n" + "\n".join(hits)
    assert call_hits == [], "lumina_research called an order/fabric method:\n" + "\n".join(call_hits)


@pytest.mark.unit
def test_twelve_templates_preregister_before_discover_data(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    specs = first_cycle_specs()
    assert len(specs) == 12
    assert tuple(item.config_id for item in specs) == FIRST_CYCLE_CONFIG_IDS
    assert "discover_data" not in Path(first_cycle_mod.__file__).read_text(encoding="utf-8")
    runner_src = Path(runner_mod.__file__).read_text(encoding="utf-8")
    assert runner_src.index("write_first_cycle_preregister") < runner_src.index("discover_data(")
    assert 'access_bars(tape, purpose="gate")' in runner_src
    order: list[str] = []

    def _pre(directory: Path) -> Path:
        order.append("preregister")
        directory.mkdir(parents=True, exist_ok=True)
        path = directory / "phase5_first_cycle_preregister.md"
        path.write_text("pre\n", encoding="utf-8")
        return path

    def _discover(**_kwargs: object) -> object:
        order.append("discover")
        return discover_data(repo_root=tmp_path)

    monkeypatch.setattr(runner_mod, "write_first_cycle_preregister", _pre)
    monkeypatch.setattr(runner_mod, "discover_data", _discover)
    result = runner_mod.run_research_cycles(
        work_dir=tmp_path / "work",
        report_dir=tmp_path / "reports",
        evolution_log_dir=tmp_path / "evo",
        repo_root=tmp_path,
    )
    assert order[:2] == ["preregister", "discover"]
    assert result.report.n_tested == 0
    assert result.report.n_hypotheses == 12


@pytest.mark.unit
def test_verify_cli_pins_holdout_seeds_not_audit_or_independent() -> None:
    source = Path(ROOT / "lumina_research" / "proof" / "cli.py").read_text(encoding="utf-8")
    assert "assert_holdout_seeds(HOLDOUT_SEEDS)" in source
    assert "seeds=HOLDOUT_SEEDS" in source
    assert "AUDIT_SEEDS" not in source


@pytest.mark.unit
def test_dd_only_decay_flags_in_normal_and_high_vol() -> None:
    cfg = load_default_config()
    mean, _stdev = oos_stats(INDEPENDENT_OOS)
    series = _dd_only_series(oos_mean=mean)
    assert _max_drawdown(series) >= MATERIAL_DD_MULT * (max(INDEPENDENT_OOS) - min(INDEPENDENT_OOS))
    normal = assess_material(series, INDEPENDENT_OOS, cfg, vol_regime="normal")
    high = assess_material(series, INDEPENDENT_OOS, cfg, vol_regime="high_vol")
    assert normal.ready is True
    assert normal.severity >= 1
    assert high.severity >= 1
    assert high.stage != "active"
    combined_high = combined_assessment(series, INDEPENDENT_OOS, cfg, vix=HIGH_VOL_VIX + 5.0)
    assert combined_high.vol_regime == "high_vol"
    assert combined_high.assessment.stage != "active"


@pytest.mark.unit
def test_ic_collapse_in_high_vol_still_detects(tmp_path: Path) -> None:
    runtime = make_runtime(tmp_path)
    admit_signal(runtime, "hyp-ic-hv", trial_id=1, oos=INDEPENDENT_OOS)
    mean, _stdev = oos_stats(INDEPENDENT_OOS)
    vix = HIGH_VOL_VIX + 5.0
    for _ in range(20):
        runtime.observe("hyp-ic-hv", mean, vix=vix)
    dropped = 0.20 * mean
    detect_day: int | None = None
    for day in range(1, 21):
        stage = runtime.observe("hyp-ic-hv", dropped, vix=vix).stage
        if detect_day is None and stage != "active":
            detect_day = day
    assert detect_day is not None
    assert detect_day <= TTD_MAX_TRADING_DAYS


@pytest.mark.unit
def test_high_vol_dd_only_decay_detection_and_ttd(tmp_path: Path) -> None:
    """Frozen floor: meaningful DD-only decay (>=1.5x) must be detected in high vol.

    Detector-only: vol-scaled / quiet crash-recover DD, never a skip. Floors stay.
    """
    mean, _stdev = oos_stats(INDEPENDENT_OOS)
    n_paths = 12
    detected = 0
    ttds: list[int] = []
    vix = HIGH_VOL_VIX + 5.0
    decay_start = 25
    for index in range(n_paths):
        runtime = make_runtime(tmp_path / f"dd-{index}")
        hyp = f"hyp-dd-only-{index}"
        admit_signal(runtime, hyp, trial_id=index + 1, oos=INDEPENDENT_OOS, instrument="MES")
        depth = 0.40 + 0.02 * float(index % 3)
        series = _dd_only_series(oos_mean=mean, decay_start=decay_start, depth=depth)
        detect_day: int | None = None
        for day, value in enumerate(series):
            stage = runtime.observe(hyp, value, vix=vix).stage
            if detect_day is None and stage != "active":
                detect_day = max(0, day - decay_start)
        if detect_day is not None:
            detected += 1
            ttds.append(detect_day)
    detection_rate = detected / float(n_paths)
    max_ttd = max(ttds) if ttds else None
    # Keep the numbers in the assertion message for the audit report.
    missed = detection_rate < DETECTION_RATE_MIN or max_ttd is None or max_ttd > TTD_MAX_TRADING_DAYS
    assert not missed, (
        f"FROZEN FLOOR MISS high_vol DD-only: detection={detection_rate:.3f} "
        f"(floor {DETECTION_RATE_MIN}) max_ttd={max_ttd} (floor {TTD_MAX_TRADING_DAYS}) "
        f"n={n_paths} detected={detected}. Do not loosen FAR/TTD/detection floors."
    )


@pytest.mark.unit
def test_phase5_change_files_are_in_the_mutant_iterator() -> None:
    assert "material.py" in PHASE5_CHANGE_FILES
    assert "vol_regime.py" in PHASE5_CHANGE_FILES
    mutants = iter_mutants(24, files=PHASE5_CHANGE_FILES)
    assert len(mutants) >= 24
    files = {item.path.split("/")[-1] for item in mutants}
    assert "material.py" in files
    assert "statistics.py" in files or "monitor.py" in files


@pytest.mark.unit
def test_frozen_far_floors_unchanged() -> None:
    assert FAR_HEALTHY_MAX == 0.05
    assert FAR_HIGH_VOL_MAX == 0.10
    assert DETECTION_RATE_MIN == 0.85
    assert TTD_MAX_TRADING_DAYS == 15

"""K1–K16 merge-gate tests for the champion/challenger ladder (ADR-0045)."""

from __future__ import annotations

import json
import time
from datetime import datetime, timedelta, timezone
from pathlib import Path

import pytest

from lumina_core.code_evolution.operators import PARAMETER_CATALOG
from lumina_core.code_evolution.proposal import CodeMutationOperator, CodeMutationProposal
from lumina_core.code_evolution.runtime_overlay import (
    effective_min_confluence,
    load_overlay,
)
from lumina_core.code_evolution.runtime_role import CHALLENGER, CHAMPION, applied_root_for_role
from lumina_core.evolution.artifacts import freeze_bundle
from lumina_core.evolution.canary import observe_canary
from lumina_core.evolution.challenger_venue.dna_namespace import register_challenger_dna
from lumina_core.evolution.challenger_venue.fills import fill_price, gap_gate, trade_pnl
from lumina_core.evolution.challenger_venue.imports_guard import scan_forbidden_imports
from lumina_core.evolution.challenger_venue.isolation import (
    ChampionHeartbeat,
    run_with_fault_boundary,
    spawn_venue_process,
    venue_crash_worker,
)
from lumina_core.evolution.challenger_venue.journal import record_and_digest, replay_digest, load_journal
from lumina_core.evolution.challenger_venue.mds_fanout import ChampionSafeFanout
from lumina_core.evolution.challenger_venue.slot import try_occupy
from lumina_core.evolution.council import compose_dossier, resolve_steve_decision
from lumina_core.evolution.council_notify import hub_visible, notify_council
from lumina_core.evolution.cutover import chaos_drill, try_swap
from lumina_core.evolution.dna_registry import DNARegistry, PolicyDNA
from lumina_core.evolution.exemption import AllowlistExemption, on_exemption_expiry
from lumina_core.evolution.invalidation import BEHAVIOR_TWEAK, POLICY_INCOMPATIBLE, classify_code_proposal
from lumina_core.evolution.schema_evolution import apply_extension, loaded_ledger_hash, overlay_schema_ok


def _write_params(root: Path, role: str, params: dict[str, float]) -> Path:
    store = Path(applied_root_for_role(root, role))
    store.mkdir(parents=True, exist_ok=True)
    clean = {k: float(v) for k, v in params.items() if k in PARAMETER_CATALOG}
    path = store / "params.json"
    path.write_text(json.dumps(clean), encoding="utf-8")
    return store


def _zip(path: Path) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(b"PK\x03\x04lumina-test-zip")
    return path


def test_k1_champion_ignores_challenger_store(tmp_path: Path) -> None:
    journal = tmp_path / "ce"
    _write_params(journal, CHALLENGER, {"confluence_threshold": 0.91})
    champ = load_overlay(journal_root=journal, role=CHAMPION)
    assert champ.active is False
    assert effective_min_confluence(0.65, champ) == pytest.approx(0.65)
    chal = load_overlay(journal_root=journal, role=CHALLENGER)
    assert chal.active is True
    assert effective_min_confluence(0.65, chal) == pytest.approx(0.91)


def test_k2_challenger_dna_does_not_touch_champion_active(tmp_path: Path) -> None:
    champ_reg = DNARegistry(
        jsonl_path=tmp_path / "champ.jsonl",
        sqlite_path=tmp_path / "champ.sqlite3",
    )
    active = PolicyDNA.create(
        prompt_id="live",
        version="active",
        content={"n": "champ"},
        fitness_score=1.0,
        generation=1,
    )
    champ_reg.register_dna(active)
    chal = PolicyDNA.create(
        prompt_id="live",
        version="active",
        content={"n": "chal"},
        fitness_score=9.0,
        generation=2,
    )
    register_challenger_dna(tmp_path, chal)
    latest = champ_reg.get_latest_dna(version="active")
    assert latest is not None
    assert latest.hash == active.hash


def test_k3_forbidden_snippet_rejected(tmp_path: Path) -> None:
    journal = tmp_path / "ce"
    store = Path(applied_root_for_role(journal, CHALLENGER))
    snip = store / "snippets"
    snip.mkdir(parents=True, exist_ok=True)
    (snip / "bad.py").write_text("def generated_strategy():\n    open('/tmp/x','w')\n", encoding="utf-8")
    snap = load_overlay(journal_root=journal, role=CHALLENGER)
    assert snap.active is False
    assert any("open" in r or "forbidden" in r for r in snap.fail_reasons)


def test_k3_supervisor_tick_has_no_in_process_exec() -> None:
    import inspect

    from lumina_core.engine import supervisor_tick_signal as mod

    src = inspect.getsource(mod)
    assert "exec(" not in src
    assert "eval(" not in src
    assert "compile(" not in src


def test_k4_venue_crash_leaves_champion_heartbeat() -> None:
    hb = ChampionHeartbeat()
    assert run_with_fault_boundary(lambda: (_ for _ in ()).throw(RuntimeError("down"))) is None
    proc = spawn_venue_process(venue_crash_worker)
    proc.join(timeout=8)
    hb.beat()
    assert hb.alive
    assert proc.exitcode != 0


def test_k5_slow_challenger_does_not_block_champion() -> None:
    fan = ChampionSafeFanout(capacity=2)
    t0 = time.perf_counter()
    for i in range(50):
        fan.publish_to_challenger({"i": i})
    elapsed = time.perf_counter() - t0
    assert elapsed < 0.5
    assert fan.dropped >= 1


def test_k6_gap_gate_blocks_fantasy_notify() -> None:
    mid, spread = 100.0, 4.0
    fan_entry = fill_price(side="BUY", mid=mid, spread=spread, fantasy=True)
    fan_exit = fill_price(side="BUY", mid=110.0, spread=spread, fantasy=True, closing=True)
    real_entry = fill_price(side="BUY", mid=mid, spread=spread, fantasy=False)
    real_exit = fill_price(side="BUY", mid=110.0, spread=spread, fantasy=False, closing=True)
    fan_pnl = trade_pnl(side="BUY", qty=1, entry=fan_entry, exit=fan_exit)
    real_pnl = trade_pnl(side="BUY", qty=1, entry=real_entry, exit=real_exit)
    assert fan_pnl > real_pnl
    gate = gap_gate(fantasy_pnl=fan_pnl, realistic_pnl=real_pnl, max_gap_ratio=0.05)
    assert gate["passed"] is False
    assert gate["notify_allowed"] is False


def test_k7_replay_digest_matches(tmp_path: Path) -> None:
    rec = {
        "intent_id": "i1",
        "side": "BUY",
        "qty": 1,
        "fill_price": 100.1,
        "pnl": 1.2,
        "overlay_id": "o",
        "dna_hash": "abc",
        "reason": "fill",
    }
    _, d1 = record_and_digest(tmp_path, rec)
    rows = load_journal(tmp_path)
    assert replay_digest(rows) == d1


def test_k8_snippet_cannot_be_behavior_tweak() -> None:
    prop = CodeMutationProposal(
        proposal_id="codevo_snip_k8",
        operator=CodeMutationOperator.STRATEGY_SNIPPET_ADJUST,
        target="sandbox.strategy_snippet",
        description="snip",
        payload={"code": "def generated_strategy():\n    return 1\n"},
        rationale="t",
        estimated_loc=2,
    )
    assert classify_code_proposal(prop) == POLICY_INCOMPATIBLE
    tweak = CodeMutationProposal(
        proposal_id="codevo_param_k8",
        operator=CodeMutationOperator.PARAMETER_TWEAK,
        target="sandbox.params",
        description="c",
        payload={"key": "confluence_threshold", "old_value": 0.65, "new_value": 0.7},
        rationale="t",
        estimated_loc=1,
    )
    assert classify_code_proposal(tweak) == BEHAVIOR_TWEAK
    lookback = CodeMutationProposal(
        proposal_id="codevo_ema_k8",
        operator=CodeMutationOperator.PARAMETER_TWEAK,
        target="sandbox.params",
        description="ema",
        payload={"key": "ema_fast_window", "old_value": 8, "new_value": 12},
        rationale="t",
        estimated_loc=1,
    )
    assert classify_code_proposal(lookback) == POLICY_INCOMPATIBLE


def test_k9_second_challenger_queued(tmp_path: Path) -> None:
    a = try_occupy(tmp_path, candidate_id="a", fitness=1.0)
    assert a["status"] == "occupied"
    b = try_occupy(tmp_path, candidate_id="b", fitness=0.5)
    assert b["status"] == "queued"
    assert b["active"] == "a"


def test_k10_missing_weights_aborts_swap(tmp_path: Path) -> None:
    incomplete = freeze_bundle(
        tmp_path,
        artifact_id="chal_incomplete",
        role=CHALLENGER,
        overlay_digest="x",
        dna_hash="dna",
        policy_zip="",
        schema_ledger="",
    )
    before = {"artifact_id": "champ"}
    # seed pointer
    from lumina_core.evolution.artifacts import write_pointer

    write_pointer(tmp_path, CHAMPION, before)
    result = try_swap(
        tmp_path,
        challenger=incomplete,
        positions=[],
        challenger_health_green=True,
    )
    assert result["swapped"] is False
    assert result["pointer"]["artifact_id"] == "champ"


def test_k11_open_position_blocks_swap(tmp_path: Path) -> None:
    z = _zip(tmp_path / "w.zip")
    chal = freeze_bundle(
        tmp_path,
        artifact_id="chal_ok",
        role=CHALLENGER,
        overlay_digest="x",
        dna_hash="dna",
        policy_zip=str(z),
        schema_ledger="",
    )
    result = try_swap(
        tmp_path,
        challenger=chal,
        positions=[{"qty": 1}],
        challenger_health_green=True,
    )
    assert result["swapped"] is False
    assert result["reason"] == "open_position"


def test_k12_chaos_drill_restore_digest(tmp_path: Path) -> None:
    z1 = _zip(tmp_path / "c.zip")
    z2 = _zip(tmp_path / "n.zip")
    champ = freeze_bundle(
        tmp_path,
        artifact_id="champ1",
        role=CHAMPION,
        overlay_digest="a",
        dna_hash="d1",
        policy_zip=str(z1),
        schema_ledger="",
    )
    chal = freeze_bundle(
        tmp_path,
        artifact_id="chal1",
        role=CHALLENGER,
        overlay_digest="b",
        dna_hash="d2",
        policy_zip=str(z2),
        schema_ledger="",
    )
    drill = chaos_drill(tmp_path, champion=champ, challenger=chal)
    assert drill["ok"] is True
    assert drill["match"] is True


def test_k13_canary_dd_restores(tmp_path: Path) -> None:
    z = _zip(tmp_path / "c.zip")
    champ = freeze_bundle(
        tmp_path,
        artifact_id="champ_canary",
        role=CHAMPION,
        overlay_digest="a",
        dna_hash="d1",
        policy_zip=str(z),
        schema_ledger="",
    )
    from lumina_core.evolution.cutover import freeze_champion

    frozen = freeze_champion(tmp_path, champ)
    out = observe_canary(
        tmp_path,
        freeze_id=frozen.artifact_id,
        trades=1,
        drawdown=0.09,
    )
    assert out["restore_invoked"] is True


def test_k14_council_veto_timeout_hub(tmp_path: Path) -> None:
    dossier = compose_dossier(
        question="cutover?",
        twin_values_ok=True,
        constitution_violations=0,
        risk_dd=0.2,
        swarm_fitness_delta=0.1,
        evolution_proof_passed=True,
    )
    assert dossier.risk_veto is True
    yes = resolve_steve_decision(dossier, ack="yes")
    assert yes["allowed"] is False
    override = resolve_steve_decision(
        dossier,
        ack="yes",
        override_risk_veto=True,
        override_reason="operator accepts",
        dual_confirm=True,
    )
    assert override["allowed"] is True
    timeout = resolve_steve_decision(dossier, ack="", timed_out=True)
    assert timeout["allowed"] is False
    notify_council(tmp_path, "real", dossier, telegram_ok=False)
    assert hub_visible(tmp_path, "real") is True


def test_k15_org_col_overlay_without_ledger(tmp_path: Path) -> None:
    journal = tmp_path / "ce"
    _write_params(journal, CHAMPION, {"confluence_threshold": 0.7})
    snap = load_overlay(
        journal_root=journal,
        role=CHAMPION,
        schema_ledger_expected="abc",
        schema_ledger_loaded="",
        requires_org_cols=True,
    )
    assert snap.active is False
    assert "schema_ledger_mismatch" in snap.fail_reasons
    blocked = apply_extension(
        tmp_path,
        proposal_id="p1",
        columns=[{"name": "org_feat", "type": "REAL"}],
        capital_mode="real",
    )
    assert blocked["ok"] is False
    ok = apply_extension(
        tmp_path,
        proposal_id="p1",
        columns=[{"name": "org_feat", "type": "REAL"}],
        capital_mode="sim",
    )
    assert ok["ok"] is True
    assert overlay_schema_ok(
        expected=ok["ledger_hash"],
        loaded=loaded_ledger_hash(tmp_path),
        requires_org_cols=True,
    )
    bad = apply_extension(
        tmp_path,
        proposal_id="p2",
        columns=[{"name": "drop_table", "type": "TEXT"}],
        capital_mode="sim",
    )
    assert bad["ok"] is False


def test_k16_exemption_expiry_holds_mid_trade() -> None:
    ex = AllowlistExemption(
        target="sandbox.params",
        expires_at=datetime.now(timezone.utc) - timedelta(seconds=1),
        reason="trial",
    )
    held = on_exemption_expiry(ex, open_challenger_position=True)
    assert held["unload"] is False
    assert held["stop_new_applies"] is True
    flat = on_exemption_expiry(ex, open_challenger_position=False)
    assert flat["unload"] is True


def test_venue_package_forbids_nt_imports() -> None:
    assert scan_forbidden_imports() == []

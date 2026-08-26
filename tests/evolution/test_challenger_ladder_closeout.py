"""Closeout tests for remaining champion/challenger ladder gaps."""

from __future__ import annotations

import json
from pathlib import Path
from types import SimpleNamespace

from lumina_core.code_evolution.runtime_overlay import (
    bind_overlay_to_engine,
    effective_min_confluence,
    load_champion_from_pointer,
)
from lumina_core.code_evolution.runtime_role import CHAMPION, CHALLENGER, applied_root_for_role
from lumina_core.evolution.artifacts import freeze_bundle, write_pointer
from lumina_core.evolution.challenger_health import evaluate_challenger_health
from lumina_core.evolution.challenger_venue.admission import admit_challenger_intent
from lumina_core.evolution.challenger_venue.proof import venue_proof
from lumina_core.evolution.challenger_venue.replay import replay_tape_digest, simulate_fills
from lumina_core.evolution.challenger_venue.runtime import VenueRuntime
from lumina_core.evolution.cutover import try_swap
from lumina_core.evolution.playground_reentry import (
    playground_reentry_may_start,
    request_playground_reentry,
)
from lumina_core.evolution.invalidation import POLICY_INCOMPATIBLE
from lumina_core.risk.admission_chain import ADMISSION_STEP_CONSTITUTION, AdmissionChain, AdmissionContext


def _zip(path: Path) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(b"PK\x03\x04lumina-test-zip")
    return path


def test_challenger_intent_rejects_skip_flags() -> None:
    blocked = admit_challenger_intent(
        {
            "side": "BUY",
            "qty": 1,
            "symbol": "MES",
            "metadata": {"skip_admission_chain_recheck": True},
        }
    )
    assert blocked["admitted"] is False
    assert "skip_flag" in blocked["reason"]
    ok = admit_challenger_intent({"side": "BUY", "qty": 1, "symbol": "MES"})
    assert ok["admitted"] is True
    assert ok["bypassed"] is False


def test_admission_forbid_bypass_even_in_sim() -> None:
    chain = AdmissionChain(steps=(ADMISSION_STEP_CONSTITUTION,))
    ctx = AdmissionContext(
        engine=SimpleNamespace(app=None),
        mode="sim",
        symbol="MES",
        regime="NEUTRAL",
        proposed_risk=1.0,
        step_handlers={ADMISSION_STEP_CONSTITUTION: lambda _c: (True, "ok")},
        experimental_bypass_step_ids=frozenset({ADMISSION_STEP_CONSTITUTION}),
        forbid_bypass=True,
    )
    allowed, reason, _trace = chain.run(ctx)
    assert allowed is False
    assert reason.startswith("experimental_bypass_forbidden:")


def test_k7_tape_replay_matches_simulated_fills() -> None:
    events = [
        {
            "quote": {"last": 100.0, "bid": 99.0, "ask": 101.0},
            "intent": {"intent_id": "a", "side": "BUY", "qty": 1},
            "overlay_id": "o",
            "dna_hash": "d",
        },
        {
            "quote": {"last": 110.0, "bid": 109.0, "ask": 111.0},
            "intent": {"intent_id": "b", "side": "SELL", "qty": 1},
            "overlay_id": "o",
            "dna_hash": "d",
        },
    ]
    d1 = replay_tape_digest(events)
    d2 = replay_tape_digest(events)
    assert d1 == d2
    assert len(simulate_fills(events)) == 2


def test_venue_runtime_admits_and_journals(tmp_path: Path) -> None:
    rt = VenueRuntime(tmp_path, overlay_id="o", dna_hash="d")
    rt.on_tick({"last": 100.0, "bid": 99.0, "ask": 101.0})
    out = rt.submit_intent({"intent_id": "i1", "side": "BUY", "qty": 1, "symbol": "MES"})
    assert out["admitted"] is True
    proof = venue_proof(tmp_path, min_days=5, min_trades=50, gap_passed=True)
    assert proof["ready"] is False
    assert proof["notify_allowed"] is False


def test_playground_reentry_never_starts_birth(tmp_path: Path) -> None:
    denied = request_playground_reentry(tmp_path, invalidation="behavior_tweak")
    assert denied["ok"] is False
    req = request_playground_reentry(tmp_path, invalidation=POLICY_INCOMPATIBLE, steve_approved=False)
    assert req["ok"] is True
    assert req["starts_birth"] is False
    ok, reason = playground_reentry_may_start(tmp_path)
    assert ok is False
    assert reason == "awaiting_steve"


def test_champion_overlay_follows_pointer_not_challenger_store(tmp_path: Path) -> None:
    journal = tmp_path / "state" / "code_evolution"
    chal_store = Path(applied_root_for_role(journal, CHALLENGER))
    chal_store.mkdir(parents=True, exist_ok=True)
    (chal_store / "params.json").write_text(json.dumps({"confluence_threshold": 0.91}), encoding="utf-8")
    engine = SimpleNamespace(runtime_role=CHAMPION, runtime_overlay=None)
    bind_overlay_to_engine(engine, workspace=tmp_path, journal_root=journal, role=CHAMPION)
    assert effective_min_confluence(0.65, engine.runtime_overlay) == 0.65
    z = _zip(tmp_path / "w.zip")
    frozen = freeze_bundle(
        tmp_path,
        artifact_id="chal_ptr",
        role=CHALLENGER,
        overlay_digest="x",
        dna_hash="dna",
        policy_zip=str(z),
        schema_ledger="",
        overlay_src=chal_store,
    )
    write_pointer(tmp_path, CHAMPION, {"artifact_id": frozen.artifact_id})
    snap = load_champion_from_pointer(tmp_path, journal_root=journal)
    assert effective_min_confluence(0.65, snap) == 0.91


def test_health_blocks_swap_when_heartbeat_dead(tmp_path: Path) -> None:
    z = _zip(tmp_path / "w.zip")
    chal = freeze_bundle(
        tmp_path,
        artifact_id="chal_h",
        role=CHALLENGER,
        overlay_digest="x",
        dna_hash="dna",
        policy_zip=str(z),
        schema_ledger="",
    )
    write_pointer(tmp_path, CHAMPION, {"artifact_id": "champ"})
    result = try_swap(
        tmp_path,
        challenger=chal,
        positions=[],
        challenger_health_green=True,
        heartbeat_alive=False,
        overlay_loaded=True,
        schema_match=True,
    )
    assert result["swapped"] is False
    assert "heartbeat" in result["reason"]
    green = evaluate_challenger_health(
        heartbeat_alive=True,
        overlay_loaded=True,
        schema_match=True,
        open_crit_violations=0,
    )
    assert green["green"] is True

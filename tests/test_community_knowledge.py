from __future__ import annotations

import json
from typing import Any

import pytest

from lumina_core.evolution.community_knowledge import append_community_queue_item, run_community_knowledge_nightly
from lumina_core.evolution.dna_registry import PolicyDNA
from lumina_core.evolution.evolution_guard import EvolutionGuard
from lumina_core.evolution.lumina_bible import LuminaBible
from lumina_core.evolution.multi_day_sim_runner import ShadowFill, SimResult


class _FakeSimRunner:
    def evaluate_variants(self, variants: list[PolicyDNA], **_: Any) -> list[SimResult]:
        v = variants[0]
        return [
            SimResult(
                dna_hash=v.hash,
                day_count=1,
                avg_pnl=50.0,
                max_drawdown_ratio=0.01,
                regime_fit_bonus=0.0,
                fitness=1.25,
                shadow_mode=True,
                hypothetical_fills=[
                    ShadowFill(1, "BUY", 1, 100.0, 101.0, 1.0, "community_shadow"),
                ],
            )
        ]


class _TwinOk:
    def evaluate_dna_promotion(self, _dna: PolicyDNA) -> dict[str, Any]:
        return {"recommendation": True, "confidence": 0.9, "risk_flags": []}


class _TwinLowConfidence:
    def evaluate_dna_promotion(self, _dna: PolicyDNA) -> dict[str, Any]:
        return {"recommendation": True, "confidence": 0.5, "risk_flags": []}


def test_append_community_queue_item_validates(monkeypatch: pytest.MonkeyPatch, tmp_path) -> None:
    q = tmp_path / "q.jsonl"

    def _cfg() -> dict[str, Any]:
        return {"queue_path": str(q)}

    monkeypatch.setattr("lumina_core.evolution.community_knowledge._community_knowledge_config", _cfg)
    assert append_community_queue_item({"hypothesis": "short"}) is False
    ok = append_community_queue_item(
        {
            "hypothesis": "A long enough hypothesis title for the gate",
            "excerpt": "Sixteen+ chars of excerpt text required here for safe external ingestion validation.",
            "source": "paper",
        },
    )
    assert ok is True
    assert q.read_text(encoding="utf-8").strip()


def test_run_community_knowledge_nightly_commits_when_vetted(monkeypatch: pytest.MonkeyPatch, tmp_path) -> None:
    queue = tmp_path / "queue.jsonl"
    proc = tmp_path / "processed.txt"
    bible_path = tmp_path / "bible.jsonl"
    line = {
        "hypothesis": "Size positions with ATR bands in chop",
        "excerpt": "Community note: scale size down when ATR percentile exceeds 80 and regime is ranging; "
        "documented edge in 2024 prop cohort backtests.",
        "source": "trader",
    }
    queue.write_text(json.dumps(line) + "\n", encoding="utf-8")

    def _cfg() -> dict[str, Any]:
        return {
            "enabled": True,
            "max_commit_per_generation": 2,
            "queue_path": str(queue),
            "processed_path": str(proc),
            "twin_confidence_min": 0.8,
        }

    monkeypatch.setattr(
        "lumina_core.evolution.community_knowledge._community_knowledge_config",
        _cfg,
    )

    bible = LuminaBible(path=bible_path)
    active = PolicyDNA.create(
        prompt_id="seed",
        version="active",
        content={"name": "seed"},
        fitness_score=1.0,
        generation=1,
        lineage_hash="L1",
    )
    out = run_community_knowledge_nightly(
        bible=bible,
        sim_runner=_FakeSimRunner(),
        approval_twin=_TwinOk(),
        guard=EvolutionGuard(),
        active_dna=active,
        base_metrics={"net_pnl": 100.0, "max_drawdown": 50.0, "sharpe": 0.4, "account_equity": 50_000.0},
        generation_offset=0,
        vector_collection=None,
    )
    assert out.get("committed") == 1
    rows = [ln for ln in bible_path.read_text(encoding="utf-8").splitlines() if ln.strip()]
    assert rows
    last = json.loads(rows[-1])
    assert last.get("entry_type") == "community_external_rule"
    assert proc.read_text(encoding="utf-8").strip()


def test_run_community_knowledge_skips_low_twin_confidence(monkeypatch: pytest.MonkeyPatch, tmp_path) -> None:
    queue = tmp_path / "queue.jsonl"
    proc = tmp_path / "processed.txt"
    bible_path = tmp_path / "bible.jsonl"
    queue.write_text(
        json.dumps(
            {
                "hypothesis": "Another long hypothesis title here",
                "excerpt": "Enough characters in excerpt body to pass validation gate for community pipeline.",
                "source": "paper",
            }
        )
        + "\n",
        encoding="utf-8",
    )

    def _cfg() -> dict[str, Any]:
        return {
            "enabled": True,
            "max_commit_per_generation": 2,
            "queue_path": str(queue),
            "processed_path": str(proc),
            "twin_confidence_min": 0.8,
        }

    monkeypatch.setattr(
        "lumina_core.evolution.community_knowledge._community_knowledge_config",
        _cfg,
    )

    bible = LuminaBible(path=bible_path)
    out = run_community_knowledge_nightly(
        bible=bible,
        sim_runner=_FakeSimRunner(),
        approval_twin=_TwinLowConfidence(),
        guard=EvolutionGuard(),
        active_dna=None,
        base_metrics={"net_pnl": 10.0, "max_drawdown": 20.0, "sharpe": 0.1, "account_equity": 50_000.0},
        generation_offset=0,
        vector_collection=None,
    )
    assert int(out.get("committed", 0) or 0) == 0
    assert not bible_path.exists() or not bible_path.read_text(encoding="utf-8").strip()

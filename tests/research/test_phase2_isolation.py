"""Research agents cannot import the live Risk Core / PromotionGate."""

from __future__ import annotations

import ast
from pathlib import Path
from typing import Literal

import pytest

from lumina_research.agents.loop import run_phase2_loop
from tests.research.phase2_harness import make_agents

ROOT = Path(__file__).resolve().parents[2]
AGENTS = ROOT / "lumina_research" / "agents"
BANNED_PREFIXES = (
    "lumina_core.risk",
    "lumina_core.evolution.promotion_gate",
    "lumina_core.evolution.promotion_evidence",
)


def _module_from_import(node: ast.AST) -> str:
    if isinstance(node, ast.ImportFrom):
        return node.module or ""
    if isinstance(node, ast.Import):
        return node.names[0].name
    return ""


@pytest.mark.unit
def test_phase2_agents_do_not_import_live_risk_or_promotion_gate() -> None:
    hits: list[str] = []
    for path in AGENTS.rglob("*.py"):
        tree = ast.parse(path.read_text(encoding="utf-8"))
        for node in ast.walk(tree):
            if not isinstance(node, (ast.Import, ast.ImportFrom)):
                continue
            module = _module_from_import(node)
            for banned in BANNED_PREFIXES:
                if module == banned or module.startswith(banned + "."):
                    rel = path.relative_to(ROOT).as_posix()
                    hits.append(f"{rel}:{node.lineno}:{module}")
    assert hits == [], "Phase 2 agents imported a live KEEP surface:\n" + "\n".join(hits)


@pytest.mark.unit
def test_equity_is_forwarded_to_validation_agent(tmp_path: Path) -> None:
    _bus, _reg, _auth, _h, validation, _p = make_agents(tmp_path, equity=50_000.0)
    assert object.__getattribute__(validation, "_equity") == 50_000.0


@pytest.mark.unit
def test_contracts_es_nq_mes_mnq_are_exercised_by_the_phase2_loop(tmp_path: Path) -> None:
    instruments: tuple[Literal["ES", "NQ", "MES", "MNQ"], ...] = ("ES", "NQ", "MES", "MNQ")
    for instrument in instruments:
        report = run_phase2_loop(
            audit_path=tmp_path / f"audit-{instrument}.jsonl",
            experiment_log_path=tmp_path / f"exp-{instrument}.jsonl",
            n_noise=2,
            n_planted=1,
            seed=21,
            instrument=instrument,
        )
        assert report.n_hypotheses == 3
        assert all(item.oos_values is not None for item in report.candidates)

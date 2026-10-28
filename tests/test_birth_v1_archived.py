"""Live tree must not import archived Birth-v1 or skip the Validation Gate."""

from __future__ import annotations

import ast
from pathlib import Path

import pytest

from lumina_core.engine.errors import LuminaError
from lumina_core.engine.meta_agent_core import SelfEvolutionMetaAgent
from lumina_core.evolution.orchestrator import EvolutionOrchestrator
from lumina_core.evolution.promotion_gate import PromotionGate, PromotionGateEvidence

ROOT = Path(__file__).resolve().parents[1]
LIVE_TREES = (
    ROOT / "lumina_core",
    ROOT / "lumina_launcher",
    ROOT / "lumina_os",
    ROOT / "lumina_research",
    ROOT / "tests",
)
ARCHIVE_MARKERS = (
    "lumina_core.birth",
    "lumina_launcher.birth",
    "lumina_os.backend.birth_endpoints",
    "lumina_core.evolution.strategy_generator",
    "lumina_core.evolution.orchestrator_core",
    "lumina_core.evolution.multi_day_sim_runner",
    "lumina_core.evolution.reality_generator",
    "lumina_core.evolution.fitness_evaluator",
    "lumina_core.evolution.meta_swarm",
    "lumina_core.maturity.playground",
    "lumina_core.maturity.awakening",
    "lumina_core.maturity.apprenticeship",
    "lumina_core.maturity.proving_ground",
    "lumina_core.maturity.phase_runners",
    "lumina_core.maturity.birth_exit",
    "lumina_core.maturity.maturity_service",
    "lumina_launcher.services.birth_service",
    "lumina_core.evolution.council",
    "lumina_core.evolution.council_notify",
)


def _module_from_import(node: ast.AST) -> str:
    if isinstance(node, ast.ImportFrom) and node.module:
        return node.module
    if isinstance(node, ast.Import):
        return ".".join(alias.name for alias in node.names)
    return ""


def _live_python_files() -> list[Path]:
    files: list[Path] = []
    for tree in LIVE_TREES:
        if not tree.is_dir():
            continue
        for path in tree.rglob("*.py"):
            if any(part in {"__pycache__", "archive"} for part in path.parts):
                continue
            files.append(path)
    return files


@pytest.mark.unit
def test_lumina_core_birth_is_not_importable() -> None:
    with pytest.raises(ImportError):
        __import__("lumina_core.birth")


@pytest.mark.unit
def test_archive_readme_states_insufficient_validation_rigor() -> None:
    text = (ROOT / "archive" / "birth-v1" / "README.md").read_text(encoding="utf-8")
    assert "Archived – insufficient validation rigor. Reuse Risk Core, Execution Fabric, Event Bus, Constitution." in text


@pytest.mark.unit
def test_live_tree_has_no_hard_imports_of_archived_birth_v1() -> None:
    hits: list[str] = []
    for path in _live_python_files():
        source = path.read_text(encoding="utf-8", errors="ignore")
        try:
            tree = ast.parse(source)
        except SyntaxError:
            continue
        for node in ast.walk(tree):
            if not isinstance(node, (ast.Import, ast.ImportFrom)):
                continue
            module = _module_from_import(node)
            if any(module == marker or module.startswith(f"{marker}.") for marker in ARCHIVE_MARKERS):
                rel = path.relative_to(ROOT).as_posix()
                hits.append(f"{rel}:{node.lineno}:{module}")
    assert hits == [], "live tree still hard-imports archived Birth-v1:\n" + "\n".join(hits)


@pytest.mark.unit
def test_nightly_evolution_and_apply_candidate_fail_closed() -> None:
    report = EvolutionOrchestrator().run_nightly_evolution_cycle()
    assert report.get("mutation_applied") is False
    assert report.get("reason") == "BIRTH_V1_ARCHIVED"
    with pytest.raises(LuminaError) as captured:
        SelfEvolutionMetaAgent._apply_candidate(None, {"name": "skip-gate"})  # type: ignore[misc]
    assert captured.value.code == "VALIDATION_GATE_REQUIRED"


@pytest.mark.unit
def test_promotion_gate_rejects_incomplete_charter_evidence(tmp_path: Path) -> None:
    gate = PromotionGate(audit_path=tmp_path / "promotion_gate_audit.jsonl")
    evidence = PromotionGateEvidence(
        dna_hash="deadbeefcafebabe",
        cv_combinatorial={"combinations": 1, "pbo": 0.9, "dsr": 0.0},
        cv_walk_forward={"windows": 1, "purged_sharpe_positive_pct": 0.1},
        reality_gap_stats={"mean_gap": 0.0, "max_gap": 0.0},
        stress_report={"max_drawdown": 0.0, "band": "GREEN"},
        live_pnl_samples=[1.0, 1.0, 1.0],
        backtest_pnl_samples=[1.0, 1.0, 1.0],
        min_sample_trades=30,
    )
    decision = gate.evaluate(evidence.dna_hash, evidence=evidence)
    assert decision.promoted is False

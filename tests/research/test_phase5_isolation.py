"""Phase 5 sources cannot import live Risk Core, PromotionGate, or archive birth-v1."""

from __future__ import annotations

import ast
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]
TARGETS = (
    ROOT / "lumina_research" / "proof",
    ROOT / "lumina_research" / "cycles",
    ROOT / "lumina_research" / "monitoring",
    ROOT / "lumina_research" / "ports",
    ROOT / "lumina_research" / "diagnostics.py",
    ROOT / "lumina_research" / "agents" / "economic_templates.py",
    ROOT / "lumina_research" / "agents" / "hypothesis.py",
    ROOT / "lumina_research" / "agents" / "synthetic.py",
    ROOT / "lumina_research" / "agents" / "validation_agent.py",
)
BANNED = (
    "lumina_core.risk",
    "lumina_core.trading_engine",
    "lumina_core.evolution.promotion_gate",
    "lumina_core.evolution.promotion_evidence",
    "lumina_core.broker",
    "archive.birth_v1",
    "archive.birth-v1",
    "grpc",
)
PLACEHOLDERS = ("TODO", "FIXME", "XXX", "NotImplemented", "pass  #")


def _module_from_import(node: ast.AST) -> str:
    if isinstance(node, ast.ImportFrom):
        return node.module or ""
    if isinstance(node, ast.Import):
        return node.names[0].name
    return ""


def _python_files() -> tuple[Path, ...]:
    files: list[Path] = []
    for target in TARGETS:
        if target.is_file():
            files.append(target)
            continue
        files.extend(sorted(target.rglob("*.py")))
    return tuple(files)


@pytest.mark.unit
def test_phase5_source_has_no_todo_or_pass_placeholders() -> None:
    hits: list[str] = []
    for path in _python_files():
        for lineno, line in enumerate(path.read_text(encoding="utf-8").splitlines(), start=1):
            stripped = line.strip()
            if stripped.startswith("#"):
                continue
            if any(token in line for token in PLACEHOLDERS):
                hits.append(f"{path.relative_to(ROOT)}:{lineno}:{stripped}")
    assert hits == [], "placeholder in Phase 5:\n" + "\n".join(hits)


@pytest.mark.unit
def test_phase5_does_not_import_live_risk_promotion_or_archive() -> None:
    hits: list[str] = []
    for path in _python_files():
        source = path.read_text(encoding="utf-8")
        assert "archive/birth-v1" not in source
        tree = ast.parse(source)
        for node in ast.walk(tree):
            if not isinstance(node, (ast.Import, ast.ImportFrom)):
                continue
            module = _module_from_import(node)
            for banned in BANNED:
                if module == banned or module.startswith(banned + "."):
                    rel = path.relative_to(ROOT).as_posix()
                    hits.append(f"{rel}:{node.lineno}:{module}")
    assert hits == [], "Phase 5 imported a forbidden surface:\n" + "\n".join(hits)


@pytest.mark.unit
def test_phase4_floors_unchanged() -> None:
    from lumina_research.monitoring.acceptance import (
        CONFIRM_WINDOWS,
        DETECTION_RATE_MIN,
        FAR_HEALTHY_MAX,
        FAR_HIGH_VOL_MAX,
        HIGH_VOL_CONFIRM_WINDOWS,
        TTD_MAX_TRADING_DAYS,
        TTD_MEDIUM_MAX_TRADING_DAYS,
        FAR_HIGH_VOL_EXTREME_NOT_A_PASS,
    )

    assert CONFIRM_WINDOWS == 2
    assert HIGH_VOL_CONFIRM_WINDOWS == 3
    assert HIGH_VOL_CONFIRM_WINDOWS <= 3
    assert FAR_HEALTHY_MAX == 0.05
    assert FAR_HIGH_VOL_MAX == 0.10
    assert DETECTION_RATE_MIN == 0.85
    assert TTD_MAX_TRADING_DAYS == 15
    assert TTD_MEDIUM_MAX_TRADING_DAYS == 45
    assert FAR_HIGH_VOL_EXTREME_NOT_A_PASS == 0.12

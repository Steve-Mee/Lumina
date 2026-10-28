"""Shared Phase 3 test helpers. Synthetic only, no network."""

from __future__ import annotations

from pathlib import Path

from lumina_core.agent_orchestration.schemas_research import SignedReview
from lumina_research.evolution.loop import EvolutionRuntime
from lumina_research.evolution.types import default_parent

REVIEW_KEY = b"phase3-human-review-key"


def write_adr(root: Path, target: str, name: str = "0057-test-protected-change.md") -> Path:
    path = root / name
    path.write_text(
        "\n".join(
            [
                "# ADR-0057: Test protected change",
                "",
                "**Status:** Proposed",
                "**Date:** 2026-10-28",
                "",
                "## Context",
                "",
                f"Changing {target} requires a human because capital preservation is sacred.",
                "",
                "## Decision",
                "",
                "Evolution records the proposal. Humans apply out of band. No auto-apply.",
                "",
                "## Consequences",
                "",
                "### Positive",
                "",
                "Audit trail of every protected proposal.",
                "",
                "### Negative",
                "",
                "Threshold changes are slower than a fitness hack.",
                "",
            ]
        ),
        encoding="utf-8",
    )
    return path


def make_runtime(tmp_path: Path, *, equity: float = 100_000.0) -> EvolutionRuntime:
    adr_root = tmp_path / "adr"
    adr_root.mkdir()
    return EvolutionRuntime(
        audit_path=tmp_path / "audit.jsonl",
        experiment_log_path=tmp_path / "experiments.jsonl",
        adr_root=adr_root,
        equity=equity,
        review_key=REVIEW_KEY,
    )


def sign_protected(
    runtime: EvolutionRuntime,
    *,
    adr_path: Path,
    config_id: str,
    kind: str,
    target: str,
    verdict: str = "approve",
    reviewer_id: str = "steve",
) -> SignedReview:
    return runtime.reviews.sign_review(
        reviewer_id=reviewer_id,
        adr_bytes=adr_path.read_bytes(),
        verdict=verdict,
        config_id=config_id,
        kind=kind,
        target=target,
    )


def dummy_genome():
    return default_parent()

"""Wave A PR4.4 — split certificate_pipeline into preflight/remediation/runway modules."""
from __future__ import annotations

from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
BIRTH = ROOT / "lumina_core" / "birth"
SRC = BIRTH / "certificate_pipeline.py"


def extract(lines: list[str], start: int, end: int) -> str:
    return "".join(lines[start - 1 : end])


def dedent_method(body: str) -> str:
    """Convert indented class method into module-level function with pipeline param."""
    out_lines: list[str] = []
    for line in body.splitlines(keepends=True):
        if line.startswith("    "):
            out_lines.append(line[4:])
        else:
            out_lines.append(line)
    text = "".join(out_lines)
    # Rewrite def name(self → def name(pipeline
    text = text.replace("def ensure_holdout_preflight(\n        self,", "def ensure_holdout_preflight(\n    pipeline,")
    text = text.replace("def run_certificate_remediation(\n        self,", "def run_certificate_remediation(\n    pipeline,")
    text = text.replace("def resolve_birth_exit_winrate(self)", "def resolve_birth_exit_winrate(pipeline)")
    text = text.replace(
        "def resolve_baseline_oos_winrate(self, *, checkpoint_state",
        "def resolve_baseline_oos_winrate(pipeline, *, checkpoint_state",
    )
    text = text.replace(
        "def bootstrap_runway_stage5(self, *, train_ticks",
        "def bootstrap_runway_stage5(pipeline, *, train_ticks",
    )
    text = text.replace(
        "def run_certificate_runway_stages(\n        self,",
        "def run_certificate_runway_stages(\n    pipeline,",
    )
    text = text.replace(
        "def fail_certificate_with_runway_checkpoint(\n        self,",
        "def fail_certificate_with_runway_checkpoint(\n    pipeline,",
    )
    # self._host → pipeline._host ; self.method → pipeline.method
    text = text.replace("self._host", "pipeline._host")
    text = text.replace("self.resolve_", "pipeline.resolve_")
    text = text.replace("self.bootstrap_", "pipeline.bootstrap_")
    text = text.replace("self.run_certificate_", "pipeline.run_certificate_")
    text = text.replace("self.fail_certificate_", "pipeline.fail_certificate_")
    text = text.replace("self.ensure_", "pipeline.ensure_")
    return text


def main() -> None:
    lines = SRC.read_text(encoding="utf-8").splitlines(keepends=True)

    # Preflight: method lines 58-261
    preflight_hdr = '''"""Holdout preflight expansion for birth certificate pipeline."""
from __future__ import annotations

from typing import Any

from lumina_core.birth.data_expansion import clamp_expansion_steps, expand_birth_data
from lumina_core.birth.history_loader import actual_calendar_days_from_ticks
from lumina_core.birth.news_enricher import enrich_ticks_with_news
from lumina_core.birth.preflight import assess_split_preflight, data_manifest_from_split
from lumina_core.birth.progress import write_birth_progress
from lumina_core.birth.remediation import manifest_train_hash_matches
from lumina_core.birth.tick_cache_persist import compute_ticks_fingerprint, save_birth_data_cache
from lumina_core.rl.trend_features import ENRICH_VERSION
from lumina_core.logging_utils import get_logger

logger = get_logger("lumina.birth.certificate_preflight")


'''
    preflight_body = dedent_method(extract(lines, 58, 261))
    (BIRTH / "certificate_preflight.py").write_text(
        preflight_hdr + preflight_body.rstrip() + "\n", encoding="utf-8"
    )

    # Remediation: 263-449
    rem_hdr = '''"""Certificate remediation loop for birth certificate pipeline."""
from __future__ import annotations

from typing import Any

from lumina_core.birth.certificate_evaluator import evaluate_holdout_certificate
from lumina_core.birth.curriculum import CurriculumStage
from lumina_core.birth.data_expansion import clamp_expansion_steps, expand_birth_data
from lumina_core.birth.news_enricher import enrich_ticks_with_news
from lumina_core.birth.progress import write_birth_progress
from lumina_core.birth.remediation import (
    RemediationAction,
    filter_train_ticks_for_holdout_profile,
    select_regime_diverse_train_ticks,
    select_remediation_plan,
)
from lumina_core.birth.sim_runner import run_policy_rollout
from lumina_core.logging_utils import get_logger

logger = get_logger("lumina.birth.certificate_remediation")


'''
    rem_body = dedent_method(extract(lines, 263, 449))
    (BIRTH / "certificate_remediation.py").write_text(
        rem_hdr + rem_body.rstrip() + "\n", encoding="utf-8"
    )

    # Runway: 451-737
    runway_hdr = '''"""Certificate runway stages + fail helpers for birth certificate pipeline."""
from __future__ import annotations

from typing import Any

from lumina_core.birth.certificate_evaluator import evaluate_holdout_certificate
from lumina_core.birth.curriculum import (
    CurriculumStage,
    filter_ticks_for_stage,
    ordered_runway_stages,
    stage_trade_target,
)
from lumina_core.birth.pattern_miner import mine_winning_patterns
from lumina_core.birth.progress import read_birth_progress, write_birth_progress
from lumina_core.birth.runway import (
    micro_oos_evolution_proof_passed,
    micro_oos_probe,
    micro_oos_sanity_passed,
    runway_stage_index,
    ticks_for_runway_stage,
)
from lumina_core.birth.stage_pass_receipt import receipt_for_stage
from lumina_core.birth.stage_scorecard import build_scorecard_payload
from lumina_core.logging_utils import get_logger

logger = get_logger("lumina.birth.certificate_runway")


'''
    runway_body = dedent_method(extract(lines, 451, 737))
    (BIRTH / "certificate_runway.py").write_text(
        runway_hdr + runway_body.rstrip() + "\n", encoding="utf-8"
    )

    # Host: keep polish + complete + thin wrappers
    polish_and_complete = extract(lines, 739, 1033)

    facade = '''"""Birth certificate preflight, runway, remediation, and completion pipeline.

Bounded modules: ``certificate_preflight``, ``certificate_remediation``,
``certificate_runway``. Host class keeps thin delegates + polish/complete.
"""
from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

from lumina_core.birth.birth_certificate import (
    build_certificate_from_eval,
    certificate_path,
    write_certificate,
)
from lumina_core.birth.buffer_persist import clear_buffer
from lumina_core.birth.checkpoint import clear_checkpoint
from lumina_core.birth.curriculum import CurriculumStage
from lumina_core.birth.certificate_evaluator import evaluate_holdout_certificate
from lumina_core.birth.dna_handoff import register_birth_gen0_dna
from lumina_core.birth.bible_meta import update_bible_after_birth
from lumina_core.birth.progress import write_birth_progress
from lumina_core.birth.runway import micro_oos_sanity_passed
from lumina_core.birth.stage_scorecard import build_scorecard_payload
from lumina_core.birth import certificate_preflight as _preflight
from lumina_core.birth import certificate_remediation as _remediation
from lumina_core.birth import certificate_runway as _runway
from lumina_core.logging_utils import get_logger

logger = get_logger("lumina.birth.certificate_pipeline")


class BirthCertificatePipeline:
    def __init__(self, host: Any) -> None:
        self._host = host

    def ensure_holdout_preflight(
        self,
        *,
        ticks: list[dict[str, Any]],
        split: Any,
        max_days: int,
        prefer_real: bool,
        start_price: float,
        training_mode: str,
        reuse_manifest: bool = False,
        saved_manifest: dict[str, Any] | None = None,
    ) -> tuple[list[dict[str, Any]], Any, dict[str, Any]] | dict[str, Any]:
        return _preflight.ensure_holdout_preflight(
            self,
            ticks=ticks,
            split=split,
            max_days=max_days,
            prefer_real=prefer_real,
            start_price=start_price,
            training_mode=training_mode,
            reuse_manifest=reuse_manifest,
            saved_manifest=saved_manifest,
        )

    def run_certificate_remediation(
        self,
        *,
        split: Any,
        eval_result: dict[str, Any],
        training_mode: str,
        ppo_steps_per_update: int,
        trade_budget_cap: int,
        prefer_real: bool,
        start_price: float,
    ) -> dict[str, Any]:
        return _remediation.run_certificate_remediation(
            self,
            split=split,
            eval_result=eval_result,
            training_mode=training_mode,
            ppo_steps_per_update=ppo_steps_per_update,
            trade_budget_cap=trade_budget_cap,
            prefer_real=prefer_real,
            start_price=start_price,
        )

    def resolve_birth_exit_winrate(self) -> float:
        return _runway.resolve_birth_exit_winrate(self)

    def resolve_baseline_oos_winrate(self, *, checkpoint_state: dict[str, Any] | None = None) -> float:
        return _runway.resolve_baseline_oos_winrate(self, checkpoint_state=checkpoint_state)

    def bootstrap_runway_stage5(self, *, train_ticks: list[dict[str, Any]]) -> None:
        return _runway.bootstrap_runway_stage5(self, train_ticks=train_ticks)

    def run_certificate_runway_stages(
        self,
        *,
        split: Any,
        validation_ticks: list[dict[str, Any]],
        train_core_ticks: list[dict[str, Any]],
        training_mode: str,
        ppo_steps_per_update: int,
        trade_budget_cap: int,
        prefer_real: bool,
        start_price: float,
        baseline_oos_winrate: float,
        birth_exit_winrate: float,
    ) -> dict[str, Any] | None:
        return _runway.run_certificate_runway_stages(
            self,
            split=split,
            validation_ticks=validation_ticks,
            train_core_ticks=train_core_ticks,
            training_mode=training_mode,
            ppo_steps_per_update=ppo_steps_per_update,
            trade_budget_cap=trade_budget_cap,
            prefer_real=prefer_real,
            start_price=start_price,
            baseline_oos_winrate=baseline_oos_winrate,
            birth_exit_winrate=birth_exit_winrate,
        )

    def fail_certificate_with_runway_checkpoint(
        self,
        *,
        eval_result: dict[str, Any],
        training_mode: str,
        trade_budget_cap: int,
    ) -> dict[str, Any]:
        return _runway.fail_certificate_with_runway_checkpoint(
            self,
            eval_result=eval_result,
            training_mode=training_mode,
            trade_budget_cap=trade_budget_cap,
        )

'''
    # Append polish/complete methods (still indented as class methods)
    facade += polish_and_complete
    SRC.write_text(facade.rstrip() + "\n", encoding="utf-8")

    print("certificate split done")
    for name in (
        "certificate_pipeline.py",
        "certificate_preflight.py",
        "certificate_remediation.py",
        "certificate_runway.py",
    ):
        n = len((BIRTH / name).read_text(encoding="utf-8").splitlines())
        print(f"  {name}: {n}")


if __name__ == "__main__":
    main()

"""Regression: local re-import of write_birth_progress caused UnboundLocalError on new birth."""

from __future__ import annotations

from types import SimpleNamespace
from unittest.mock import MagicMock, patch

from lumina_core.birth.birth_phase_train_complete import run_curriculum_and_complete
from lumina_core.birth.curriculum import CurriculumStage


def test_run_curriculum_and_complete_does_not_shadow_write_birth_progress() -> None:
    """Local `from ... import write_birth_progress` binds the name for the whole function.

    Python then raises UnboundLocalError on the first call site (before that import).
    Module-level import keeps the name free/global.
    """
    code = run_curriculum_and_complete.__code__
    assert "write_birth_progress" not in code.co_varnames
    assert "merge_birth_progress_extra" not in code.co_varnames


def test_run_curriculum_and_complete_first_progress_write_succeeds() -> None:
    """Smoke: first write_birth_progress in curriculum path must not raise UnboundLocalError."""
    host = MagicMock()
    host.workspace_root = "ws"
    host.birth_start_time = 0.0
    host.cumulative_trades = 0
    host._stages_passed = set()
    host._terminal_freeze = None
    host._active_stage_metrics = None
    host._stop_requested.return_value = False
    host.final_policy_path = MagicMock()
    host.final_policy_path.is_file.return_value = False
    host._verify_stage_pass_receipt_for_skip.return_value = False
    host._run_stage_research_loop.return_value = {
        "status": "error",
        "failure_reason": "test_short_circuit",
    }

    cfg = SimpleNamespace(
        trade_budget_cap=10_000,
        curriculum=SimpleNamespace(
            curriculum_ppo_timesteps=1000,
            polish_ppo_timesteps=1000,
            certificate_runway_enabled=False,
            certificate_runway_validation_pct=0.2,
            runway_micro_oos_max_trades=100,
        ),
        certificate_thresholds={},
    )
    boot = SimpleNamespace(
        cfg=cfg,
        training_mode="certified",
        practice_mode=False,
        prefer_real=True,
        ppo_steps_per_update=1000,
        checkpoint_state=None,
    )
    data = SimpleNamespace(
        split=SimpleNamespace(train=[object()], holdout=[], holdout_days=0),
        start_price=100.0,
    )

    with patch(
        "lumina_core.birth.birth_phase_train_complete.write_birth_progress"
    ) as write_progress:
        with patch(
            "lumina_core.birth.birth_phase_train_complete.ordered_stages",
            return_value=[CurriculumStage.STAGE1_TREND],
        ):
            with patch(
                "lumina_core.birth.foundation_stages.ticks_for_foundation_stage",
                return_value=[object()],
            ):
                with patch(
                    "lumina_core.birth.birth_phase_train_complete.purged_validation_split",
                    return_value=SimpleNamespace(validation=[]),
                ):
                    with patch(
                        "lumina_core.birth.birth_phase_train_complete.stage_trade_target",
                        return_value=100,
                    ):
                        result = run_curriculum_and_complete(
                            host,
                            boot,  # type: ignore[arg-type]
                            data,  # type: ignore[arg-type]
                        )

    assert write_progress.call_count >= 1
    first_kwargs = write_progress.call_args_list[0].kwargs
    assert first_kwargs.get("stage") == "training_running"
    assert first_kwargs.get("phase") == "curriculum_stage"
    assert result.get("status") == "error"
    assert result.get("failure_reason") == "test_short_circuit"

from __future__ import annotations

from argparse import Namespace
from unittest.mock import patch

from lumina_core.engine import runtime_entrypoint


class _FakeParser:
    def parse_known_args(self, _argv):
        args = Namespace(
            parallel_realities=None,
            set_ohlc_dna_stress=None,
            set_neuro_ohlc_rollouts=None,
            sim_only=False,
            real_safe=False,
            mode="auto",
            headless=False,
            stability_check=False,
            run_human_loop=False,
        )
        return args, []


def test_runtime_stops_after_successful_first_boot_and_waits_for_user_start() -> None:
    with patch.object(runtime_entrypoint, "_build_parser", return_value=_FakeParser()):
        with patch.object(runtime_entrypoint, "_resolve_mode", return_value="real"):
            with patch.object(runtime_entrypoint, "_first_boot_needed", return_value=True):
                with patch.object(runtime_entrypoint, "_run_first_boot_training", return_value=0):
                    with patch.object(runtime_entrypoint, "_run_real_runtime", side_effect=AssertionError("must not run")):
                        with patch.object(runtime_entrypoint, "_write_first_boot_progress") as write_progress:
                            rc = runtime_entrypoint.run_with_mode("auto", argv=[])
    assert rc == 0
    assert write_progress.called
    assert any("completed_waiting_user_action" in str(call.args) for call in write_progress.call_args_list)

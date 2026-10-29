"""Research-loop diagnostics. Flags are not Validation Gate floors."""

from __future__ import annotations

KILL_RATE_EXPECTATION = 0.90
KILL_RATE_WEAK = 0.70
KILL_RATE_STRUCTURAL_LOW = 0.80
KILL_RATE_ALL_DEAD = 0.97


def diagnose_kill_rate(
    *,
    kill_rate: float | None,
    n_hypotheses: int,
    n_survivors: int,
) -> str:
    """Flag structurally low or suspiciously total death. >90% is expected, not a gate."""
    if kill_rate is None:
        return "not_tested"
    if kill_rate < KILL_RATE_WEAK:
        return "flag_gate_too_weak_or_generator_overfit"
    if kill_rate < KILL_RATE_STRUCTURAL_LOW:
        return "flag_structurally_low"
    if kill_rate > KILL_RATE_ALL_DEAD and n_survivors == 0 and n_hypotheses >= 20:
        return "flag_all_dead_check_known_good_synthetics"
    if kill_rate > KILL_RATE_EXPECTATION:
        return "expected_high_kill"
    return "within_expectation"

"""Playground recovery — a stall is a sustained window, not a 2s poll.

Unchanged n_P between trades is not a stall. A short NT dip is not a stall.
Three sustained windows halt the clock. A healthy window clears the count.
No wipe, no expand_data, no floor cut.
"""
from __future__ import annotations

from dataclasses import dataclass

WINDOW_SEC = 30 * 60
MAX_STALL_WINDOWS = 3
OCCUPANCY_SAMPLE_BARS = 500
OCCUPANCY_CRASH_BELOW = 0.25
# Orders that never fill: crawl already waits this many bars before one edge.
FILL_STARVE_BARS = 500


@dataclass(frozen=True, slots=True)
class StallState:
    windows: int = 0
    fault: str = ""
    fault_since: float | None = None
    healthy_since: float | None = None
    hold_fault: str = ""


@dataclass(frozen=True, slots=True)
class StallStep:
    state: StallState
    event: str
    stop: bool


def active_fault(
    *,
    nt_health: str,
    occupancy: float | None,
    total_bars: int,
) -> str | None:
    """Pipeline death after a real sample. Unknown NT health is not a fault."""
    if str(nt_health or "") == "down":
        return "nt_down"
    if int(total_bars) >= OCCUPANCY_SAMPLE_BARS and occupancy is not None:
        if float(occupancy) + 1e-12 < OCCUPANCY_CRASH_BELOW:
            return "occupancy_crash"
    return None


def step_stall(
    state: StallState,
    *,
    now: float,
    active: str | None,
    unfilled_edge: bool,
    frozen: bool,
    window_sec: float = WINDOW_SEC,
    max_windows: int = MAX_STALL_WINDOWS,
) -> StallStep:
    """Advance one observation. ``frozen`` is pause or waiting-on-operator."""
    if frozen:
        return StallStep(state=state, event="", stop=state.windows >= max_windows)

    windows = int(state.windows)
    fault = str(state.fault or "")
    fault_since = state.fault_since
    healthy_since = state.healthy_since
    hold = str(state.hold_fault or "")
    event = ""

    def _count(name: str) -> None:
        nonlocal windows, hold, event
        if hold == name:
            hold = ""
            return
        windows += 1
        event = "halt" if windows >= max_windows else "window"

    if active:
        healthy_since = None
        if fault != active or fault_since is None:
            fault = active
            fault_since = float(now)
        elif float(now) - float(fault_since) >= float(window_sec):
            _count(active)
            fault_since = float(now)
    else:
        fault = ""
        fault_since = None
        if healthy_since is None:
            healthy_since = float(now)
        elif windows > 0 and float(now) - float(healthy_since) >= float(window_sec):
            windows = 0
            healthy_since = float(now)
            event = "reset"

    if unfilled_edge and event not in {"window", "halt"}:
        _count("orders_unfilled")

    stop = windows >= max_windows
    if stop and event != "reset":
        event = "halt"
    new = StallState(
        windows=windows,
        fault=fault,
        fault_since=fault_since,
        healthy_since=healthy_since,
        hold_fault=hold,
    )
    return StallStep(state=new, event=event, stop=stop)


def occupancy_crashed(occupancy: float | None, *, lo: float = OCCUPANCY_CRASH_BELOW) -> bool:
    """Bare comparison. The clock ignores this until OCCUPANCY_SAMPLE_BARS."""
    if occupancy is None:
        return False
    return float(occupancy) + 1e-12 < float(lo)


@dataclass(frozen=True, slots=True)
class ConclusiveState:
    bracket: int = 0
    asked_at: float | None = None
    continued_through: int = 0


def economic_fail(blockers: list[str] | tuple[str, ...]) -> bool:
    for item in blockers:
        text = str(item)
        if text.startswith("mean_r") or text.startswith("skill_wr") or "wr_or_be" in text:
            return True
        if text == "economic_viability":
            return True
    return False


def step_conclusive(
    state: ConclusiveState,
    *,
    now: float,
    n_p: int,
    blockers: list[str] | tuple[str, ...],
    window_sec: float = WINDOW_SEC,
    sample: int = 150,
) -> tuple[ConclusiveState, str]:
    """Ask once per 150 closes when economics still fail. Silence expires the window.

    CONTINUE is not a pass. The event is ``ask``, ``expire``, or ``"".
    """
    n = int(n_p)
    if n < int(sample) or not economic_fail(blockers):
        return state, ""
    bracket = (n // int(sample)) * int(sample)
    if int(state.continued_through) >= bracket:
        return state, ""
    if int(state.bracket) != bracket or state.asked_at is None:
        return (
            ConclusiveState(
                bracket=bracket,
                asked_at=float(now),
                continued_through=int(state.continued_through),
            ),
            "ask",
        )
    if float(now) - float(state.asked_at) >= float(window_sec):
        return state, "expire"
    return state, ""

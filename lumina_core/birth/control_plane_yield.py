"""Yield the interpreter during long Birth loops so the operator API can answer."""

from __future__ import annotations

import time

# sleep(0) releases the GIL. It does not change the tape or the exam.
_CONTROL_PLANE_YIELD_STEPS = 128


def release_control_plane(step: int) -> None:
    """Let the desktop API run during a tight Python loop.

    Birth shares this process with the operator API. A year-tape oracle scan
    or rollout otherwise stalls health and birth status, and the shell treats
    that silence as a dead Birth.
    """
    if int(step) > 0 and int(step) % _CONTROL_PLANE_YIELD_STEPS == 0:
        time.sleep(0)

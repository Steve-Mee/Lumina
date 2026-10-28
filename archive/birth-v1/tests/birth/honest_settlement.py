"""Shared honest close-reason counts and Foundation eval kwargs (ADR-0046)."""

from __future__ import annotations


def foundation_eval_kwargs(**overrides: object) -> dict[str, object]:
    """Process-R / occupancy physics for evaluate_stage_pass. Not WR floors."""
    payload: dict[str, object] = {
        "median_loss_r": 1.1,
        "mean_r": -0.05,
        "geometry_net_rr": 1.2,
        "first_touch_hit_rate": 0.28,
        "unique_calendar_days": 30,
    }
    payload.update(overrides)
    return payload


def foundation_receipt_fields(**overrides: object) -> dict[str, object]:
    """v2 receipt physics so integrity re-eval is fail-closed without WR gates."""
    payload: dict[str, object] = {
        "schema": "foundation_v2",
        "median_loss_r": 1.1,
        "mean_r": -0.05,
        "occupancy": 0.45,
        "geometry_net_rr": 1.2,
        "unique_calendar_days": 30,
    }
    payload.update(overrides)
    return payload


def honest_closes(trades: int, *, flatten_share: float = 0.0) -> dict[str, int]:
    """Split ``trades`` into stop/target vs flatten. Default is fully decisive."""
    n = max(0, int(trades))
    flat_n = int(round(n * float(flatten_share)))
    flat_n = max(0, min(n, flat_n))
    honest = n - flat_n
    tgt = int(round(honest * 0.55))
    stop = honest - tgt
    return {
        "closes_stop": stop,
        "closes_target": tgt,
        "closes_time_stop": 0,
        "closes_flatten": flat_n,
        "closes_unknown": 0,
    }

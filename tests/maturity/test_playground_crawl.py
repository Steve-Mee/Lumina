"""Playground crawl ledger — fills are not closes, R needs the stop that went out."""
from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from types import SimpleNamespace

import numpy as np
import pytest

from lumina_core.maturity.playground.crawl import (
    advance_crawl,
    observation_for_row,
    publish_live_bar,
    rebase_blind_denominator,
    resolve_crawl_submission,
)
from lumina_core.reasoning.agent_contracts import apply_agent_policy_gateway
from lumina_core.maturity.playground.fills import record_orderpath_fill, record_policy_close
from lumina_core.maturity.playground.habitat import live_occupancy
from lumina_core.maturity.playground.tape import append_tape_row, tape_skill_metrics


class _Policy:
    observation_space = SimpleNamespace(shape=(4,))

    def predict(self, obs: np.ndarray, deterministic: bool = True) -> tuple[np.ndarray, None]:
        _ = (obs, deterministic)
        step = int(getattr(self, "n", 0))
        self.n = step + 1
        side = 1.0 if step == 0 else 0.0
        return np.array([[side, 0.0, 0.01, 0.02]], dtype=np.float32), None


def _sink(root: Path) -> tuple[list[str], object]:
    calls: list[str] = []

    def place_order(
        *,
        action: str,
        qty: int,
        stop_px: float,
        target_px: float,
        instrument: str,
    ) -> dict[str, object]:
        _ = target_px
        calls.append(action)
        oid = f"SIM-{len(calls)}"
        fill_px = 100.0 if action == "BUY" else 102.0
        record_orderpath_fill(
            root,
            order_id=oid,
            fill_px=fill_px,
            qty=qty,
            instrument=instrument,
            mode="sim",
            source="ops_place_order",
            kind="fill",
            policy=True,
        )
        return {"ok": True, "order_id": oid, "fill_px": fill_px, "stop_px": stop_px}

    return calls, place_order


@pytest.mark.unit
def test_fill_is_not_a_close(tmp_path: Path) -> None:
    record_orderpath_fill(
        tmp_path,
        order_id="SIM-1",
        fill_px=100.0,
        qty=1,
        instrument="MES",
        mode="sim",
        source="orderpath",
        kind="fill",
        policy=True,
    )
    metrics = tape_skill_metrics(tmp_path)
    assert metrics["n_p"] == 0
    assert metrics["policy_only"] is True
    assert metrics["mean_r"] is None


@pytest.mark.unit
def test_plant_close_is_not_policy_only(tmp_path: Path) -> None:
    record_orderpath_fill(
        tmp_path,
        order_id="PLANT-1",
        fill_px=100.0,
        qty=1,
        instrument="MES",
        mode="sim",
        source="orderpath",
        kind="close",
        policy=False,
        r=-0.2,
        win=False,
    )
    metrics = tape_skill_metrics(tmp_path)
    assert metrics["n_plant"] == 1
    assert metrics["policy_only"] is False


@pytest.mark.unit
def test_predict_exception_places_no_order(tmp_path: Path) -> None:
    calls, place_order = _sink(tmp_path)

    class _Boom:
        observation_space = SimpleNamespace(shape=(4,))

        def predict(self, obs: np.ndarray, deterministic: bool = True) -> tuple[np.ndarray, None]:
            _ = (obs, deterministic)
            raise RuntimeError("predict down")

    publish_live_bar(
        tmp_path,
        price=100.0,
        observation=[100.0, 0.2, 0.1, 0.3],
        ts="t0",
    )
    result = advance_crawl(
        tmp_path,
        policy=_Boom(),
        place_order=place_order,  # type: ignore[arg-type]
        instrument="MES",
        mode="sim",
    )
    assert calls == []
    assert result["reason"] == "predict_failed"
    assert result["skip_counts"].get("predict_failed") == 1


@pytest.mark.unit
def test_close_without_stop_leaves_r_absent(tmp_path: Path) -> None:
    refused = record_policy_close(
        tmp_path,
        order_id="SIM-EXIT",
        entry_px=100.0,
        exit_px=101.0,
        stop_px=0.0,
        side=1,
        qty=1,
        instrument="MES",
        mode="sim",
        source="ops_place_order",
    )
    assert refused["ok"] is False
    assert refused["reason"] == "r_inputs_missing"
    assert tape_skill_metrics(tmp_path)["n_p"] == 0


@pytest.mark.unit
def test_tape_write_without_order_id_fails(tmp_path: Path) -> None:
    with pytest.raises(ValueError, match="order_id_missing"):
        append_tape_row(tmp_path, {"kind": "fill", "source": "orderpath", "fill_px": 1.0})


@pytest.mark.unit
def test_crawl_orders_only_through_place_order(tmp_path: Path) -> None:
    calls, place_order = _sink(tmp_path)
    publish_live_bar(
        tmp_path,
        price=100.0,
        observation=[100.0, 0.2, 0.1, 0.3],
        ts="2026-09-25T00:00:00Z",
    )
    publish_live_bar(
        tmp_path,
        price=102.0,
        observation=[102.0, 0.2, 0.1, 0.3],
        ts="2026-09-25T00:01:00Z",
    )
    result = advance_crawl(
        tmp_path,
        policy=_Policy(),
        place_order=place_order,  # type: ignore[arg-type]
        instrument="MES",
        mode="sim",
    )
    assert result["armed"] is True
    assert calls == []
    metrics = tape_skill_metrics(tmp_path)
    assert metrics["n_p"] == 0
    assert metrics["mean_r"] is None
    assert metrics["policy_only"] is True
    assert live_occupancy(tmp_path) is not None


@pytest.mark.unit
def test_incomplete_obs_is_not_a_policy_action(tmp_path: Path) -> None:
    calls, place_order = _sink(tmp_path)
    publish_live_bar(tmp_path, price=100.0, observation=None, ts="t0", skip="obs_incomplete")
    publish_live_bar(tmp_path, price=100.0, observation=[0.0, 0.0, 0.0, 0.0], ts="t1")
    result = advance_crawl(
        tmp_path,
        policy=_Policy(),
        place_order=place_order,  # type: ignore[arg-type]
        instrument="MES",
        mode="sim",
    )
    assert calls == []
    assert result["bars"] == 2
    assert result["total_bars"] == 0
    assert result["blind_bars"] == 2
    raw = json.loads((tmp_path / "state" / "lumina_playground_occupancy.json").read_text(encoding="utf-8"))
    assert raw["total_bars"] == 0
    assert raw["occupancy"] is None


@pytest.mark.unit
def test_unfilled_orders_open_a_stall_window(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr("lumina_core.maturity.playground.crawl.FILL_STARVE_BARS", 2)

    class _Buy:
        observation_space = SimpleNamespace(shape=(4,))

        def predict(self, obs: np.ndarray, deterministic: bool = True) -> tuple[np.ndarray, None]:
            _ = (obs, deterministic)
            return np.array([[1.0, 0.0, 0.01, 0.02]], dtype=np.float32), None

    def refuse(**_kwargs: object) -> dict[str, object]:
        return {"ok": False}

    for i in range(2):
        publish_live_bar(
            tmp_path,
            price=100.0 + i,
            observation=[100.0, 0.2, 0.1, 0.4],
            ts=f"t{i}",
        )
    result = advance_crawl(
        tmp_path,
        policy=_Buy(),
        place_order=refuse,
        instrument="MES",
        mode="sim",
    )
    assert result["orders_unfilled"] is False
    assert tape_skill_metrics(tmp_path)["n_p"] == 0


@pytest.mark.unit
def test_usable_bar_without_a_sink_stays_on_the_cursor(tmp_path: Path) -> None:
    calls, place_order = _sink(tmp_path)
    publish_live_bar(
        tmp_path,
        price=100.0,
        observation=[100.0, 0.2, 0.1, 0.3],
        ts="t0",
    )
    held = advance_crawl(
        tmp_path,
        policy=_Policy(),
        place_order=None,
        instrument="MES DEC26",
        mode="sim",
    )
    assert calls == []
    assert held["reason"] != "order_sink_missing"
    sent = advance_crawl(
        tmp_path,
        policy=_Policy(),
        place_order=place_order,  # type: ignore[arg-type]
        instrument="MES DEC26",
        mode="sim",
    )
    assert calls == []
    assert sent["total_bars"] >= 1


@pytest.mark.unit
def test_blind_denominator_correction_keeps_the_cursor(tmp_path: Path) -> None:
    state = tmp_path / "state"
    state.mkdir()
    (state / "lumina_playground_crawl.json").write_text(
        json.dumps(
            {
                "cursor": 100,
                "total_bars": 100,
                "flat_bars": 100,
                "skip_counts": {"obs_incomplete": 95},
            }
        ),
        encoding="utf-8",
    )
    assert rebase_blind_denominator(tmp_path) is True
    saved = json.loads((state / "lumina_playground_crawl.json").read_text(encoding="utf-8"))
    assert saved["cursor"] == 100
    assert saved["total_bars"] == 0
    assert saved["blind_bars"] == 100
    assert saved["sensor_denominator_corrected"] is True
    occ = json.loads((state / "lumina_playground_occupancy.json").read_text(encoding="utf-8"))
    assert occ["occupancy"] is None
    assert rebase_blind_denominator(tmp_path) is False
    book = (tmp_path / "reports" / "playground_cycle_journal" / "EXPERIMENT.md").read_text(encoding="utf-8")
    assert "sensor denominator" in book


def _lineage() -> dict[str, object]:
    return {
        "model_identifier": "unit-test-model",
        "prompt_version": "unit-v1",
        "prompt_hash": "abc123",
        "policy_version": "agent-policy-gateway-v1",
        "provider_route": ["unit-provider"],
        "calibration_factor": 1.0,
    }


@pytest.mark.unit
def test_sim_crawl_zeroes_hold_and_real_keeps_the_dream_window() -> None:
    future = datetime.now(timezone.utc).timestamp() + 3600.0
    intent = {"instrument": "MES DEC26", "stop_px": 7700.0, "target_px": 7800.0}
    sim = resolve_crawl_submission(intent, "sim")
    assert sim is not None
    assert sim["symbol"] == "MES DEC26"
    assert sim["hold_until_ts"] == 0.0
    assert resolve_crawl_submission(intent, "sim_real_guard") is not None
    assert resolve_crawl_submission(intent, "real") is None
    assert resolve_crawl_submission({"instrument": ""}, "sim") == {"reject": "chart_listing_missing"}
    blocked = apply_agent_policy_gateway(
        signal="BUY",
        confluence_score=0.9,
        min_confluence=0.2,
        hold_until_ts=future,
        mode="sim",
        session_allowed=True,
        risk_allowed=True,
        lineage=_lineage(),
    )
    assert blocked["signal"] == "HOLD"
    assert blocked["reason"] == "hold_window_active"
    opened = apply_agent_policy_gateway(
        signal="BUY",
        confluence_score=0.9,
        min_confluence=0.2,
        hold_until_ts=float(sim["hold_until_ts"]),
        mode="sim",
        session_allowed=True,
        risk_allowed=True,
        lineage=_lineage(),
    )
    assert opened["signal"] == "BUY"
    assert opened["reason"] == "accepted"


def _window(n: int = 60) -> list[dict[str, float]]:
    rows: list[dict[str, float]] = []
    for i in range(n):
        close = 100.0 + i * 0.05
        rows.append(
            {
                "open": close - 0.02,
                "high": close + 0.1,
                "low": close - 0.1,
                "close": close,
                "last": close,
                "volume": 10.0,
            }
        )
    return rows


@pytest.mark.unit
def test_short_window_and_missing_confidence_are_named_skips() -> None:
    engine = SimpleNamespace(
        get_current_dream_snapshot=lambda: {"confidence": None, "confluence_score": None},
        account_equity=100_000.0,
    )
    short, short_reason = observation_for_row(
        {"close": 100.0, "last": 100.0},
        engine=engine,
        data=[],
        idx=0,
        position=0,
        qty=0,
        entry_price=0.0,
    )
    assert short is None
    assert short_reason == "trend_window_short"
    data = _window()
    missing, missing_reason = observation_for_row(
        data[-1],
        engine=engine,
        data=data,
        idx=len(data) - 1,
        position=0,
        qty=0,
        entry_price=0.0,
    )
    assert missing is None
    assert missing_reason == "confidence_missing"
    known = SimpleNamespace(
        get_current_dream_snapshot=lambda: {
            "confidence": None,
            "confluence_score": 0.8,
            "fib_levels": {"0.382": None, "0.5": None, "0.618": None},
        },
        account_equity=100_000.0,
    )
    vector, reason = observation_for_row(
        data[-1],
        engine=known,
        data=data,
        idx=len(data) - 1,
        position=0,
        qty=0,
        entry_price=0.0,
    )
    assert reason == ""
    assert vector is not None
    assert len(vector) == 43
    assert vector[6] == pytest.approx(0.8)


@pytest.mark.unit
def test_last_bar_age_reads_the_tail_not_the_prefix(tmp_path: Path) -> None:
    from lumina_core.maturity.playground.crawl import last_bar_age_sec

    state = tmp_path / "state"
    state.mkdir()
    path = state / "lumina_playground_bars.jsonl"
    fresh = datetime.now(timezone.utc).isoformat()
    with path.open("w", encoding="utf-8") as handle:
        handle.write("x" * 80000 + "\n")
        handle.write(json.dumps({"price": 10.0, "ts": fresh}) + "\n")
    age = last_bar_age_sec(tmp_path)
    assert age is not None
    assert age < 30.0


def test_stale_backlog_is_not_a_decision(tmp_path: Path) -> None:
    from lumina_core.maturity.playground.crawl import skip_stale_backlog

    state = tmp_path / "state"
    state.mkdir()
    old = "2026-09-29T17:50:36+00:00"
    fresh = datetime.now(timezone.utc).isoformat()
    obs = [1.0, 0.2]
    rows = [
        {"price": 10.0, "ts": old, "observation": obs},
        {"price": 11.0, "ts": old, "observation": obs},
        {"price": 12.0, "ts": fresh, "observation": obs},
    ]
    (state / "lumina_playground_bars.jsonl").write_text(
        "".join(json.dumps(row) + "\n" for row in rows),
        encoding="utf-8",
    )
    (state / "lumina_playground_crawl.json").write_text(
        json.dumps({"cursor": 0, "total_bars": 4, "flat_bars": 4, "blind_bars": 0, "skip_counts": {}}),
        encoding="utf-8",
    )
    assert skip_stale_backlog(tmp_path) == 2
    raw = json.loads((state / "lumina_playground_crawl.json").read_text(encoding="utf-8"))
    assert raw["cursor"] == 2
    assert raw["total_bars"] == 4
    assert raw["skip_counts"]["stale_backlog"] == 2

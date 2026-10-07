"""Tape-A lift bonus and path-DD tax. Eval ledgers and holdout B are not involved."""

from __future__ import annotations

from pathlib import Path
from typing import Any

import numpy as np
import pytest

from lumina_core.birth.awakening_select_env import bind_parent_tape_a_wr
from lumina_core.birth.awakening_train_reward import (
    LIFT_WIN_BONUS_CAP_R,
    OCC_POTENTIAL_CAP_R,
    PATH_DD_TAX_R,
    lift_win_bonus,
    living_close_reward,
    occupancy_potential_shaping,
    path_dd_tax,
    policy_close_pnl_usd,
    policy_path_dd_pct,
)


def _close(
    process_r: float,
    *,
    closes_before: int,
    train_wr: float | None,
    parent_wr: float | None,
    plant: bool = False,
) -> float:
    return living_close_reward(
        process_r,
        plant=plant,
        occupancy=0.40,
        policy_closes_before=closes_before,
        train_sharpe_value=0.0,
        train_wr=train_wr,
        parent_wr=parent_wr,
    )


@pytest.mark.unit
def test_one_r_loss_dominates_capped_win_bonus() -> None:
    loss = _close(-1.0, closes_before=80, train_wr=0.30, parent_wr=0.34)
    win = _close(0.20, closes_before=80, train_wr=0.30, parent_wr=0.34)
    assert loss == pytest.approx(-1.0)
    assert win == pytest.approx(0.20 + LIFT_WIN_BONUS_CAP_R)
    assert abs(loss) > LIFT_WIN_BONUS_CAP_R
    assert abs(loss) > (win - 0.20)
    assert _close(1.0, closes_before=80, train_wr=0.30, parent_wr=0.34, plant=True) == 0.0


@pytest.mark.unit
def test_lift_bonus_waits_for_sample_and_turns_off_at_the_gap() -> None:
    assert (
        lift_win_bonus(
            process_r=0.4,
            policy_closes_before=49,
            train_wr=0.20,
            parent_wr=0.30,
        )
        == 0.0
    )
    assert lift_win_bonus(
        process_r=0.4,
        policy_closes_before=50,
        train_wr=0.34,
        parent_wr=0.30,
    ) == pytest.approx(LIFT_WIN_BONUS_CAP_R)
    assert (
        lift_win_bonus(
            process_r=0.4,
            policy_closes_before=50,
            train_wr=0.35,
            parent_wr=0.30,
        )
        == 0.0
    )
    assert (
        lift_win_bonus(
            process_r=0.4,
            policy_closes_before=50,
            train_wr=0.20,
            parent_wr=None,
        )
        == 0.0
    )
    assert (
        lift_win_bonus(
            process_r=-0.4,
            policy_closes_before=80,
            train_wr=0.20,
            parent_wr=0.30,
        )
        == 0.0
    )


@pytest.mark.unit
def test_path_dd_tax_starts_after_500_closes_at_20_percent() -> None:
    dd = policy_path_dd_pct([-10_000.0])
    assert dd == pytest.approx(20.0)
    assert path_dd_tax(policy_closes_before=499, dd_pct=dd) == 0.0
    assert path_dd_tax(policy_closes_before=500, dd_pct=19.9) == 0.0
    assert path_dd_tax(policy_closes_before=500, dd_pct=None) == 0.0
    assert path_dd_tax(policy_closes_before=500, dd_pct=dd) == pytest.approx(-PATH_DD_TAX_R)
    assert policy_close_pnl_usd({"risk_usd": 40.0}, -1.0) == pytest.approx(-40.0)
    assert policy_close_pnl_usd(
        {"rl_close_accounting_net_usd": -12.5},
        -1.0,
    ) == pytest.approx(-12.5)
    assert policy_close_pnl_usd({}, -1.0) is None


@pytest.mark.unit
def test_occupancy_cap_does_not_clip_path_dd_tax() -> None:
    shaped = occupancy_potential_shaping(0.50, 0.90)
    tax = path_dd_tax(policy_closes_before=500, dd_pct=21.0)
    assert abs(shaped) <= OCC_POTENTIAL_CAP_R
    assert tax == pytest.approx(-PATH_DD_TAX_R)
    assert abs(tax) > OCC_POTENTIAL_CAP_R
    assert shaped + tax <= tax + 1e-12


class _ProbeEnv:
    def __init__(self, n_bars: int) -> None:
        self.enriched = [{}] * n_bars
        self.env = type("_Inner", (), {"_idx": 0})()
        self._policy_rs: list[float] = []
        self._policy_pnl_usd: list[float] = []
        self.policy_trades = 0
        self.parent_tape_a_wr: float | None = None
        self.resets = 0
        self.steps = 0

    def reset(self) -> tuple[np.ndarray[Any, np.dtype[np.float64]], dict[str, Any]]:
        self.resets += 1
        self._policy_rs = []
        self._policy_pnl_usd = []
        return np.zeros(1), {}

    def step(self, _action: Any) -> tuple[np.ndarray[Any, np.dtype[np.float64]], float, bool, bool, dict[str, Any]]:
        self.steps += 1
        self.policy_trades += 1
        sign = 1.0 if len(self._policy_rs) % 2 == 0 else -0.5
        self._policy_rs.append(sign)
        return np.zeros(1), sign, False, False, {}


class _ProbeModel:
    def predict(self, _obs: Any, deterministic: bool = True) -> tuple[np.ndarray[Any, np.dtype[np.float64]], None]:
        del deterministic
        return np.zeros(1), None

    def learn(self, **_kwargs: Any) -> None:
        raise AssertionError("parent probe must not learn")


@pytest.mark.unit
def test_parent_probe_is_cached_and_does_not_learn(tmp_path: Path) -> None:
    parent = tmp_path / "parent.zip"
    parent.write_bytes(b"PK\x03\x04parent-a")
    env = _ProbeEnv(60)
    model = _ProbeModel()
    wr, stopped = bind_parent_tape_a_wr(
        env,
        model,
        parent_path=parent,
        reports_dir=tmp_path,
    )
    assert stopped is False
    assert wr == pytest.approx(0.5)
    assert env.parent_tape_a_wr == pytest.approx(0.5)
    assert env.policy_trades == 0
    assert env._policy_rs == []
    assert env.steps == 60
    stepped = env.steps
    wr2, stopped2 = bind_parent_tape_a_wr(
        env,
        model,
        parent_path=parent,
        reports_dir=tmp_path,
    )
    assert stopped2 is False
    assert wr2 == pytest.approx(0.5)
    assert env.steps == stepped


@pytest.mark.unit
def test_short_parent_probe_caches_unknown_wr(tmp_path: Path) -> None:
    parent = tmp_path / "parent.zip"
    parent.write_bytes(b"PK\x03\x04short")
    env = _ProbeEnv(10)
    wr, stopped = bind_parent_tape_a_wr(
        env,
        _ProbeModel(),
        parent_path=parent,
        reports_dir=tmp_path,
    )
    assert stopped is False
    assert wr is None
    assert env.steps == 10
    wr2, _stopped2 = bind_parent_tape_a_wr(
        env,
        _ProbeModel(),
        parent_path=parent,
        reports_dir=tmp_path,
    )
    assert wr2 is None
    assert env.steps == 10


@pytest.mark.unit
def test_stopped_parent_probe_is_not_cached(tmp_path: Path) -> None:
    parent = tmp_path / "parent.zip"
    parent.write_bytes(b"PK\x03\x04stop")
    env = _ProbeEnv(60)
    wr, stopped = bind_parent_tape_a_wr(
        env,
        _ProbeModel(),
        parent_path=parent,
        reports_dir=tmp_path,
        should_stop=lambda: True,
    )
    assert stopped is True
    assert wr is None
    assert env.steps == 0
    wr2, stopped2 = bind_parent_tape_a_wr(
        env,
        _ProbeModel(),
        parent_path=parent,
        reports_dir=tmp_path,
    )
    assert stopped2 is False
    assert wr2 == pytest.approx(0.5)
    assert env.steps == 60


def test_day_residual_uses_trade_r_and_refuses_an_unknown_day() -> None:
    from lumina_core.birth.awakening_train_reward import day_mean_residual, session_day_key

    assert session_day_key({"timestamp": "2026-07-23T14:31:00"}) == "2026-07-23"
    assert session_day_key({"ts_iso": "2026-07-29T00:00:00Z"}) == "2026-07-29"
    assert session_day_key({}) is None
    assert session_day_key({"timestamp": "noday"}) is None
    from lumina_core.birth.awakening_train_reward import resolve_entry_day

    row = {"timestamp": "2026-07-23T14:31:00"}
    assert resolve_entry_day(None, row, flat_before=True, opened=True) == "2026-07-23"
    assert resolve_entry_day("2026-07-22", row, flat_before=False, opened=True) == "2026-07-22"
    assert resolve_entry_day(None, {}, flat_before=True, opened=True) is None
    assert day_mean_residual(0.40, -0.20) == pytest.approx(0.60)
    assert day_mean_residual(-1.0, -0.20) == pytest.approx(-0.80)
    assert day_mean_residual(0.40, 0.0) == pytest.approx(0.40)
    assert day_mean_residual(0.40, None) is None


def test_birth_day_book_is_cached_and_does_not_learn(tmp_path: Path) -> None:
    from lumina_core.birth.awakening_select_env import bind_birth_tape_a_days

    class _DayEnv(_ProbeEnv):
        def __init__(self) -> None:
            super().__init__(4)
            self._policy_day_closes: list[tuple[str, float]] = []
            self.birth_day_means: dict[str, float] | None = None
            self.record_policy_days = False
            self._script = [
                ("2026-07-23", 1.0),
                ("2026-07-23", -0.5),
                ("2026-07-24", 0.4),
                ("2026-07-24", 0.2),
            ]

        def reset(self) -> tuple[np.ndarray[Any, np.dtype[np.float64]], dict[str, Any]]:
            obs, info = super().reset()
            self._cursor = 0
            return obs, info

        def step(self, _action: Any) -> tuple[np.ndarray[Any, np.dtype[np.float64]], float, bool, bool, dict[str, Any]]:
            obs, reward, terminated, truncated, info = super().step(_action)
            day, trade_r = self._script[self._cursor]
            self._cursor += 1
            if self.record_policy_days:
                self._policy_day_closes.append((day, trade_r))
            return obs, reward, terminated, truncated, info

    parent = tmp_path / "parent.zip"
    parent.write_bytes(b"PK\x03\x04birth-days")
    env = _DayEnv()
    means, stopped = bind_birth_tape_a_days(
        env,
        _ProbeModel(),
        parent_path=parent,
        reports_dir=tmp_path,
    )
    assert stopped is False
    assert means is not None
    assert means["2026-07-23"] == pytest.approx(0.25)
    assert means["2026-07-24"] == pytest.approx(0.30)
    assert env.birth_day_means == means
    stepped = env.steps
    means2, stopped2 = bind_birth_tape_a_days(
        env,
        _ProbeModel(),
        parent_path=parent,
        reports_dir=tmp_path,
    )
    assert stopped2 is False
    assert means2 == means
    assert env.steps == stepped


def test_birth_day_probe_stops_at_the_training_horizon(tmp_path: Path) -> None:
    from lumina_core.birth.awakening_select_env import bind_birth_tape_a_days

    class _LongEnv(_ProbeEnv):
        def __init__(self) -> None:
            super().__init__(501)
            self._policy_day_closes: list[tuple[str, float]] = []
            self.birth_day_means = None
            self.record_policy_days = False

        def step(self, _action: Any) -> tuple[np.ndarray[Any, np.dtype[np.float64]], float, bool, bool, dict[str, Any]]:
            obs, reward, terminated, truncated, info = super().step(_action)
            if self.record_policy_days:
                self._policy_day_closes.append(("2026-07-23", 0.1))
            return obs, reward, terminated, truncated, info

    parent = tmp_path / "parent.zip"
    parent.write_bytes(b"PK\x03\x04birth-long")
    env = _LongEnv()
    means, stopped = bind_birth_tape_a_days(
        env,
        _ProbeModel(),
        parent_path=parent,
        reports_dir=tmp_path,
        step_cap=40,
    )
    assert stopped is False
    assert env.steps == 40
    assert means is not None
    assert means["2026-07-23"] == pytest.approx(0.1)


def test_stopped_birth_day_probe_is_not_cached(tmp_path: Path) -> None:
    from lumina_core.birth.awakening_select_env import bind_birth_tape_a_days

    parent = tmp_path / "parent.zip"
    parent.write_bytes(b"PK\x03\x04birth-stop")
    env = _ProbeEnv(4)
    env.birth_day_means = None
    means, stopped = bind_birth_tape_a_days(
        env,
        _ProbeModel(),
        parent_path=parent,
        reports_dir=tmp_path,
        should_stop=lambda: True,
    )
    assert stopped is True
    assert means is None
    assert env.steps == 0


def test_median_win_tax_is_off_until_the_book_is_a_known_scalp() -> None:
    from lumina_core.birth.awakening_train_reward import (
        MEDIAN_WIN_COLLAPSE_TAX_R,
        median_win_collapse_tax,
    )

    small = [0.40, -1.0] * 10
    assert median_win_collapse_tax(policy_rs_before=small, parent_median_win_r=1.0) == 0.0
    assert median_win_collapse_tax(policy_rs_before=[1.0, -1.0] * 40, parent_median_win_r=None) == 0.0
    healthy = [1.0, -1.0] * 30
    assert median_win_collapse_tax(policy_rs_before=healthy, parent_median_win_r=1.0) == 0.0
    scalp = [0.40, -1.0] * 30
    assert median_win_collapse_tax(
        policy_rs_before=scalp,
        parent_median_win_r=1.018,
    ) == pytest.approx(-MEDIAN_WIN_COLLAPSE_TAX_R)

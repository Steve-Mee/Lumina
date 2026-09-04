"""MARK_EYES gym wrapper: 46-dim eyes around SelectPhysicsEnv. Does not grow sim_runner."""

from __future__ import annotations

from typing import Any

import gymnasium as gym
import numpy as np

from lumina_core.birth.awakening_mark_eyes import MARK_EYES_OBS_DIM, MarkEyesProtocolError
from lumina_core.birth.awakening_mark_eyes_obs import (
    MarkEyesState,
    concat_mark_eyes,
    unreal_r_from_rl,
)
from lumina_core.birth.awakening_path_exit_k3 import PATH_EXIT_K3_SHADOW
from lumina_core.birth.awakening_path_shape_k3_dead import PATH_SHAPE_K3_SHADOW
from lumina_core.birth.awakening_select_env import make_select_train_env


def _rl_env(inner: Any) -> Any:
    cur = inner
    env = getattr(cur, "env", None)
    if env is not None and hasattr(env, "_position"):
        return env
    return cur


class MarkEyesEnv(gym.Env):
    """Concatenates mark-path extras onto the frozen 43-dim vector."""

    metadata = {"render_modes": ["human"]}

    def __init__(self, inner: gym.Env) -> None:
        super().__init__()
        if bool(PATH_EXIT_K3_SHADOW.get()) or bool(PATH_SHAPE_K3_SHADOW.get()):
            raise MarkEyesProtocolError("hooks must stay False at MARK_EYES wrapper construct")
        self.env = inner
        self.observation_space = gym.spaces.Box(-1e6, 1e6, shape=(46,), dtype=np.float32)
        self.action_space = inner.action_space
        self.state = MarkEyesState()
        self._entry_regime = "NEUTRAL"
        self._entry_bar = 0
        self._entry_plant = False

    def _eyes(self, obs: Any) -> np.ndarray:
        rl = _rl_env(self.env)
        pos = int(getattr(rl, "_position", 0) or 0)
        u = unreal_r_from_rl(rl) if pos != 0 else None
        if pos == 0:
            self.state.on_flat()
            extra = (0.0, 0.0, 0.0)
        else:
            self.state.on_step(position=pos, unreal_r=u)
            extra = (0.0, 0.0, 0.0) if u is None else self.state.extra_vec()
        return concat_mark_eyes(obs, extra)

    def reset(self, **kwargs: Any) -> Any:
        self.state.on_flat()
        self._entry_regime = "NEUTRAL"
        self._entry_bar = 0
        self._entry_plant = False
        out = self.env.reset(**kwargs)
        if isinstance(out, tuple):
            obs, info = out
            return self._eyes(obs), info
        return self._eyes(out)

    def render(self) -> None:
        return None

    def close(self) -> None:
        close = getattr(self.env, "close", None)
        if callable(close):
            close()

    def step(self, action: Any) -> Any:
        inner = self.env
        rl = _rl_env(inner)
        plant_at_start = bool(getattr(inner, "entry_is_plant", False))
        bars_at_start = int(getattr(rl, "_bars_held", 0) or 0)
        pos_before = int(getattr(rl, "_position", 0) or 0)
        obs, reward, terminated, truncated, info = inner.step(action)
        pos_after = int(getattr(rl, "_position", 0) or 0)
        if pos_before == 0 and pos_after != 0:
            data = getattr(rl, "data", None) or []
            idx = min(int(getattr(rl, "_idx", 0) or 0), max(0, len(data) - 1))
            row = data[idx] if data else {}
            self._entry_regime = str((row or {}).get("regime") or "NEUTRAL")
            self._entry_bar = int(idx)
            self._entry_plant = bool(getattr(inner, "entry_is_plant", False))
        if bool((info or {}).get("trade_closed")):
            info = dict(info or {})
            info["entry_regime"] = self._entry_regime
            info["entry_bar_index"] = self._entry_bar
            info["bars_held"] = bars_at_start
            info["plant_entry"] = bool(plant_at_start)
            info["plant"] = bool(plant_at_start)
            info["force_open"] = bool(plant_at_start)
            info["pnl"] = info.get("rl_close_accounting_net_usd", info.get("pnl"))
        obs46 = self._eyes(obs)
        if tuple(obs46.shape) != (MARK_EYES_OBS_DIM,):
            raise MarkEyesProtocolError("wrapper obs must be shape (46,)")
        return obs46, reward, terminated, truncated, info


def make_mark_eyes_train_env(
    data: list[dict[str, Any]],
    *,
    workspace_root: Any,
    reports_dir: Any,
    max_steps: int,
    tax_r: float = 0.0,
    train_reward_fn: Any | None = None,
) -> MarkEyesEnv:
    if abs(float(tax_r)) > 0.0 or train_reward_fn is not None:
        raise MarkEyesProtocolError("MARK_EYES is not hole-tax; tax_r must stay 0.0")
    inner = make_select_train_env(
        data,
        workspace_root=workspace_root,
        reports_dir=reports_dir,
        max_steps=int(max_steps),
        tax_r=0.0,
        train_reward_fn=None,
    )
    return MarkEyesEnv(inner)


def make_mark_eyes_eval_env(
    data: list[dict[str, Any]],
    *,
    workspace_root: Any,
    reports_dir: Any,
    max_steps: int,
) -> MarkEyesEnv:
    return make_mark_eyes_train_env(
        data,
        workspace_root=workspace_root,
        reports_dir=reports_dir,
        max_steps=int(max_steps),
        tax_r=0.0,
        train_reward_fn=None,
    )


__all__ = ["MarkEyesEnv", "make_mark_eyes_eval_env", "make_mark_eyes_train_env"]

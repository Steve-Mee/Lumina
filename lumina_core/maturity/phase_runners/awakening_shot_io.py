"""Default train/eval for the live Awakening shot. Holdout never enters learn()."""
from __future__ import annotations

from pathlib import Path
from types import SimpleNamespace
from typing import Any

def default_train(
    *,
    train: list[dict[str, Any]],
    holdout: list[dict[str, Any]],
    init_path: Path,
    child_path: Path,
    workspace: Path,
    reports: Path,
    pin: int,
    lr_scale: float = 1.0,
) -> dict[str, Any]:
    del holdout
    from lumina_core.maturity.phase_runners.awakening_shot import AwakeningShotError
    from lumina_core.birth.awakening_select_env import make_select_train_env
    from lumina_core.rl.ppo_device import _resolve_ppo_device
    from lumina_core.rl.ppo_trainer import PPOTrainer

    env = make_select_train_env(
        list(train),
        workspace_root=workspace,
        reports_dir=reports,
        max_steps=max(int(pin), len(train)),
    )
    device = _resolve_ppo_device()
    try:
        from stable_baselines3 import PPO
    except Exception as exc:
        raise AwakeningShotError(f"ppo_import_failed: {exc}") from exc
    try:
        model = PPO.load(str(init_path), env=env, device=device)
    except Exception as exc:
        raise AwakeningShotError(f"ppo_load_failed: {exc}") from exc
    _heartbeat(workspace, activity="train_A", train_timesteps=0)
    scale = float(lr_scale)
    if abs(scale - 1.0) > 1e-12:
        try:
            model.learning_rate = float(model.learning_rate) * scale
        except (TypeError, ValueError):
            pass
    cap = _timestep_cap_callback(int(pin), workspace=workspace)
    try:
        model.learn(
            total_timesteps=int(pin),
            reset_num_timesteps=False,
            callback=cap,
            progress_bar=False,
        )
    except Exception as exc:
        raise AwakeningShotError(f"learn_failed: {exc}") from exc
    actual = int(getattr(cap, "ran", 0) or 0) if cap is not None else int(pin)
    if actual > int(pin):
        raise AwakeningShotError(f"trainer ran {actual} steps > pin {pin}")
    engine = SimpleNamespace(rl_policy_model=model)
    trainer = PPOTrainer(engine=engine, model_dir=reports)
    trainer.save_weights(str(child_path))
    return {
        "actual_timesteps": actual,
        "optimizer_steps": int(getattr(model, "_n_updates", 0) or 0),
        "device": device,
    }


def default_eval(
    *,
    holdout: list[dict[str, Any]],
    child_path: Path,
    workspace: Path,
    reports: Path,
    ledger_path: Path,
) -> dict[str, Any]:
    from lumina_core.maturity.phase_runners.awakening_shot import AwakeningShotError
    from lumina_core.birth.awakening_grind_run import run_evaluate_only
    from lumina_core.birth.awakening_select_env import select_runtime
    from lumina_core.birth.birth_exit_policy_export import is_gitignored_ppo_zip

    if is_gitignored_ppo_zip(child_path):
        raise AwakeningShotError("eval_refused_gitignored_ppo")
    _heartbeat(workspace, activity="eval_B", train_timesteps=None)
    metrics = run_evaluate_only(
        runtime=select_runtime(),
        holdout=list(holdout),
        workspace_root=workspace,
        reports_dir=reports,
        ledger_path=ledger_path,
        policy_path=child_path,
    )
    n_all = int(metrics.n or 0)
    policy_n = int(metrics.policy_trades or 0)
    skill = _policy_skill_from_ledger(ledger_path)
    if skill["policy_trades"] > 0:
        policy_n = int(skill["policy_trades"])
        n_all = int(skill["n_all"])
    _, seed_source = _occupancy_seed_source(workspace, reports)
    return {
        "oos_winrate": float(skill["wr"] if skill["policy_trades"] > 0 else metrics.wr),
        "holdout_trades": policy_n,
        "n_all": n_all,
        "policy_trades": policy_n,
        "policy_only": bool(skill["policy_only"]),
        "oos_sharpe": skill["sharpe"] if skill["policy_trades"] > 0 else metrics.oos_sharpe,
        "oos_dd_pct": skill["dd_pct"] if skill["policy_trades"] > 0 else metrics.oos_dd_pct,
        "occupancy": metrics.occupancy,
        "mean_r": skill["mean_r"] if skill["policy_trades"] > 0 else metrics.mean_r,
        "median_loss_r": skill["median_loss_r"],
        "edge": metrics.edge,
        "holdout_exhausted": bool(metrics.holdout_exhausted),
        "occupancy_seed_source": seed_source,
        "n_plant": int(skill["n_plant"]),
    }


def _occupancy_seed_source(workspace: Path, reports: Path) -> tuple[float | None, str]:
    from lumina_core.birth.awakening_grind_run import resolve_awakening_occupancy_seed

    return resolve_awakening_occupancy_seed(reports, workspace)


def _policy_skill_from_ledger(path: Path) -> dict[str, Any]:
    """Skill metrics from policy closes only. Plant airframe is occupancy, not skill."""
    empty: dict[str, Any] = {
        "policy_only": False,
        "policy_trades": 0,
        "n_all": 0,
        "n_plant": 0,
        "wr": 0.0,
        "sharpe": None,
        "dd_pct": None,
        "mean_r": None,
        "median_loss_r": None,
    }
    if not path.is_file():
        return empty
    import json

    from lumina_core.birth.foundation_metrics import mean_r, median_loss_r
    from lumina_core.birth.runway import risk_metrics_from_pnl

    rows: list[dict[str, Any]] = []
    try:
        for line in path.read_text(encoding="utf-8").splitlines():
            raw = line.strip()
            if not raw:
                continue
            row = json.loads(raw)
            if isinstance(row, dict):
                rows.append(row)
    except (OSError, ValueError, TypeError):
        return empty
    n_all = len(rows)
    plant = [r for r in rows if _is_plant_row(r)]
    policy = [r for r in rows if not _is_plant_row(r)]
    pnl = [_float_row(r, "pnl") for r in policy if r.get("pnl") is not None]
    rs = [_float_row(r, "trade_r") for r in policy if r.get("trade_r") is not None]
    n_pol = len(policy)
    wins = sum(1 for x in pnl if x > 0.0)
    sharpe, dd = (None, None)
    if pnl:
        s, d = risk_metrics_from_pnl(pnl)
        sharpe, dd = float(s), float(d)
    return {
        "policy_only": n_pol > 0,
        "policy_trades": n_pol,
        "n_all": n_all,
        "n_plant": len(plant),
        "wr": (float(wins) / float(len(pnl))) if pnl else 0.0,
        "sharpe": sharpe,
        "dd_pct": dd,
        "mean_r": mean_r(rs) if rs else None,
        "median_loss_r": median_loss_r(rs) if rs else None,
    }


def _is_plant_row(row: dict[str, Any]) -> bool:
    if bool(row.get("plant")):
        return True
    return str(row.get("skill_grade") or "").strip().lower() == "plant"


def _float_row(row: dict[str, Any], key: str) -> float:
    try:
        return float(row.get(key) or 0.0)
    except (TypeError, ValueError):
        return 0.0


def _heartbeat(
    workspace: Path,
    *,
    activity: str,
    train_timesteps: int | None,
) -> None:
    try:
        from lumina_core.maturity.awakening.progress import merge_awakening_progress

        patch: dict[str, Any] = {"activity": activity}
        if train_timesteps is not None:
            patch["train_timesteps"] = int(train_timesteps)
        merge_awakening_progress(workspace, patch)
    except Exception:
        return


def _timestep_cap_callback(cap: int, *, workspace: Path) -> Any:
    try:
        from stable_baselines3.common.callbacks import BaseCallback
    except Exception:
        return None

    class _Cap(BaseCallback):  # type: ignore[misc,valid-type]
        def __init__(self, max_steps: int) -> None:
            super().__init__()
            self.max_steps = int(max_steps)
            self._last_beat = -1
            self.ran = 0

        def _on_step(self) -> bool:
            self.ran += 1
            if self.ran == 1 or (self.ran - self._last_beat) >= 1024:
                self._last_beat = self.ran
                _heartbeat(workspace, activity="train_A", train_timesteps=self.ran)
            return self.ran < self.max_steps

    return _Cap(cap)

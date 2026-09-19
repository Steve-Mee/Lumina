"""Live-plant Awakening shot — one PPO continuation on Birth train, eval on holdout.

Does not mutate Birth receipts, fitness, completed flag, or birth_exit_pi_star.
ADR-0026 floors unchanged. Missing artefacts fail-closed. No synthetic fixture.
"""
from __future__ import annotations

import json
from collections.abc import Callable
from pathlib import Path
from typing import Any

from lumina_core.logging_utils import get_logger

logger = get_logger("lumina.maturity.runners.awakening_shot")

HOLD_PCT = 0.20
CHILD_ZIP_NAME = "awakening_live_pi_star.zip"
CHILD_META_NAME = "awakening_live_pi_star.json"
LEDGER_NAME = "awakening_live_holdout.jsonl"
CHILD_SCHEMA = "awakening_live_pi_star_v1"

FROZEN_RELATIVE: tuple[str, ...] = (
    "state/lumina_birth_foundation_receipts.json",
    "state/lumina_birth_fitness_vector.json",
    "state/lumina_birth_completed.flag",
    "state/lumina_birth_progress.json",
)

ProgressFn = Callable[[float, str], None]
TrainFn = Callable[..., dict[str, Any]]
EvalFn = Callable[..., dict[str, Any]]
SplitLoader = Callable[
    [Path], tuple[list[dict[str, Any]], list[dict[str, Any]], dict[str, Any]]
]


class AwakeningShotError(RuntimeError):
    """Fail-closed live shot (missing freeze artefacts, split, or train/eval)."""


def artifacts_dir(workspace_root: Path) -> Path:
    from lumina_core.birth.birth_exit_policy_export import resolve_pi_star_path

    return resolve_pi_star_path(workspace_root).parent


def live_child_zip(workspace_root: Path) -> Path:
    return artifacts_dir(workspace_root) / CHILD_ZIP_NAME


def live_ledger_path(workspace_root: Path) -> Path:
    return artifacts_dir(workspace_root) / LEDGER_NAME


def snapshot_birth_freeze(workspace_root: Path | str) -> dict[str, str]:
    """Sha256 of Birth-exit artefacts. Missing files record as empty."""
    from lumina_core.birth.birth_exit_policy_export import file_sha256, resolve_pi_star_path

    root = Path(workspace_root)
    out: dict[str, str] = {}
    for rel in FROZEN_RELATIVE:
        path = root / rel
        out[rel] = file_sha256(path) if path.is_file() else ""
    from lumina_core.maturity.awakening.freeze_pin import (
        freeze_rel_key,
        pin_birth_pi_star,
        remember_fingerprint_sha,
    )
    from lumina_core.maturity.awakening.progress import load_awakening_progress

    remember_fingerprint_sha(root, load_awakening_progress(root).get("freeze_fingerprint"))
    pi_star = resolve_pi_star_path(root)
    try:
        pin_birth_pi_star(root)
    except FileNotFoundError:
        pass
    out[freeze_rel_key(root, pi_star)] = file_sha256(pi_star) if pi_star.is_file() else ""
    meta = pi_star.with_name("birth_exit_pi_star.json")
    out[freeze_rel_key(root, meta)] = file_sha256(meta) if meta.is_file() else ""
    data = _continuum_birth_slice(root)
    out["continuum.birth_completed"] = "1" if data["birth_completed"] else "0"
    out["continuum.birth_record"] = _stable_json(data["birth_record"])
    return out


def assert_birth_freeze(workspace_root: Path | str, before: dict[str, str]) -> None:
    from lumina_core.maturity.awakening.freeze_pin import restore_birth_pi_star_from_pin

    root = Path(workspace_root)
    after = snapshot_birth_freeze(root)
    if after == before:
        return
    restore_birth_pi_star_from_pin(root)
    after = snapshot_birth_freeze(root)
    if after != before:
        delta = sorted(k for k in set(before) | set(after) if before.get(k) != after.get(k))
        raise AwakeningShotError(f"birth_freeze_violated: {delta}")


def load_live_split(workspace_root: Path) -> tuple[list[dict[str, Any]], list[dict[str, Any]], dict[str, Any]]:
    from lumina_core.birth.tick_cache_persist import (
        compute_ticks_fingerprint,
        load_split_cache,
        split_cache_path,
    )

    path = split_cache_path(workspace_root)
    if not path.is_file():
        raise AwakeningShotError("birth_split_cache_missing")
    raw = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(raw, dict):
        raise AwakeningShotError("birth_split_cache_invalid")
    hold_pct = float(raw.get("holdout_pct") or HOLD_PCT)
    split = load_split_cache(workspace_root, holdout_pct=hold_pct)
    if split is None or not split.train or not split.holdout:
        raise AwakeningShotError("birth_split_load_failed")
    expected_fp = str(raw.get("ticks_fingerprint") or "")
    from lumina_core.birth.tick_cache_persist import load_ticks_cache

    cache_fp = compute_ticks_fingerprint(load_ticks_cache(workspace_root))
    if expected_fp and cache_fp and expected_fp != cache_fp:
        raise AwakeningShotError(
            f"ticks_fingerprint_mismatch {cache_fp} != {expected_fp}"
        )
    if not split.train or not split.holdout:
        raise AwakeningShotError("birth_split_empty")
    meta = {
        "holdout_pct": hold_pct,
        "train_n": len(split.train),
        "holdout_n": len(split.holdout),
        "ticks_fingerprint": expected_fp,
    }
    return list(split.train), list(split.holdout), meta


def run_live_awakening_shot(
    workspace_root: Path | str,
    *,
    progress: ProgressFn | None = None,
    train_fn: TrainFn | None = None,
    eval_fn: EvalFn | None = None,
    split_loader: SplitLoader | None = None,
    init_path: Path | None = None,
    eval_only: bool = False,
    lr_scale: float = 1.0,
    cycle: int = 0,
) -> dict[str, Any]:
    """Train on Birth train split, eval holdout, persist ADR-0026 record (pass or fail)."""
    root = Path(workspace_root)
    freeze = snapshot_birth_freeze(root)
    try:
        result = _run_shot_body(
            root,
            progress=progress,
            train_fn=train_fn,
            eval_fn=eval_fn,
            split_loader=split_loader,
            init_path=init_path,
            eval_only=eval_only,
            lr_scale=lr_scale,
            cycle=cycle,
        )
    except Exception:
        assert_birth_freeze(root, freeze)
        raise
    assert_birth_freeze(root, freeze)
    return result


def _run_shot_body(
    root: Path,
    *,
    progress: ProgressFn | None,
    train_fn: TrainFn | None,
    eval_fn: EvalFn | None,
    split_loader: SplitLoader | None,
    init_path: Path | None = None,
    eval_only: bool = False,
    lr_scale: float = 1.0,
    cycle: int = 0,
) -> dict[str, Any]:
    from lumina_core.birth.awakening_select import AWAKENING_SELECT_PPO_TIMESTEPS
    from lumina_core.birth.birth_exit_policy_export import (
        file_sha256,
        is_gitignored_ppo_zip,
        resolve_pi_star_path,
    )
    from lumina_core.birth.evolution_proof_gate import record_and_evaluate_at_certificate
    from lumina_core.birth.fitness_vector import load_fitness_vector

    _emit(progress, 18.0, "Loading frozen π* + Birth split")
    vector = load_fitness_vector(root)
    if vector is None:
        raise AwakeningShotError("fitness_vector_missing")
    frozen_path = resolve_pi_star_path(root)
    if is_gitignored_ppo_zip(frozen_path):
        raise AwakeningShotError("init_is_gitignored_ppo")
    if not frozen_path.is_file() or frozen_path.stat().st_size <= 0:
        raise AwakeningShotError(f"birth_exit_pi_star_missing path={frozen_path}")
    frozen_sha = file_sha256(frozen_path)
    from lumina_core.maturity.awakening.freeze_pin import (
        expected_zip_sha_from_fingerprint,
        remember_fingerprint_sha,
        restore_birth_pi_star_from_pin,
    )
    from lumina_core.maturity.awakening.progress import load_awakening_progress

    fp = load_awakening_progress(root).get("freeze_fingerprint")
    remember_fingerprint_sha(root, fp if isinstance(fp, dict) else None)
    expected = expected_zip_sha_from_fingerprint(fp if isinstance(fp, dict) else None)
    pin_sha_path = root / "state" / "lumina_birth_freeze" / "sha256.txt"
    if expected is None and pin_sha_path.is_file():
        text = pin_sha_path.read_text(encoding="utf-8").strip()
        expected = text if len(text) == 64 else None
    if expected and frozen_sha != expected:
        restore_birth_pi_star_from_pin(root)
        frozen_sha = file_sha256(frozen_path) if frozen_path.is_file() else ""
        if frozen_sha != expected:
            raise AwakeningShotError(
                f"birth_pi_star_sha_mismatch expected={expected[:16]} got={frozen_sha[:16]} "
                "canonical Birth zip was overwritten; restore birth_exit_pi_star.zip "
                "matching the freeze fingerprint (not the Sep-3 harvest)"
            )
    load_path = Path(init_path) if init_path is not None else frozen_path
    if is_gitignored_ppo_zip(load_path):
        raise AwakeningShotError("init_is_gitignored_ppo")
    if not load_path.is_file() or load_path.stat().st_size <= 0:
        raise AwakeningShotError(f"init_policy_missing path={load_path}")
    init_sha = frozen_sha

    if split_loader is not None:
        train, holdout, split_meta = split_loader(root)
    else:
        train, holdout, split_meta = load_live_split(root)
    if not train or not holdout:
        raise AwakeningShotError("live_split_empty")
    if train is holdout:
        raise AwakeningShotError("train_is_holdout_same_object")

    child = live_child_zip(root)
    ledger = live_ledger_path(root)
    reports = artifacts_dir(root)
    reports.mkdir(parents=True, exist_ok=True)
    pin = int(AWAKENING_SELECT_PPO_TIMESTEPS)
    from lumina_core.maturity.phase_runners.awakening_shot_io import default_eval, default_train

    train_info: dict[str, Any] = {"actual_timesteps": 0, "optimizer_steps": 0}
    if eval_only:
        _emit(progress, 40.0, f"Cycle {int(cycle)} eval frozen π* on holdout B — no learn()")
        from lumina_core.maturity.awakening.freeze_pin import refuse_birth_pi_star_write

        refuse_birth_pi_star_write(child)
        if load_path.resolve() != child.resolve():
            child.write_bytes(load_path.read_bytes())
    else:
        _emit(progress, 40.0, f"Cycle {int(cycle)} train A (10k PPO)")
        trainer = train_fn or default_train
        train_info = trainer(
            train=train,
            holdout=holdout,
            init_path=load_path,
            child_path=child,
            workspace=root,
            reports=reports,
            pin=pin,
            lr_scale=float(lr_scale),
        )
    if not child.is_file() or child.stat().st_size <= 0:
        raise AwakeningShotError("child_zip_missing_after_train")
    child_sha = file_sha256(child)
    if child_sha == init_sha:
        logger.warning("awakening.live.child_sha_equals_init — eval still runs; ADR-0026 decides")

    _emit(progress, 70.0, f"Cycle {int(cycle)} eval holdout B")
    evaluator = eval_fn or default_eval
    eval_info = evaluator(
        holdout=holdout,
        child_path=child,
        workspace=root,
        reports=reports,
        ledger_path=ledger,
    )
    oos = float(eval_info["oos_winrate"])
    n_trades = int(eval_info["holdout_trades"])
    proof = record_and_evaluate_at_certificate(
        root,
        eval_result={"oos_winrate": oos, "holdout_trades": n_trades},
        birth_exit_winrate=float(vector.oos_wr),
    )
    sidecar = {
        "schema": CHILD_SCHEMA,
        "path": str(child),
        "sha256": child_sha,
        "init_sha256": init_sha,
        "actual_timesteps": int(train_info.get("actual_timesteps") or 0),
        "split": split_meta,
        "oos_winrate": oos,
        "holdout_trades": n_trades,
        "birth_exit_winrate": float(vector.oos_wr),
        "passed": bool(proof.passed),
        "reasons": list(proof.reasons),
    }
    (reports / CHILD_META_NAME).write_text(
        json.dumps(sidecar, indent=2) + "\n", encoding="utf-8"
    )
    _emit(progress, 85.0, "ADR-0026 evolution proof recorded")
    return {
        "ok": bool(proof.passed),
        "passed": bool(proof.passed),
        "reasons": list(proof.reasons),
        "birth_exit_winrate": float(vector.oos_wr),
        "polish_oos_winrate": oos,
        "holdout_trades": n_trades,
        "winrate_lift": proof.winrate_lift,
        "child_path": str(child),
        "child_sha256": child_sha,
        "init_sha256": init_sha,
        "split": split_meta,
        "train_n": len(train),
        "holdout_n": len(holdout),
        "policy_trades": int(eval_info.get("policy_trades") or 0),
        "n_all": int(eval_info.get("n_all") or 0),
        "policy_only": eval_info.get("policy_only") is True,
        "oos_sharpe": eval_info.get("oos_sharpe"),
        "oos_dd_pct": eval_info.get("oos_dd_pct"),
        "occupancy": eval_info.get("occupancy"),
        "mean_r": eval_info.get("mean_r"),
        "edge": eval_info.get("edge"),
        "median_loss_r": eval_info.get("median_loss_r"),
        "holdout_exhausted": bool(eval_info.get("holdout_exhausted")),
        "occupancy_seed_source": eval_info.get("occupancy_seed_source") or "",
        "n_plant": int(eval_info.get("n_plant") or 0),
        "eval_only": bool(eval_only),
        "lr_scale": float(lr_scale),
    }


def _emit(progress: ProgressFn | None, pct: float, message: str) -> None:
    if progress is not None:
        progress(pct, message)


def _continuum_birth_slice(root: Path) -> dict[str, Any]:
    try:
        from lumina_core.maturity.continuum import load_continuum

        data = load_continuum(root)
    except Exception:
        return {"birth_completed": False, "birth_record": None}
    completed = list(data.get("completed_phases") or [])
    rec = (data.get("phase_records") or {}).get("birth")
    return {"birth_completed": "birth" in completed, "birth_record": rec}


def _stable_json(value: Any) -> str:
    try:
        return json.dumps(value, sort_keys=True, default=str)
    except TypeError:
        return str(value)


__all__ = [
    "AwakeningShotError",
    "CHILD_ZIP_NAME",
    "FROZEN_RELATIVE",
    "assert_birth_freeze",
    "live_child_zip",
    "live_ledger_path",
    "load_live_split",
    "run_live_awakening_shot",
    "snapshot_birth_freeze",
]

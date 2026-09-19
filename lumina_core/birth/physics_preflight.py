"""Fail-closed Birth physics probe (torch + SB3) for the live interpreter.

Birth must not claim "started" and must not load Fabric/history until this
interpreter can import the training engine. Missing SB3 is not retryable
theatre: install the physics stack, then Reuse data. Never WIPE_FULL.
"""

from __future__ import annotations

import importlib
import os
import sys
import time
from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from lumina_core.birth.physics_stack_install import _has_nvidia
from lumina_core.birth.progress import write_birth_progress
from lumina_core.logging_utils import get_logger

logger = get_logger("lumina.birth.physics_preflight")

PHYSICS_READY = "physics_ready"
PHYSICS_UNAVAILABLE = "physics_unavailable"
CUDA_REQUIRED = "cuda_required"
INSTALL_HINT = "python scripts/install_birth_physics_stack.py"
CPU_PPO_ENV = "LUMINA_ALLOW_CPU_PPO"

_Importer = Callable[[str], Any]


def _cpu_ppo_allowed(explicit: bool | None) -> bool:
    if explicit is not None:
        return bool(explicit)
    raw = str(os.getenv(CPU_PPO_ENV, "") or "").strip().lower()
    return raw in {"1", "true", "yes", "on"}


def physics_missing_message(*, missing: tuple[str, ...]) -> str:
    pkgs = ", ".join(missing) if missing else "torch/stable_baselines3"
    return (
        f"Leermotor ontbreekt ({pkgs}). Birth start niet tot de physics-installer klaar is. "
        f"Run: {INSTALL_HINT} — daarna Reuse data. Niet WIPE_FULL (tick-cache blijft geldig)."
    )


def cuda_required_message() -> str:
    return (
        "NVIDIA-videokaart gevonden maar CUDA-torch ontbreekt. "
        f"CPU-PPO is verboden zonder {CPU_PPO_ENV}=1. Run: {INSTALL_HINT}"
    )


def import_sb3_ppo() -> Any:
    """Import Stable-Baselines3 PPO or fail closed with the operator install hint."""
    try:
        from stable_baselines3 import PPO
    except ModuleNotFoundError as exc:
        missing = (str(exc.name or "stable_baselines3").strip() or "stable_baselines3",)
        raise RuntimeError(physics_missing_message(missing=missing)) from exc
    return PPO


def require_sb3_base_callback() -> Any:
    """Import SB3 BaseCallback or fail closed with the operator install hint."""
    try:
        from stable_baselines3.common.callbacks import BaseCallback
    except ImportError as exc:
        name = str(getattr(exc, "name", None) or "stable_baselines3").strip() or "stable_baselines3"
        raise RuntimeError(physics_missing_message(missing=(name,))) from exc
    return BaseCallback


def operator_physics_detail(exc: BaseException) -> str:
    """Operator-facing physics message. Never prefix RuntimeError / pip-install theatre."""
    text = str(exc).strip()
    if INSTALL_HINT in text or "Leermotor ontbreekt" in text or "CUDA-torch ontbreekt" in text:
        return text
    missing = ("stable_baselines3",)
    if isinstance(exc, ModuleNotFoundError):
        name = str(getattr(exc, "name", None) or "").strip()
        if name:
            missing = (name,)
    return physics_missing_message(missing=missing)


@dataclass(frozen=True, slots=True)
class BirthPhysicsProbe:
    ok: bool
    reason: str
    retryable: bool
    torch_ok: bool
    sb3_ok: bool
    gymnasium_ok: bool
    cuda_available: bool
    device_name: str | None
    python_exe: str
    missing: tuple[str, ...]
    human_message: str
    next_action: str | None
    recommended_actions: tuple[str, ...]

    def reject_payload(self, *, target_trades: int, training_mode: str) -> dict[str, Any]:
        return {
            "status": PHYSICS_UNAVAILABLE,
            "message": self.human_message,
            "reason": self.reason,
            "retryable": False,
            "target_trades": int(target_trades),
            "practice_mode": str(training_mode) == "practice",
            "missing": list(self.missing),
            "next_action": self.next_action,
            "recommended_actions": list(self.recommended_actions),
            "python": self.python_exe,
        }


@dataclass(frozen=True, slots=True)
class BirthExceptionAttention:
    retryable: bool
    reason_code: str
    actions: tuple[str, ...]


_DEFAULT_BIRTH_ERROR_ACTIONS: tuple[str, ...] = (
    "check_fabric_nt8",
    "check_mds_connection",
    "resume_from_checkpoint",
    "wipe_and_retry",
)


_PHYSICS_TEXT_MARKERS: tuple[str, ...] = (
    INSTALL_HINT,
    "Leermotor ontbreekt",
    "CUDA-torch ontbreekt",
    "PPOEvolutionLogger",
    "stable-baselines3",
    "stable_baselines3",
    "pip install stable-baselines3",
)


def is_physics_failure(exc: BaseException, *, _depth: int = 0) -> bool:
    if isinstance(exc, ModuleNotFoundError):
        name = str(getattr(exc, "name", "") or "").strip().lower()
        if name in {"torch", "stable_baselines3", "gymnasium"} or name.startswith(
            "stable_baselines3"
        ):
            return True
    text = str(exc)
    lowered = text.lower()
    if any(marker.lower() in lowered for marker in _PHYSICS_TEXT_MARKERS):
        return True
    if _depth >= 3:
        return False
    cause = exc.__cause__ or exc.__context__
    if cause is not None and cause is not exc:
        return is_physics_failure(cause, _depth=_depth + 1)
    return False


def birth_exception_attention(exc: BaseException) -> BirthExceptionAttention:
    if is_physics_failure(exc):
        return BirthExceptionAttention(
            retryable=False,
            reason_code=PHYSICS_UNAVAILABLE,
            actions=("install_birth_physics_stack", "retry_birth"),
        )
    return BirthExceptionAttention(
        retryable=True,
        reason_code="birth_error",
        actions=_DEFAULT_BIRTH_ERROR_ACTIONS,
    )


def trainer_requires_physics(trainer: object | None) -> bool:
    """True only for the live PPOTrainer mint path (never for test stubs)."""
    if trainer is None:
        return False
    create = getattr(trainer, "create_fresh_birth_policy", None)
    if not callable(create):
        return False
    module = str(getattr(create, "__module__", "") or "")
    return module.startswith("lumina_core.rl.")


def probe_birth_physics(
    *,
    importer: _Importer | None = None,
    has_nvidia: bool | None = None,
    allow_cpu_ppo: bool | None = None,
    python_exe: str | None = None,
) -> BirthPhysicsProbe:
    """Probe this interpreter. Never stubs sys.modules. Fail closed on missing SB3/torch."""
    load = importer or importlib.import_module
    exe = python_exe or sys.executable
    missing: list[str] = []
    torch_ok = False
    sb3_ok = False
    gym_ok = False
    cuda = False
    device: str | None = None

    try:
        torch_mod = load("torch")
        torch_ok = True
        cuda_mod = getattr(torch_mod, "cuda", None)
        cuda = bool(cuda_mod is not None and cuda_mod.is_available())
        if cuda:
            name = str(cuda_mod.get_device_name(0) or "").strip()
            device = name or "NVIDIA GPU"
    except Exception:
        missing.append("torch")

    try:
        load("gymnasium")
        gym_ok = True
    except Exception:
        missing.append("gymnasium")

    try:
        sb3 = load("stable_baselines3")
        if getattr(sb3, "PPO", None) is None:
            missing.append("stable_baselines3.PPO")
        else:
            sb3_ok = True
    except Exception:
        missing.append("stable_baselines3")

    if sb3_ok:
        try:
            callbacks = load("stable_baselines3.common.callbacks")
            if getattr(callbacks, "BaseCallback", None) is None:
                missing.append("stable_baselines3.common.callbacks.BaseCallback")
                sb3_ok = False
        except Exception:
            missing.append("stable_baselines3.common.callbacks")
            sb3_ok = False

    nvidia = bool(_has_nvidia()) if has_nvidia is None else bool(has_nvidia)
    if not torch_ok or not sb3_ok or not gym_ok or missing:
        miss = tuple(missing)
        return BirthPhysicsProbe(
            ok=False,
            reason=PHYSICS_UNAVAILABLE,
            retryable=False,
            torch_ok=torch_ok,
            sb3_ok=sb3_ok,
            gymnasium_ok=gym_ok,
            cuda_available=False,
            device_name=device,
            python_exe=exe,
            missing=miss,
            human_message=physics_missing_message(missing=miss),
            next_action=INSTALL_HINT,
            recommended_actions=("install_birth_physics_stack", "retry_birth"),
        )

    if nvidia and not cuda and not _cpu_ppo_allowed(allow_cpu_ppo):
        return BirthPhysicsProbe(
            ok=False,
            reason=CUDA_REQUIRED,
            retryable=False,
            torch_ok=True,
            sb3_ok=True,
            gymnasium_ok=True,
            cuda_available=False,
            device_name=device,
            python_exe=exe,
            missing=("torch.cuda",),
            human_message=cuda_required_message(),
            next_action=INSTALL_HINT,
            recommended_actions=("install_birth_physics_stack", "retry_birth"),
        )

    return BirthPhysicsProbe(
        ok=True,
        reason=PHYSICS_READY,
        retryable=True,
        torch_ok=True,
        sb3_ok=True,
        gymnasium_ok=True,
        cuda_available=cuda,
        device_name=device,
        python_exe=exe,
        missing=(),
        human_message="Leermotor klaar.",
        next_action=None,
        recommended_actions=(),
    )


def write_physics_failure_progress(
    workspace_root: Path | str,
    *,
    probe: BirthPhysicsProbe,
    target_trades: int,
    start_time: float,
    training_mode: str,
) -> None:
    write_birth_progress(
        workspace_root,
        stage="error",
        phase=PHYSICS_UNAVAILABLE,
        message=probe.human_message,
        progress_pct=0.0,
        cumulative_trades=0,
        target_trades=int(target_trades),
        ppo_steps=0,
        birth_start_time=float(start_time or 0.0),
        needs_attention=True,
        retryable=False,
        last_error=probe.human_message,
        attention_reason_code=PHYSICS_UNAVAILABLE,
        training_mode=str(training_mode),
        residual_failure=True,
        attention_recommended_actions=list(probe.recommended_actions),
        physics_probe={
            "ok": False,
            "reason": probe.reason,
            "missing": list(probe.missing),
            "python": probe.python_exe,
            "cuda_available": probe.cuda_available,
        },
    )


def enforce_birth_physics(
    svc: Any,
    *,
    target_trades: int,
    start_time: float,
    training_mode: str,
    probe: BirthPhysicsProbe | None = None,
) -> dict[str, Any] | None:
    """Launcher T=0 gate. Blocks wipe handshake / certified start / thread spawn."""
    result = probe if probe is not None else probe_birth_physics()
    if result.ok:
        return None
    logger.error(
        "birth.physics.preflight_failed reason=%s missing=%s python=%s",
        result.reason,
        ",".join(result.missing),
        result.python_exe,
    )
    svc._error = result.human_message
    try:
        write_physics_failure_progress(
            svc.workspace_root,
            probe=result,
            target_trades=int(target_trades),
            start_time=float(start_time or time.time()),
            training_mode=str(training_mode),
        )
    except Exception as exc:
        logger.warning("birth.physics.progress_write_failed: %s", exc)
    return result.reject_payload(target_trades=int(target_trades), training_mode=str(training_mode))


def reject_birth_if_physics_missing(
    host: Any,
    *,
    target_trades: int | None = None,
) -> dict[str, Any] | None:
    """Engine-path T=0 gate. Test stubs (non-rl module) skip; live PPOTrainer cannot."""
    trainer = getattr(host, "ppo_trainer", None)
    if trainer is None:
        runtime = getattr(host, "runtime", None)
        trainer = getattr(runtime, "ppo_trainer", None) if runtime is not None else None
    if not trainer_requires_physics(trainer):
        return None
    result = probe_birth_physics()
    if result.ok:
        return None
    cfg = getattr(host, "birth_config", None)
    resolved_target = int(target_trades or getattr(cfg, "trade_budget_cap", 0) or 0)
    training_mode = "practice" if bool(getattr(host, "practice_mode", False)) else "certified"
    start_time = float(getattr(host, "birth_start_time", 0.0) or time.time())
    logger.error(
        "birth.physics.engine_preflight_failed reason=%s missing=%s python=%s",
        result.reason,
        ",".join(result.missing),
        result.python_exe,
    )
    try:
        write_physics_failure_progress(
            host.workspace_root,
            probe=result,
            target_trades=resolved_target,
            start_time=start_time,
            training_mode=training_mode,
        )
    except Exception as exc:
        logger.warning("birth.physics.engine_progress_write_failed: %s", exc)
    return result.reject_payload(target_trades=resolved_target, training_mode=training_mode)

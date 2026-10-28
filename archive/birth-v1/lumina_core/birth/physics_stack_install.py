"""Windows-safe Birth physics stack installer (torch + SB3, never vLLM)."""

from __future__ import annotations

import os
import subprocess
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Sequence

from lumina_core.logging_utils import get_logger

logger = get_logger("lumina.birth.physics_stack_install")

TORCH_PIN = "torch==2.11.0"
SB3_PIN = "stable_baselines3==2.8.0"
GYM_PIN = "gymnasium==1.2.3"
FARAMA_PIN = "Farama-Notifications==0.0.4"

CUDA_INDEX_CANDIDATES: tuple[str, ...] = (
    "https://download.pytorch.org/whl/cu128",
    "https://download.pytorch.org/whl/cu129",
    "https://download.pytorch.org/whl/cu126",
)

FORBIDDEN_PACKAGES: frozenset[str] = frozenset({"vllm", "ray", "compressed-tensors"})

HUMAN_SUMMARY_LINES: tuple[str, ...] = (
    "Leermotor gezet. Denk-assistent is apart. vLLM is niet geïnstalleerd.",
    "Training engine installed. Talking assistant is separate.",
    "CUDA/PyTorch + Stable-Baselines3 only — never vLLM in this environment.",
    "Learning trades does not wait for the assistant.",
    "Next: Genesis / Birth. Voice (Ollama or cloud) is optional.",
)


@dataclass(frozen=True, slots=True)
class TorchInstallSpec:
    torch_spec: str
    index_url: str | None
    extra_packages: tuple[str, ...]
    require_cuda: bool
    reason: str

    def pip_commands(self, python_exe: str) -> list[list[str]]:
        commands: list[list[str]] = []
        torch_cmd = [python_exe, "-m", "pip", "install", "--upgrade", self.torch_spec]
        if self.index_url:
            torch_cmd.extend(["--index-url", self.index_url])
        commands.append(torch_cmd)
        rest = [python_exe, "-m", "pip", "install", "--upgrade", *self.extra_packages]
        commands.append(rest)
        return commands


def _has_nvidia() -> bool:
    try:
        completed = subprocess.run(
            ["nvidia-smi", "-L"],
            capture_output=True,
            text=True,
            timeout=8,
            check=False,
        )
    except Exception:
        return False
    return completed.returncode == 0 and bool((completed.stdout or "").strip())


def select_torch_install_spec(
    *,
    os_name: str | None = None,
    has_nvidia: bool | None = None,
) -> TorchInstallSpec:
    """Choose CUDA index on NVIDIA machines; CPU index otherwise. Never vLLM."""
    platform_name = (os_name or os.name).lower()
    nvidia = bool(has_nvidia) if has_nvidia is not None else _has_nvidia()
    extras = (SB3_PIN, GYM_PIN, FARAMA_PIN)
    if nvidia:
        return TorchInstallSpec(
            torch_spec=TORCH_PIN,
            index_url=CUDA_INDEX_CANDIDATES[0],
            extra_packages=extras,
            require_cuda=True,
            reason=f"nvidia gpu on {platform_name}; CUDA wheel required",
        )
    return TorchInstallSpec(
        torch_spec=TORCH_PIN,
        index_url=None,
        extra_packages=extras,
        require_cuda=False,
        reason=f"no nvidia gpu on {platform_name}; CPU torch",
    )


def assert_command_has_no_forbidden(command: Sequence[str]) -> None:
    joined = " ".join(command).lower()
    for banned in FORBIDDEN_PACKAGES:
        if banned in joined:
            raise RuntimeError(f"Birth physics installer must not install {banned}")


def _vllm_contaminated(python_exe: str) -> bool:
    probe = (
        "import importlib.util, sys; "
        "sys.exit(0 if importlib.util.find_spec('vllm') is None else 2)"
    )
    proc = subprocess.run([python_exe, "-c", probe], check=False, capture_output=True, text=True)
    return proc.returncode == 2


def install_birth_physics_stack(
    *,
    python_exe: str | None = None,
    workspace_root: Path | str | None = None,
    dry_run: bool = False,
) -> dict[str, object]:
    """Install torch+SB3 into the running interpreter. Never vLLM."""
    del workspace_root
    exe = python_exe or sys.executable
    spec = select_torch_install_spec()
    commands = spec.pip_commands(exe)
    for command in commands:
        assert_command_has_no_forbidden(command)
    ran: list[list[str]] = []
    if not dry_run:
        if spec.require_cuda:
            installed_cuda = False
            last_err = ""
            for index in CUDA_INDEX_CANDIDATES:
                cmd = [exe, "-m", "pip", "install", "--upgrade", TORCH_PIN, "--index-url", index]
                assert_command_has_no_forbidden(cmd)
                logger.info("birth.physics.install.torch index=%s", index)
                proc = subprocess.run(cmd, check=False, capture_output=True, text=True)
                ran.append(cmd)
                if proc.returncode == 0:
                    installed_cuda = True
                    break
                last_err = (proc.stderr or proc.stdout or "")[-2000:]
            if not installed_cuda:
                raise RuntimeError(
                    "CUDA torch wheel install failed on NVIDIA GPU. "
                    "CPU fallback is forbidden. Last pip error:\n"
                    f"{last_err}"
                )
        else:
            cmd = commands[0]
            logger.info("birth.physics.install cmd=%s", " ".join(cmd))
            subprocess.run(cmd, check=True)
            ran.append(cmd)
        rest = commands[1:]
        for cmd in rest:
            logger.info("birth.physics.install cmd=%s", " ".join(cmd))
            subprocess.run(cmd, check=True)
            ran.append(cmd)
        if _vllm_contaminated(exe):
            raise RuntimeError(
                "Physics venv is contaminated: import vllm succeeded. "
                "vLLM must never live next to the training engine."
            )
    return {
        "ok": True,
        "spec_reason": spec.reason,
        "require_cuda": spec.require_cuda,
        "commands": ran if ran else commands,
        "python": exe,
        "human_summary": list(HUMAN_SUMMARY_LINES),
        "vllm_installed": False,
    }

"""Sandboxed mutation executor façade (M5)."""
from __future__ import annotations

from typing import Any

from lumina_core.safety.sandboxed_executor_inprocess import SandboxedInProcessMixin
from lumina_core.safety.sandboxed_executor_subprocess import SandboxedSubprocessMixin
from pathlib import Path

from lumina_core.safety.sandboxed_executor_types import (
    SandboxedResult,
    _DEFAULT_TIMEOUT_S,
    _build_sandbox_env,
    _strip_secrets,
)

__all__ = ["SandboxedMutationExecutor", "SandboxedResult"]


class SandboxedMutationExecutor(SandboxedSubprocessMixin, SandboxedInProcessMixin):
    """Evaluates a DNA mutant in a fully isolated subprocess.

    Parameters
    ----------
    timeout_s:
        Hard subprocess timeout in seconds.  Overruns → failed evaluation.
    repo_root:
        Path to repository root used to populate ``sys.path`` inside the
        subprocess.  Defaults to three levels above this file.
    always_sandbox:
        If ``True``, subprocess mode is always used (ignores config).
        If ``False`` (default), uses config to decide (in-process for SIM
        when ``sandbox_mutations=false``).
    """

    def __init__(
        self,
        timeout_s: int = _DEFAULT_TIMEOUT_S,
        repo_root: Path | None = None,
        *,
        always_sandbox: bool = False,
    ) -> None:
        self._timeout_s = max(5, int(timeout_s))
        self._repo_root = repo_root or Path(__file__).resolve().parents[2]
        self._always_sandbox = always_sandbox

    def _should_use_subprocess(self, mode: str) -> bool:
        if self._always_sandbox:
            return True
        if str(mode).strip().lower() == "real":
            return True
        # Check config; default to True for safety.
        try:
            from lumina_core.config_loader import ConfigLoader

            evo = ConfigLoader.section("evolution", default={}) or {}
            return bool(evo.get("sandbox_mutations", True))
        except Exception:
            logging.exception("Unhandled broad exception fallback in lumina_core/safety/sandboxed_executor.py:256")
            return True

    def evaluate(
        self,
        *,
        dna_content: str,
        mode: str,
        pnl: float = 0.0,
        max_dd: float = 0.0,
        sharpe: float = 0.0,
    ) -> SandboxedResult:
        """Evaluate *dna_content* under *mode* and return a ``SandboxedResult``.

        Args:
            dna_content: Raw DNA string.
            mode: Trading mode (``"real"``, ``"paper"``, ``"sim"``).
            pnl: Net PnL for fitness calculation.
            max_dd: Maximum drawdown for fitness calculation.
            sharpe: Sharpe ratio for fitness calculation.

        Returns:
            ``SandboxedResult`` with ``passed=True`` iff constitution is clean
            and fitness > 0.
        """
        # Build deterministic input hash for audit trail.
        payload = {
            "dna_content": dna_content,
            "mode": mode,
            "pnl": pnl,
            "max_dd": max_dd,
            "sharpe": sharpe,
        }
        payload_json = json.dumps(payload, sort_keys=True)
        input_hash = hashlib.sha256(payload_json.encode()).hexdigest()
        dna_hash = hashlib.sha256(dna_content.encode()).hexdigest()[:16]

        if not self._should_use_subprocess(mode):
            return self._run_in_process(
                dna_hash=dna_hash,
                dna_content=dna_content,
                mode=mode,
                pnl=pnl,
                max_dd=max_dd,
                sharpe=sharpe,
                input_hash=input_hash,
            )

        return self._run_subprocess(
            dna_hash=dna_hash,
            payload_json=payload_json,
            input_hash=input_hash,
            mode=mode,
        )


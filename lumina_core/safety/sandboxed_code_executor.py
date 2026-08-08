"""SandboxedCodeExecutor — subprocess isolation for trading-code proposals.

Mirrors SandboxedMutationExecutor isolation guarantees:
  - private tmpdir for state/logs
  - secrets stripped from env
  - hard timeout
  - JSON stdin/stdout only
  - network effectively blocked
  - constitution re-check inside worker (defense in depth)

v1 evaluates PARAMETER_TWEAK / ADD_SIMPLE_INDICATOR / STRATEGY_SNIPPET_ADJUST only.
Never mutates the live repository tree.
"""

from __future__ import annotations

import hashlib
import json
import logging
import subprocess
import sys
import tempfile
from pathlib import Path
from typing import Any, Final

from lumina_core.code_evolution.proposal import CodeSandboxEvalResult
from lumina_core.safety.sandboxed_executor import _build_sandbox_env

logger = logging.getLogger(__name__)

_DEFAULT_TIMEOUT_S: Final[int] = 30
_MAX_STDOUT_BYTES: Final[int] = 64 * 1024

# Worker runs entirely from embedded script — no pickle.
from lumina_core.safety.sandboxed_code_worker import _CODE_SANDBOX_WORKER

class SandboxedCodeExecutor:
    """Evaluate a code-evolution proposal in an isolated subprocess."""

    def __init__(
        self,
        timeout_s: int = _DEFAULT_TIMEOUT_S,
        repo_root: Path | None = None,
        *,
        always_sandbox: bool = True,
    ) -> None:
        self._timeout_s = max(5, int(timeout_s))
        self._repo_root = repo_root or Path(__file__).resolve().parents[2]
        self._always_sandbox = always_sandbox

    def evaluate(
        self,
        *,
        proposal_id: str,
        operator: str,
        payload: dict[str, Any],
        mode: str = "sim",
    ) -> CodeSandboxEvalResult:
        """Run sandboxed evaluation. Fail-closed on any error/timeout."""
        body = {
            "proposal_id": proposal_id,
            "operator": operator,
            "payload": payload,
            "mode": mode,
        }
        payload_json = json.dumps(body, sort_keys=True)
        input_hash = hashlib.sha256(payload_json.encode()).hexdigest()

        # Always sandbox for code evolution (v1 invariant) unless tests force otherwise.
        if not self._always_sandbox and str(mode).lower() == "sim":
            return self._run_in_process(
                proposal_id=proposal_id,
                operator=operator,
                payload=payload,
                mode=mode,
                input_hash=input_hash,
            )

        return self._run_subprocess(
            proposal_id=proposal_id,
            payload_json=payload_json,
            input_hash=input_hash,
            mode=mode,
        )

    def _run_subprocess(
        self,
        *,
        proposal_id: str,
        payload_json: str,
        input_hash: str,
        mode: str,
    ) -> CodeSandboxEvalResult:
        with tempfile.TemporaryDirectory(prefix="lumina_code_sbx_") as tmpdir:
            tmp = Path(tmpdir)
            (tmp / "state").mkdir()
            (tmp / "logs").mkdir()

            env = _build_sandbox_env()
            env["LUMINA_SANDBOX_TMP"] = tmpdir
            env["LUMINA_REPO_ROOT"] = str(self._repo_root)

            try:
                proc = subprocess.run(
                    [sys.executable, "-c", _CODE_SANDBOX_WORKER],
                    input=payload_json,
                    capture_output=True,
                    text=True,
                    timeout=self._timeout_s,
                    env=env,
                    check=False,
                )
            except subprocess.TimeoutExpired:
                logger.warning(
                    "SandboxedCodeExecutor TIMEOUT (id=%s, limit=%ds)",
                    proposal_id,
                    self._timeout_s,
                )
                return CodeSandboxEvalResult(
                    proposal_id=proposal_id,
                    passed=False,
                    score=0.0,
                    violations=["sandbox_timeout"],
                    input_hash=input_hash,
                    output_hash="",
                    timed_out=True,
                    error=f"timeout after {self._timeout_s}s",
                    mode=mode,
                    sandbox_used=True,
                )
            except Exception as exc:
                logger.error("SandboxedCodeExecutor subprocess error: %s", exc)
                return CodeSandboxEvalResult(
                    proposal_id=proposal_id,
                    passed=False,
                    score=0.0,
                    violations=["sandbox_process_error"],
                    input_hash=input_hash,
                    output_hash="",
                    error=str(exc)[:200],
                    mode=mode,
                    sandbox_used=True,
                )

            stdout = (proc.stdout or "").strip()[:_MAX_STDOUT_BYTES]
            output_hash = hashlib.sha256(stdout.encode()).hexdigest()

            if proc.returncode != 0:
                return CodeSandboxEvalResult(
                    proposal_id=proposal_id,
                    passed=False,
                    score=0.0,
                    violations=["subprocess_nonzero_exit"],
                    input_hash=input_hash,
                    output_hash=output_hash,
                    error=f"exit={proc.returncode}: {(proc.stderr or '')[:200]}",
                    mode=mode,
                    sandbox_used=True,
                )

            try:
                result = json.loads(stdout)
            except (json.JSONDecodeError, ValueError) as exc:
                return CodeSandboxEvalResult(
                    proposal_id=proposal_id,
                    passed=False,
                    score=0.0,
                    violations=["output_parse_error"],
                    input_hash=input_hash,
                    output_hash=output_hash,
                    error=str(exc),
                    mode=mode,
                    sandbox_used=True,
                )

            viol = list(result.get("violations") or [])
            score = float(result.get("score", 0.0) or 0.0)
            passed = bool(result.get("passed")) and not viol and score > 0.0
            return CodeSandboxEvalResult(
                proposal_id=proposal_id,
                passed=passed,
                score=score if passed else 0.0,
                violations=viol if not passed else [],
                input_hash=input_hash,
                output_hash=output_hash,
                mode=mode,
                sandbox_used=True,
            )

    def _run_in_process(
        self,
        *,
        proposal_id: str,
        operator: str,
        payload: dict[str, Any],
        mode: str,
        input_hash: str,
    ) -> CodeSandboxEvalResult:
        """SIM-only fallback used in unit tests when always_sandbox=False."""
        # Delegate to subprocess path by default for honesty; in-process only for speed tests.
        try:
            body = {"operator": operator, "payload": payload}
            # Reuse subprocess always for real isolation when possible.
            return self._run_subprocess(
                proposal_id=proposal_id,
                payload_json=json.dumps(body, sort_keys=True),
                input_hash=input_hash,
                mode=mode,
            )
        except Exception as exc:
            return CodeSandboxEvalResult(
                proposal_id=proposal_id,
                passed=False,
                score=0.0,
                violations=["in_process_error"],
                input_hash=input_hash,
                output_hash="",
                error=str(exc)[:200],
                mode=mode,
                sandbox_used=False,
            )

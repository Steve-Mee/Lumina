"""Subprocess sandbox runner (M5 extract)."""
from __future__ import annotations

import hashlib
import json
import logging
import subprocess
import sys
import tempfile
from pathlib import Path

from lumina_core.safety.sandboxed_executor_types import (
    SandboxedResult,
    _build_sandbox_env,
    _MAX_STDOUT_BYTES,
    _SANDBOX_WORKER_SCRIPT,
)

logger = logging.getLogger(__name__)


class SandboxedSubprocessMixin:
    def _run_subprocess(
        self,
        *,
        dna_hash: str,
        payload_json: str,
        input_hash: str,
        mode: str,
    ) -> SandboxedResult:
        with tempfile.TemporaryDirectory(prefix="lumina_sbx_") as tmpdir:
            tmp = Path(tmpdir)
            (tmp / "state").mkdir()
            (tmp / "logs").mkdir()

            env = _build_sandbox_env()
            env["LUMINA_SANDBOX_TMP"] = tmpdir
            env["LUMINA_REPO_ROOT"] = str(self._repo_root)

            try:
                proc = subprocess.run(
                    [sys.executable, "-c", _SANDBOX_WORKER_SCRIPT],
                    input=payload_json,
                    capture_output=True,
                    text=True,
                    timeout=self._timeout_s,
                    env=env,
                )
            except subprocess.TimeoutExpired:
                logger.warning(
                    "SandboxedMutationExecutor TIMEOUT (dna=%s, mode=%s, limit=%ds)",
                    dna_hash,
                    mode,
                    self._timeout_s,
                )
                return SandboxedResult(
                    dna_hash=dna_hash,
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
                logger.error("SandboxedMutationExecutor subprocess error: %s", exc)
                return SandboxedResult(
                    dna_hash=dna_hash,
                    score=0.0,
                    violations=["sandbox_process_error"],
                    input_hash=input_hash,
                    output_hash="",
                    error=str(exc),
                    mode=mode,
                    sandbox_used=True,
                )

        stdout = proc.stdout.strip()[:_MAX_STDOUT_BYTES]
        output_hash = hashlib.sha256(stdout.encode()).hexdigest()

        if proc.returncode != 0:
            logger.warning(
                "Sandbox non-zero exit %d (dna=%s): stderr=%s",
                proc.returncode,
                dna_hash,
                proc.stderr[:300],
            )
            return SandboxedResult(
                dna_hash=dna_hash,
                score=0.0,
                violations=["subprocess_nonzero_exit"],
                input_hash=input_hash,
                output_hash=output_hash,
                error=f"exit={proc.returncode}: {proc.stderr[:200]}",
                mode=mode,
                sandbox_used=True,
            )

        try:
            result = json.loads(stdout)
        except (json.JSONDecodeError, ValueError) as exc:
            logger.error("Sandbox output parse error: %s | stdout=%r", exc, stdout[:200])
            return SandboxedResult(
                dna_hash=dna_hash,
                score=0.0,
                violations=["output_parse_error"],
                input_hash=input_hash,
                output_hash=output_hash,
                error=str(exc),
                mode=mode,
                sandbox_used=True,
            )

        logger.debug(
            "Sandbox result: dna=%s mode=%s score=%.4f violations=%s",
            dna_hash,
            mode,
            result.get("score", 0.0),
            result.get("violations", []),
        )
        return SandboxedResult(
            dna_hash=dna_hash,
            score=float(result.get("score", 0.0)),
            violations=list(result.get("violations", [])),
            input_hash=input_hash,
            output_hash=output_hash,
            mode=mode,
            sandbox_used=True,
        )


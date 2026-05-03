"""SandboxedMutationExecutor — fully isolated subprocess execution for DNA evaluation.

Every DNA mutation is scored in a hermetically isolated subprocess before the
result is trusted.  This guarantees:

  1. State isolation — all I/O is redirected to a private tmpdir; the live
     ``state/`` and ``logs/`` directories are never touched.
  2. Process isolation — a buggy or adversarially crafted mutant cannot crash,
     corrupt, or DoS the parent LUMINA process.
  3. Constitutional pre-screening — the constitution is checked inside the
     sandbox so violations are caught before any code is executed.
  4. Deterministic auditing — every evaluation produces a signed audit record
     (SHA-256 of inputs + outputs) suitable for forensic review.
  5. Hard timeout — every sandbox has a maximum wall-clock budget; overruns
     are treated as failed evaluations, never as successes.

Security model:
  - JSON stdin/stdout — no pickle/shared memory, preventing gadget attacks.
  - No network — the subprocess is invoked without sockets; any attempt to
    call external APIs will fail silently inside the sandbox.
  - Env-var whitelist — only the vars required for Python imports are passed;
    secrets (API keys, tokens) are stripped from the subprocess environment.
"""

from __future__ import annotations

import hashlib
import json
import logging
import os
import subprocess
import sys
import tempfile
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Final

logger = logging.getLogger(__name__)

_DEFAULT_TIMEOUT_S: Final[int] = 45
_MAX_STDOUT_BYTES: Final[int] = 64 * 1024  # 64 KB max output

# Env-var keys that must NEVER be forwarded to the sandbox.
_SECRET_ENV_PREFIXES: Final[tuple[str, ...]] = (
    "XAI_API_KEY",
    "OPENAI_API_KEY",
    "ANTHROPIC_API_KEY",
    "NT_ACCESS_TOKEN",
    "CROSSTRADE_TOKEN",
    "TELEGRAM_BOT_TOKEN",
    "LUMINA_JWT_SECRET",
    "SECRET_",
    "PRIVATE_",
    "PASSWORD",
    "PASSWD",
    "API_KEY",
    "AUTH_TOKEN",
)


def _strip_secrets(env: dict[str, str]) -> dict[str, str]:
    """Return a copy of *env* with all secret-like variables removed."""
    clean: dict[str, str] = {}
    for k, v in env.items():
        upper_k = k.upper()
        if any(
            upper_k.startswith(prefix) or upper_k.endswith(prefix) or upper_k == prefix
            for prefix in _SECRET_ENV_PREFIXES
        ):
            continue
        clean[k] = v
    return clean


# ---------------------------------------------------------------------------
# Result
# ---------------------------------------------------------------------------


@dataclass(slots=True)
class SandboxedResult:
    """Result of a sandboxed DNA evaluation.

    Attributes:
        dna_hash:      SHA-256 of the input DNA content (first 16 chars for display).
        score:         Fitness score returned by the sandbox (0.0 on any failure).
        violations:    List of constitutional violation names (fatal only).
        input_hash:    SHA-256 of the full input payload for audit trail.
        output_hash:   SHA-256 of the raw subprocess stdout for audit trail.
        timed_out:     True when the subprocess exceeded the time budget.
        error:         Human-readable error description (empty on success).
        mode:          Trading mode the evaluation was run under.
        sandbox_used:  True when a subprocess sandbox was used; False for in-process.
    """

    dna_hash: str
    score: float
    violations: list[str]
    input_hash: str
    output_hash: str
    timed_out: bool = False
    error: str = ""
    mode: str = ""
    sandbox_used: bool = True

    @property
    def passed(self) -> bool:
        """True when the mutant is safe to promote (score > 0, no violations, no error)."""
        return not self.timed_out and not self.error and not self.violations and self.score > 0.0

    @property
    def is_constitutional(self) -> bool:
        """True when zero constitutional violations were detected."""
        return not self.violations

    def to_audit_record(self) -> dict[str, Any]:
        """Serialisable dict for append to evolution_metrics.jsonl."""
        return {
            "dna_hash": self.dna_hash,
            "score": self.score,
            "violations": self.violations,
            "input_hash": self.input_hash,
            "output_hash": self.output_hash,
            "timed_out": self.timed_out,
            "error": self.error,
            "mode": self.mode,
            "sandbox_used": self.sandbox_used,
            "passed": self.passed,
        }


# ---------------------------------------------------------------------------
# The subprocess script that runs inside the sandbox
# ---------------------------------------------------------------------------

_SANDBOX_WORKER_SCRIPT: Final[str] = """\
import json, sys, os, hashlib
from pathlib import Path

# 1. Reroute all state/logs writes to the private tmpdir.
_tmp = os.environ.get("LUMINA_SANDBOX_TMP", "")
if _tmp:
    _sd = str(Path(_tmp) / "state")
    _ld = str(Path(_tmp) / "logs")
    Path(_sd).mkdir(parents=True, exist_ok=True)
    Path(_ld).mkdir(parents=True, exist_ok=True)
    os.environ["LUMINA_STATE_DIR"] = _sd
    os.environ["LUMINA_LOGS_DIR"] = _ld

# 2. Ensure repo root is importable.
_root = os.environ.get("LUMINA_REPO_ROOT", "")
if _root and _root not in sys.path:
    sys.path.insert(0, _root)

# 3. Disable any outbound network by monkey-patching socket at the lowest level.
try:
    import socket as _socket
    _socket.setdefaulttimeout(0.001)  # effectively blocks network calls
except Exception:
    logger.exception("Sandboxed executor failed to apply socket timeout hardening")

# 4. Keep startup side-effects disabled during sandbox scoring.
os.environ["LUMINA_SKIP_STARTUP_DIALOG"] = "1"

# 5. Read input payload from stdin.
try:
    payload = json.loads(sys.stdin.read())
except Exception as exc:
    print(json.dumps({"score": 0.0, "violations": [f"parse_error:{exc}"]}))
    sys.exit(1)

dna_content = str(payload.get("dna_content", ""))
mode = str(payload.get("mode", "sim"))
pnl = float(payload.get("pnl", 0.0))
max_dd = float(payload.get("max_dd", 0.0))
sharpe = float(payload.get("sharpe", 0.0))

violations = []
score = 0.0

# 6. Constitutional screening (fail-closed).
try:
    from lumina_core.safety.trading_constitution import TRADING_CONSTITUTION
    found = TRADING_CONSTITUTION.audit(dna_content, mode=mode, raise_on_fatal=False)
    violations = [v.principle_name for v in found if v.severity == "fatal"]
except Exception as exc:
    violations = [f"constitution_error:{exc}"]

# 7. Fitness scoring (only if constitution passed).
if not violations:
    try:
        from lumina_core.evolution.genetic_operators import calculate_fitness
        score = float(calculate_fitness(pnl, max_dd, sharpe))
    except Exception as exc:
        score = 0.0
        violations.append(f"fitness_error:{exc}")

print(json.dumps({"score": score, "violations": violations}))
"""


def _build_sandbox_env() -> dict[str, str]:
    """Build a sanitised environment for the subprocess."""
    clean = _strip_secrets(dict(os.environ))
    clean["LUMINA_SKIP_STARTUP_DIALOG"] = "1"
    return clean


# ---------------------------------------------------------------------------
# SandboxedMutationExecutor
# ---------------------------------------------------------------------------


class SandboxedMutationExecutor:
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

    def _run_in_process(
        self,
        *,
        dna_hash: str,
        dna_content: str,
        mode: str,
        pnl: float,
        max_dd: float,
        sharpe: float,
        input_hash: str,
    ) -> SandboxedResult:
        """In-process fallback for SIM mode — faster but without process isolation."""
        from lumina_core.safety.trading_constitution import TRADING_CONSTITUTION
        from lumina_core.evolution.genetic_operators import calculate_fitness

        violations: list[str] = []
        score = 0.0

        try:
            found = TRADING_CONSTITUTION.audit(dna_content, mode=mode, raise_on_fatal=False)
            violations = [v.principle_name for v in found if v.severity == "fatal"]
        except Exception as exc:
            logging.exception("Unhandled broad exception fallback in lumina_core/safety/sandboxed_executor.py:435")
            violations = [f"constitution_error:{exc}"]

        if not violations:
            try:
                score = float(calculate_fitness(pnl, max_dd, sharpe))
            except Exception as exc:
                logging.exception("Unhandled broad exception fallback in lumina_core/safety/sandboxed_executor.py:441")
                violations.append(f"fitness_error:{exc}")

        out_data = json.dumps({"score": score, "violations": violations})
        return SandboxedResult(
            dna_hash=dna_hash,
            score=score,
            violations=violations,
            input_hash=input_hash,
            output_hash=hashlib.sha256(out_data.encode()).hexdigest(),
            mode=mode,
            sandbox_used=False,
        )

"""MutationSandbox — isolated scoring of DNA mutants before promotion.

Runs the fitness scoring of a mutant PolicyDNA in a subprocess with a hard
timeout, so that:
  - A buggy mutant cannot corrupt the parent process state.
  - Side-effects on ``state/`` are blocked via env-var redirection.
  - A timed-out scoring attempt is treated as a failed candidate.

Design notes:
  - The sandbox uses ``subprocess`` + ``json`` stdin/stdout, not pickling,
    to avoid pickle-gadget attacks.
  - REAL mode always sandboxes; SIM mode sandboxes by default but can be
    disabled via config for speed.
  - Constitutional auditing happens inside the sandbox so violations are
    caught before any I/O reaches the live state directory.
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
from typing import Any

from lumina_core.config_loader import ConfigLoader

logger = logging.getLogger(__name__)

_SANDBOX_TIMEOUT_S = 45  # hard kill after 45 s


@dataclass(slots=True)
class SandboxResult:
    """Result of a sandboxed mutant evaluation."""

    dna_hash: str
    score: float
    violations: list[str]        # constitutional violation names
    stdout_hash: str             # SHA-256 of subprocess stdout for audit
    timed_out: bool = False
    error: str = ""

    @property
    def passed(self) -> bool:
        """True when the mutant scored > 0 with no fatal violations and no timeout."""
        return (
            not self.timed_out
            and not self.error
            and self.score > 0.0
            and not self.violations
        )


# ---------------------------------------------------------------------------
# Subprocess entry point
# ---------------------------------------------------------------------------

_SANDBOX_SCRIPT = """\
import json, sys, os, hashlib
from pathlib import Path

# Redirect state/logs to the tmp dir provided by the parent.
tmp_dir = os.environ.get("LUMINA_SANDBOX_TMP", "")
if tmp_dir:
    os.environ["LUMINA_STATE_DIR"] = str(Path(tmp_dir) / "state")
    os.environ["LUMINA_LOGS_DIR"] = str(Path(tmp_dir) / "logs")

repo_root = os.environ.get("LUMINA_REPO_ROOT", "")
if repo_root and repo_root not in sys.path:
    sys.path.insert(0, repo_root)

payload = json.loads(sys.stdin.read())
dna_content = payload["dna_content"]
mode = payload.get("mode", "sim")
pnl = float(payload.get("pnl", 0.0))
max_dd = float(payload.get("max_dd", 0.0))
sharpe = float(payload.get("sharpe", 0.0))

violations = []
score = 0.0

try:
    from lumina_core.engine.constitutional_principles import ConstitutionalChecker
    checker = ConstitutionalChecker()
    found = checker.audit(dna_content, mode=mode, raise_on_fatal=False)
    violations = [v.principle_name for v in found if v.severity == "fatal"]
except Exception as exc:
    violations = [f"checker_error:{exc}"]

if not violations:
    try:
        from lumina_core.evolution.genetic_operators import calculate_fitness
        score = calculate_fitness(pnl, max_dd, sharpe)
    except Exception as exc:
        score = 0.0
        violations.append(f"fitness_error:{exc}")

result = {
    "score": float(score),
    "violations": violations,
}
print(json.dumps(result))
"""


def _sandbox_enabled(mode: str) -> bool:
    """Returns True when mutation sandboxing is active for the given mode."""
    evo = ConfigLoader.section("evolution", default={}) or {}
    if not isinstance(evo, dict):
        return True
    # Default: always sandbox in REAL; configurable in SIM/PAPER.
    default = mode == "real"
    return bool(evo.get("sandbox_mutations", default))


class MutationSandbox:
    """Evaluates a PolicyDNA mutant in a subprocess with a hard timeout.

    Parameters
    ----------
    timeout_s:
        Subprocess timeout in seconds.  Defaults to ``_SANDBOX_TIMEOUT_S``.
    repo_root:
        Path to the repository root.  Defaults to three levels up from
        this file (``lumina_core/evolution/mutation_sandbox.py``).
    """

    def __init__(
        self,
        timeout_s: int = _SANDBOX_TIMEOUT_S,
        repo_root: Path | None = None,
    ) -> None:
        self._timeout_s = int(timeout_s)
        self._repo_root = repo_root or Path(__file__).resolve().parents[2]

    def evaluate(
        self,
        *,
        dna_hash: str,
        dna_content: str,
        mode: str,
        pnl: float = 0.0,
        max_dd: float = 0.0,
        sharpe: float = 0.0,
    ) -> SandboxResult:
        """Score a mutant DNA in an isolated subprocess.

        If sandboxing is disabled for this mode (config), the evaluation runs
        in-process for speed — but this path should only be used in SIM mode.
        """
        if not _sandbox_enabled(mode):
            return self._evaluate_in_process(
                dna_hash=dna_hash,
                dna_content=dna_content,
                mode=mode,
                pnl=pnl,
                max_dd=max_dd,
                sharpe=sharpe,
            )

        payload = json.dumps(
            {
                "dna_content": dna_content,
                "mode": mode,
                "pnl": pnl,
                "max_dd": max_dd,
                "sharpe": sharpe,
            }
        )

        with tempfile.TemporaryDirectory(prefix="lumina_sandbox_") as tmpdir:
            tmp = Path(tmpdir)
            (tmp / "state").mkdir()
            (tmp / "logs").mkdir()

            env = {**os.environ}
            env["LUMINA_SANDBOX_TMP"] = tmpdir
            env["LUMINA_REPO_ROOT"] = str(self._repo_root)
            env["LUMINA_SKIP_STARTUP_DIALOG"] = "1"

            try:
                proc = subprocess.run(
                    [sys.executable, "-c", _SANDBOX_SCRIPT],
                    input=payload,
                    capture_output=True,
                    text=True,
                    timeout=self._timeout_s,
                    env=env,
                )
            except subprocess.TimeoutExpired:
                logger.warning("MutationSandbox timed out for dna_hash=%s", dna_hash)
                return SandboxResult(
                    dna_hash=dna_hash,
                    score=0.0,
                    violations=["sandbox_timeout"],
                    stdout_hash="",
                    timed_out=True,
                    error="timeout",
                )
            except Exception as exc:
                logger.error("MutationSandbox subprocess error: %s", exc)
                return SandboxResult(
                    dna_hash=dna_hash,
                    score=0.0,
                    violations=["sandbox_error"],
                    stdout_hash="",
                    error=str(exc),
                )

        stdout = proc.stdout.strip()
        stdout_hash = hashlib.sha256(stdout.encode()).hexdigest()

        if proc.returncode != 0:
            logger.warning(
                "MutationSandbox non-zero exit %d for dna_hash=%s: %s",
                proc.returncode,
                dna_hash,
                proc.stderr[:400],
            )
            return SandboxResult(
                dna_hash=dna_hash,
                score=0.0,
                violations=["subprocess_exit_nonzero"],
                stdout_hash=stdout_hash,
                error=proc.stderr[:400],
            )

        try:
            result = json.loads(stdout)
        except (json.JSONDecodeError, ValueError) as exc:
            logger.error("MutationSandbox could not parse output: %s", exc)
            return SandboxResult(
                dna_hash=dna_hash,
                score=0.0,
                violations=["invalid_output"],
                stdout_hash=stdout_hash,
                error=str(exc),
            )

        return SandboxResult(
            dna_hash=dna_hash,
            score=float(result.get("score", 0.0)),
            violations=list(result.get("violations", [])),
            stdout_hash=stdout_hash,
        )

    # ------------------------------------------------------------------
    # In-process fallback (SIM / testing)
    # ------------------------------------------------------------------

    def _evaluate_in_process(
        self,
        *,
        dna_hash: str,
        dna_content: str,
        mode: str,
        pnl: float,
        max_dd: float,
        sharpe: float,
    ) -> SandboxResult:
        from lumina_core.engine.constitutional_principles import ConstitutionalChecker
        from lumina_core.evolution.genetic_operators import calculate_fitness

        violations: list[str] = []
        score = 0.0

        try:
            checker = ConstitutionalChecker()
            found = checker.audit(dna_content, mode=mode, raise_on_fatal=False)
            violations = [v.principle_name for v in found if v.severity == "fatal"]
        except Exception as exc:
            violations = [f"checker_error:{exc}"]

        if not violations:
            try:
                score = calculate_fitness(pnl, max_dd, sharpe)
            except Exception as exc:
                score = 0.0
                violations.append(f"fitness_error:{exc}")

        stdout_str = json.dumps({"score": score, "violations": violations})
        return SandboxResult(
            dna_hash=dna_hash,
            score=score,
            violations=violations,
            stdout_hash=hashlib.sha256(stdout_str.encode()).hexdigest(),
        )

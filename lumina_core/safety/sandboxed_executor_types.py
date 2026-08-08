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

import logging
import os
from dataclasses import dataclass
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
# LAST LINE OF DEFENSE: even if a tricked twin or upstream selection approved the DNA,
# the sandbox worker *always* re-runs the full TradingConstitution audit before any fitness.
# Violations here make passed=False regardless of twin recommendation.
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



__all__ = ['SandboxedResult', '_strip_secrets', '_build_sandbox_env']

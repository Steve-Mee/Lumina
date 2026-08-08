"""In-process sandbox runner (M5 extract)."""
from __future__ import annotations

import hashlib
import json
import logging

from lumina_core.safety.sandboxed_executor_types import SandboxedResult

logger = logging.getLogger(__name__)


class SandboxedInProcessMixin:
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

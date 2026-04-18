from __future__ import annotations

import copy
import random
from concurrent.futures import ThreadPoolExecutor, as_completed
from dataclasses import dataclass, field
from typing import Any, Callable


@dataclass(slots=True)
class ABExperimentResult:
    experiment_id: str
    selected_variant: dict[str, Any]
    variants: list[dict[str, Any]] = field(default_factory=list)


@dataclass(slots=True)
class ABExperimentFramework:
    """SIM-mode A/B framework that forks candidate agents and promotes the strongest."""

    min_forks: int = 3
    max_forks: int = 5
    max_workers: int = 5

    def run_auto_forks(
        self,
        *,
        base_agent: dict[str, Any],
        score_fn: Callable[[dict[str, Any]], dict[str, Any]],
        promote_fn: Callable[[dict[str, Any]], None] | None = None,
        seed: int | None = None,
    ) -> ABExperimentResult:
        fork_count = int(max(self.min_forks, min(self.max_forks, self.max_forks)))
        rng = random.Random(seed)
        forks = self._build_forks(base_agent=base_agent, fork_count=fork_count, rng=rng)

        results: list[dict[str, Any]] = []
        with ThreadPoolExecutor(max_workers=min(self.max_workers, fork_count)) as pool:
            future_map = {pool.submit(score_fn, fork): fork for fork in forks}
            for future in as_completed(future_map):
                fork = future_map[future]
                try:
                    scored = dict(future.result() or {})
                except Exception as exc:
                    scored = dict(fork)
                    scored["score"] = 0.0
                    scored["confidence"] = 0.0
                    scored["ab_error"] = str(exc)
                results.append(scored)

        selected = max(results, key=lambda item: float(item.get("score", 0.0))) if results else dict(base_agent)
        if promote_fn is not None:
            promote_fn(selected)

        return ABExperimentResult(
            experiment_id=f"ab-sim-{rng.randint(100000, 999999)}",
            selected_variant=selected,
            variants=results,
        )

    def _build_forks(self, *, base_agent: dict[str, Any], fork_count: int, rng: random.Random) -> list[dict[str, Any]]:
        forks: list[dict[str, Any]] = []
        for idx in range(int(fork_count)):
            fork = copy.deepcopy(base_agent)
            fork["name"] = f"{base_agent.get('name', 'agent')}_fork_{idx + 1}"
            suggestion = dict(fork.get("hyperparam_suggestion", {}))
            risk = float(suggestion.get("max_risk_percent", 1.0) or 1.0)
            dd = float(suggestion.get("drawdown_kill_percent", 8.0) or 8.0)
            threshold = float(suggestion.get("fast_path_threshold", 0.78) or 0.78)

            suggestion["max_risk_percent"] = round(max(0.1, min(5.0, risk * (1.0 + rng.uniform(-0.2, 0.2)))), 3)
            suggestion["drawdown_kill_percent"] = round(max(1.0, min(40.0, dd * (1.0 + rng.uniform(-0.15, 0.15)))), 3)
            suggestion["fast_path_threshold"] = round(max(0.4, min(0.95, threshold + rng.uniform(-0.08, 0.08))), 3)
            fork["hyperparam_suggestion"] = suggestion
            fork["ab_variant"] = idx + 1
            fork["ab_parent"] = str(base_agent.get("name", "base_agent"))
            forks.append(fork)
        return forks

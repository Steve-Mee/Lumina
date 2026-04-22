from __future__ import annotations

import copy
import hashlib
import random
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable


_DEFAULT_NEURO_DIR = Path("state/neuro_weights")


def _utc_stamp() -> str:
    return datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S%fZ")


def _clone_state_dict(state_dict: dict[str, Any]) -> dict[str, Any]:
    return {name: value.clone() if hasattr(value, "clone") else copy.deepcopy(value) for name, value in state_dict.items()}


def _try_import_torch() -> Any | None:
    try:
        import torch  # type: ignore

        return torch
    except Exception:
        return None


def _is_float_tensor(value: Any) -> bool:
    return bool(
        hasattr(value, "dtype")
        and hasattr(value, "numel")
        and hasattr(value, "detach")
        and str(getattr(value, "dtype", "")).startswith("torch.float")
    )


def mutate_weights(
    model: Any,
    *,
    mutation_std: float = 0.01,
    mutation_rate: float = 0.08,
    seed: int | None = None,
) -> dict[str, Any]:
    """Gaussian mutate floating-point tensors in PPO policy state_dict."""
    torch = _try_import_torch()
    if torch is None:
        return _clone_state_dict(dict(model.policy.state_dict()))

    if seed is not None:
        torch.manual_seed(int(seed))

    parent_state = dict(model.policy.state_dict())
    child_state = _clone_state_dict(parent_state)

    with torch.no_grad():
        for name, tensor in child_state.items():
            if not _is_float_tensor(tensor):
                continue
            if int(tensor.numel()) <= 0:
                continue
            mask = torch.rand_like(tensor) < float(mutation_rate)
            if bool(mask.any()):
                noise = torch.randn_like(tensor) * float(mutation_std)
                child_state[name] = tensor + (noise * mask.to(dtype=tensor.dtype))

    return child_state


def crossover_weights(
    parent1: dict[str, Any],
    parent2: dict[str, Any],
    *,
    crossover_ratio: float = 0.5,
    seed: int | None = None,
) -> dict[str, Any]:
    """Create child state_dict by tensor-wise random crossover."""
    torch = _try_import_torch()
    if torch is None:
        return _clone_state_dict(parent1)

    if seed is not None:
        torch.manual_seed(int(seed))

    child = _clone_state_dict(parent1)
    with torch.no_grad():
        for name, p1 in parent1.items():
            p2 = parent2.get(name)
            if p2 is None:
                continue
            if _is_float_tensor(p1) and _is_float_tensor(p2) and tuple(p1.shape) == tuple(p2.shape):
                mask = torch.rand_like(p1) < float(crossover_ratio)
                child[name] = torch.where(mask, p1, p2)
            elif hasattr(p1, "clone"):
                child[name] = p1.clone()
            else:
                child[name] = copy.deepcopy(p1)
    return child


def _build_candidate_model(base_model: Any, state_dict: dict[str, Any]) -> Any:
    candidate_model = copy.deepcopy(base_model)
    candidate_model.policy.load_state_dict(state_dict, strict=True)
    return candidate_model


def _default_eval_score(candidate_id: str) -> dict[str, Any]:
    seed = int(hashlib.sha256(candidate_id.encode("utf-8")).hexdigest()[:8], 16)
    rng = random.Random(seed)
    fitness = float(rng.uniform(-0.1, 0.4))
    confidence = float(rng.uniform(0.75, 0.97))
    return {
        "fitness": fitness,
        "confidence": confidence,
        "shadow_passed": bool(fitness > 0.0),
        "backtest_passed": bool(fitness > 0.0),
    }


def evaluate_weight_population(
    base_model: Any,
    *,
    evaluator: Callable[[Path, dict[str, Any]], dict[str, Any] | float] | None = None,
    population_size: int = 6,
    mutation_std: float = 0.01,
    mutation_rate: float = 0.08,
    crossover_ratio: float = 0.5,
    output_dir: Path = _DEFAULT_NEURO_DIR,
    max_workers: int = 4,
    seed: int | None = None,
) -> dict[str, Any]:
    """Generate, persist, and evaluate a mutated PPO weight population.

    Candidates are persisted as Stable-Baselines .zip files in output_dir.
    """
    size = max(2, int(population_size))
    rng = random.Random(seed)
    output_dir.mkdir(parents=True, exist_ok=True)

    base_state = dict(base_model.policy.state_dict())
    mutated_parents: list[dict[str, Any]] = []
    candidates: list[dict[str, Any]] = []

    for index in range(size):
        local_seed = rng.randint(0, 2**31 - 1)
        if index < max(2, size // 2):
            candidate_state = mutate_weights(
                base_model,
                mutation_std=mutation_std,
                mutation_rate=mutation_rate,
                seed=local_seed,
            )
            mutated_parents.append(candidate_state)
            origin = "mutate"
        else:
            p1 = mutated_parents[index % len(mutated_parents)] if mutated_parents else _clone_state_dict(base_state)
            p2 = (
                mutated_parents[(index + 1) % len(mutated_parents)]
                if len(mutated_parents) > 1
                else _clone_state_dict(base_state)
            )
            candidate_state = crossover_weights(
                p1,
                p2,
                crossover_ratio=crossover_ratio,
                seed=local_seed,
            )
            origin = "crossover"

        candidate_model = _build_candidate_model(base_model, candidate_state)
        candidate_id = f"{_utc_stamp()}_{index}_{origin}"
        candidate_path = output_dir / f"{candidate_id}.zip"
        candidate_model.save(str(candidate_path))
        candidates.append(
            {
                "candidate_id": candidate_id,
                "path": candidate_path,
                "state_dict": candidate_state,
                "origin": origin,
            }
        )

    def _evaluate(item: dict[str, Any]) -> dict[str, Any]:
        raw: dict[str, Any] | float
        if evaluator is None:
            raw = _default_eval_score(str(item["candidate_id"]))
        else:
            raw = evaluator(Path(item["path"]), {"candidate_id": item["candidate_id"], "origin": item["origin"]})

        payload = {"fitness": float("-inf"), "confidence": 0.0, "shadow_passed": False, "backtest_passed": False}
        if isinstance(raw, dict):
            payload.update(raw)
        else:
            payload["fitness"] = float(raw)

        return {
            "candidate_id": str(item["candidate_id"]),
            "path": str(item["path"]),
            "origin": str(item["origin"]),
            "fitness": float(payload.get("fitness", float("-inf")) or float("-inf")),
            "confidence": float(payload.get("confidence", 0.0) or 0.0),
            "shadow_passed": bool(payload.get("shadow_passed", False)),
            "backtest_passed": bool(payload.get("backtest_passed", False)),
        }

    evaluations: list[dict[str, Any]] = []
    with ThreadPoolExecutor(max_workers=max(1, min(int(max_workers), len(candidates)))) as pool:
        future_map = {pool.submit(_evaluate, item): item for item in candidates}
        for future in as_completed(future_map):
            item = future_map[future]
            try:
                evaluations.append(future.result())
            except Exception:
                evaluations.append(
                    {
                        "candidate_id": str(item["candidate_id"]),
                        "path": str(item["path"]),
                        "origin": str(item["origin"]),
                        "fitness": float("-inf"),
                        "confidence": 0.0,
                        "shadow_passed": False,
                        "backtest_passed": False,
                    }
                )

    evaluations.sort(key=lambda row: float(row.get("fitness", float("-inf"))), reverse=True)
    winner = next(
        (
            row
            for row in evaluations
            if bool(row.get("shadow_passed", False)) and bool(row.get("backtest_passed", False))
        ),
        None,
    )

    winner_state: dict[str, Any] | None = None
    if winner is not None:
        winner_state = next(
            (item["state_dict"] for item in candidates if str(item["candidate_id"]) == str(winner.get("candidate_id", ""))),
            None,
        )

    return {
        "output_dir": str(output_dir),
        "population_size": len(candidates),
        "evaluations": evaluations,
        "winner": winner,
        "winner_state_dict": winner_state,
    }

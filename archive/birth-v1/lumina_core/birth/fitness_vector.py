"""Birth gen-0 fitness vector written at Stage 5 probe (ADR-0046).

DNA generation 0 fitness is this vector — not EdgeScore, not missing cert-Sharpe.
Checksum must match the Stage-5 foundation receipt for Birth exit.
"""

from __future__ import annotations

import hashlib
import json
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any

from lumina_core.birth.foundation_metrics import FOUNDATION_SCHEMA

FITNESS_VECTOR_NAME = "lumina_birth_fitness_vector.json"


@dataclass(frozen=True, slots=True)
class BirthFitnessVector:
    schema: str
    mean_r: float
    edge: float
    occupancy: float
    oos_wr: float
    oos_sharpe: float
    median_loss_r: float
    s5_receipt_checksum: str
    trades: int

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)

    @classmethod
    def from_dict(cls, raw: dict[str, Any]) -> BirthFitnessVector | None:
        if not isinstance(raw, dict):
            return None
        if str(raw.get("schema") or "") != FOUNDATION_SCHEMA:
            return None
        try:
            return cls(
                schema=FOUNDATION_SCHEMA,
                mean_r=float(raw["mean_r"]),
                edge=float(raw["edge"]),
                occupancy=float(raw["occupancy"]),
                oos_wr=float(raw["oos_wr"]),
                oos_sharpe=float(raw["oos_sharpe"]),
                median_loss_r=float(raw["median_loss_r"]),
                s5_receipt_checksum=str(raw["s5_receipt_checksum"]),
                trades=int(raw["trades"]),
            )
        except (KeyError, TypeError, ValueError):
            return None


def fitness_vector_path(workspace_root: Path | str) -> Path:
    return Path(workspace_root) / "state" / FITNESS_VECTOR_NAME


def receipt_checksum(payload: dict[str, Any]) -> str:
    canonical = json.dumps(payload, sort_keys=True, default=str)
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()[:16]


def write_fitness_vector(workspace_root: Path | str, vector: BirthFitnessVector) -> Path:
    path = fitness_vector_path(workspace_root)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(vector.to_dict(), indent=2), encoding="utf-8")
    return path


def load_fitness_vector(workspace_root: Path | str) -> BirthFitnessVector | None:
    path = fitness_vector_path(workspace_root)
    if not path.is_file():
        return None
    try:
        raw = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return None
    return BirthFitnessVector.from_dict(raw) if isinstance(raw, dict) else None


__all__ = [
    "BirthFitnessVector",
    "FITNESS_VECTOR_NAME",
    "fitness_vector_path",
    "load_fitness_vector",
    "receipt_checksum",
    "write_fitness_vector",
]

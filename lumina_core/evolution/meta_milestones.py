"""Self-authored evolution milestones after Gen0 DNA (M16+)."""

from __future__ import annotations

import json
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from lumina_core.logging_utils import get_logger

logger = get_logger("lumina.evolution.meta_milestones")

META_MILESTONES_PATH = "state/lumina_meta_milestones.jsonl"


@dataclass(slots=True)
class MetaMilestone:
    milestone_id: str
    target_metric: str
    target_value: float
    regime_focus: str
    trade_budget: int
    reward_variant: str
    generation: int
    authored_at: float = field(default_factory=time.time)
    metadata: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return {
            "milestone_id": self.milestone_id,
            "target_metric": self.target_metric,
            "target_value": float(self.target_value),
            "regime_focus": str(self.regime_focus),
            "trade_budget": int(self.trade_budget),
            "reward_variant": str(self.reward_variant),
            "generation": int(self.generation),
            "authored_at": float(self.authored_at),
            "metadata": dict(self.metadata),
        }

    @classmethod
    def from_dict(cls, raw: dict[str, Any]) -> MetaMilestone:
        return cls(
            milestone_id=str(raw.get("milestone_id", "") or ""),
            target_metric=str(raw.get("target_metric", "winrate") or "winrate"),
            target_value=float(raw.get("target_value", 0.0) or 0.0),
            regime_focus=str(raw.get("regime_focus", "MIXED") or "MIXED"),
            trade_budget=max(500, int(raw.get("trade_budget", 2000) or 2000)),
            reward_variant=str(raw.get("reward_variant", "expectancy") or "expectancy"),
            generation=max(0, int(raw.get("generation", 0) or 0)),
            authored_at=float(raw.get("authored_at", time.time()) or time.time()),
            metadata=dict(raw.get("metadata") or {}) if isinstance(raw.get("metadata"), dict) else {},
        )


def meta_milestones_path(workspace_root: Path | str) -> Path:
    return Path(workspace_root) / META_MILESTONES_PATH


def append_meta_milestone(workspace_root: Path | str, milestone: MetaMilestone) -> None:
    path = meta_milestones_path(workspace_root)
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a", encoding="utf-8") as handle:
        handle.write(json.dumps(milestone.to_dict(), ensure_ascii=True) + "\n")
    logger.info("meta_milestones.appended id=%s gen=%s", milestone.milestone_id, milestone.generation)


def load_meta_milestones(workspace_root: Path | str) -> list[MetaMilestone]:
    path = meta_milestones_path(workspace_root)
    if not path.is_file():
        return []
    out: list[MetaMilestone] = []
    for line in path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line:
            continue
        try:
            raw = json.loads(line)
            if isinstance(raw, dict):
                out.append(MetaMilestone.from_dict(raw))
        except json.JSONDecodeError:
            continue
    return out


def _certificate_floor_winrate(workspace_root: Path) -> float:
    from lumina_core.birth.config import load_birth_v2_config

    cfg = load_birth_v2_config(workspace_root)
    return float(cfg.certificate_thresholds.min_oos_winrate)


def propose_next_milestone(
    workspace_root: Path | str,
    *,
    generation: int,
    current_winrate: float,
    current_sharpe: float,
    regime_coverage: int,
) -> MetaMilestone | None:
    """Bounded creativity: never below certificate floors."""
    root = Path(workspace_root)
    floor_wr = _certificate_floor_winrate(root)
    existing = load_meta_milestones(root)
    next_idx = len(existing) + 16
    regimes = ["TRENDING", "RANGING", "MIXED", "HIGH_VOLATILITY"]
    regime_focus = regimes[next_idx % len(regimes)]

    target_wr = max(floor_wr, min(0.62, current_winrate + 0.02))
    target_metric = "winrate" if current_winrate < 0.52 else "sharpe"
    target_value = target_wr if target_metric == "winrate" else max(0.35, current_sharpe + 0.05)

    reward_variants = ("expectancy", "trend_align", "range_patience", "risk_discipline")
    reward_variant = reward_variants[next_idx % len(reward_variants)]
    trade_budget = max(2000, 1500 + (next_idx * 250))

    milestone = MetaMilestone(
        milestone_id=f"M{next_idx}",
        target_metric=target_metric,
        target_value=round(target_value, 4),
        regime_focus=regime_focus,
        trade_budget=trade_budget,
        reward_variant=reward_variant,
        generation=generation,
        metadata={
            "regime_coverage": int(regime_coverage),
            "floor_winrate": floor_wr,
        },
    )
    append_meta_milestone(root, milestone)
    return milestone


def dynamic_stage_specs(workspace_root: Path | str) -> list[dict[str, Any]]:
    """Convert meta milestones to curriculum-compatible stage specs."""
    milestones = load_meta_milestones(workspace_root)
    specs: list[dict[str, Any]] = []
    for ms in milestones:
        specs.append(
            {
                "stage_id": f"meta_{ms.milestone_id.lower()}",
                "label": f"Meta {ms.milestone_id}",
                "trade_budget": ms.trade_budget,
                "target_metric": ms.target_metric,
                "target_value": ms.target_value,
                "regime_focus": ms.regime_focus,
                "reward_variant": ms.reward_variant,
                "generation": ms.generation,
            }
        )
    return specs
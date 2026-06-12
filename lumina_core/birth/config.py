"""Birth v2 configuration loader."""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import yaml

from lumina_core.birth.birth_certificate import BirthCertificateThresholds

logger = logging.getLogger("lumina.birth.config")


@dataclass(slots=True)
class BirthCurriculumConfig:
    stage1_trend_trades: int = 2000
    stage2_range_trades: int = 3000
    stage3_mixed_trades: int = 5000
    stage4_polish_ppo_steps: int = 50_000


@dataclass(slots=True)
class BirthV2Config:
    curriculum: BirthCurriculumConfig = field(default_factory=BirthCurriculumConfig)
    holdout_pct: float = 0.20
    certificate_thresholds: BirthCertificateThresholds = field(default_factory=BirthCertificateThresholds)
    prefer_real_data_only: bool = True
    max_real_days: int = 90
    ppo_update_timesteps: int = 25_000
    chunk_size: int = 50_000
    trade_budget_cap: int = 10_000


def _coerce_int(value: Any, default: int) -> int:
    try:
        return int(value)
    except (TypeError, ValueError):
        return default


def _coerce_float(value: Any, default: float) -> float:
    try:
        return float(value)
    except (TypeError, ValueError):
        return default


def load_birth_v2_config(workspace_root: Path | str | None = None) -> BirthV2Config:
    root = Path(workspace_root or Path.cwd())
    cfg_path = root / "config.yaml"
    raw: dict[str, Any] = {}
    if cfg_path.is_file():
        try:
            loaded = yaml.safe_load(cfg_path.read_text(encoding="utf-8")) or {}
            if isinstance(loaded, dict):
                raw = loaded
        except Exception as exc:
            logger.warning("birth_v2.config_load_failed detail=%s", exc)

    section = raw.get("birth_v2")
    if not isinstance(section, dict):
        section = {}
        # Deprecation bridge from first_boot
        fb = raw.get("first_boot")
        if isinstance(fb, dict):
            logger.warning("birth_v2: using deprecated first_boot keys; migrate to birth_v2 in config.yaml")
            section = {
                "prefer_real_data_only": fb.get("prefer_real_data_only", True),
                "max_real_days": fb.get("max_real_days", 90),
                "trade_budget_cap": fb.get("training_trades", 10_000),
                "ppo_update_timesteps": fb.get("ppo_update_timesteps", 25_000),
            }

    cur_raw = section.get("curriculum") if isinstance(section.get("curriculum"), dict) else {}
    thr_raw = section.get("certificate_thresholds") if isinstance(section.get("certificate_thresholds"), dict) else {}

    curriculum = BirthCurriculumConfig(
        stage1_trend_trades=_coerce_int(cur_raw.get("stage1_trend_trades"), 2000),
        stage2_range_trades=_coerce_int(cur_raw.get("stage2_range_trades"), 3000),
        stage3_mixed_trades=_coerce_int(cur_raw.get("stage3_mixed_trades"), 5000),
        stage4_polish_ppo_steps=_coerce_int(cur_raw.get("stage4_polish_ppo_steps"), 50_000),
    )

    try:
        thresholds = BirthCertificateThresholds.model_validate(thr_raw or {})
    except Exception:
        thresholds = BirthCertificateThresholds()

    return BirthV2Config(
        curriculum=curriculum,
        holdout_pct=max(0.05, min(0.4, _coerce_float(section.get("holdout_pct"), 0.20))),
        certificate_thresholds=thresholds,
        prefer_real_data_only=bool(section.get("prefer_real_data_only", True)),
        max_real_days=max(30, min(3650, _coerce_int(section.get("max_real_days"), 90))),
        ppo_update_timesteps=max(1000, _coerce_int(section.get("ppo_update_timesteps"), 25_000)),
        chunk_size=max(2500, _coerce_int(section.get("chunk_size"), 50_000)),
        trade_budget_cap=max(500, _coerce_int(section.get("trade_budget_cap"), 10_000)),
    )

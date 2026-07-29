"""Birth v2 configuration loader.

Bounded modules: ``config_curriculum`` (dataclasses), ``config_coercion`` (parse helpers).
Public imports remain stable via this façade.
"""
from __future__ import annotations

import logging
from pathlib import Path
from typing import Any

import yaml

from lumina_core.birth.config_coercion import (  # noqa: F401
    _coerce_float,
    _coerce_int,
    _coerce_wall_behavior,
    _parse_expansion_steps,
    build_certificate_thresholds,
    build_curriculum_config,
    build_news_config,
    build_reward_config,
    resolve_effective_trade_budget,
    resolve_trade_budget_cap,
)
from lumina_core.birth.config_curriculum import (  # noqa: F401
    BRO_ENGINE_VERSION,
    BirthCurriculumConfig,
    BirthNewsConfig,
    BirthRewardConfig,
    BirthV2Config,
)

logger = logging.getLogger("lumina.birth.config")

__all__ = [
    "BRO_ENGINE_VERSION",
    "BirthCurriculumConfig",
    "BirthNewsConfig",
    "BirthRewardConfig",
    "BirthV2Config",
    "load_birth_v2_config",
    "resolve_effective_trade_budget",
    "resolve_trade_budget_cap",
]


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
    news_raw = section.get("news") if isinstance(section.get("news"), dict) else {}
    reward_raw = section.get("reward") if isinstance(section.get("reward"), dict) else {}
    thr_raw = section.get("certificate_thresholds") if isinstance(section.get("certificate_thresholds"), dict) else {}

    curriculum = build_curriculum_config(cur_raw if isinstance(cur_raw, dict) else {})
    news = build_news_config(news_raw if isinstance(news_raw, dict) else {})
    reward = build_reward_config(reward_raw if isinstance(reward_raw, dict) else {})
    thresholds = build_certificate_thresholds(thr_raw if isinstance(thr_raw, dict) else {})

    trade_budget_cap, budget_source = resolve_trade_budget_cap(raw)
    logger.info("birth.budget cap=%s source=%s", trade_budget_cap, budget_source)

    return BirthV2Config(
        curriculum=curriculum,
        news=news,
        reward=reward,
        holdout_pct=max(0.05, min(0.4, _coerce_float(section.get("holdout_pct"), 0.20))),
        certificate_thresholds=thresholds,
        prefer_real_data_only=bool(section.get("prefer_real_data_only", True)),
        max_real_days=max(30, min(3650, _coerce_int(section.get("max_real_days"), 90))),
        ppo_update_timesteps=max(1000, _coerce_int(section.get("ppo_update_timesteps"), 25_000)),
        chunk_size=max(2500, _coerce_int(section.get("chunk_size"), 50_000)),
        trade_budget_cap=trade_budget_cap,
    )

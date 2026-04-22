"""Fase-3 evolutie-stress: OHLC (DNA) en PPO multi-rollout — sessie, env, yaml.

Leesvolgorde per instelling: omgeving → ``state/bot_stress_choices.json`` → ``config.yaml``.
"""

from __future__ import annotations

import json
import os
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from lumina_core.config_loader import ConfigLoader

BOT_STRESS_CHOICES_FILE = Path("state/bot_stress_choices.json")

ENV_OHLC_DNA_STRESS = "LUMINA_OHLC_DNA_STRESS"
ENV_NEURO_OHLC_ROLLOUTS = "LUMINA_NEURO_OHLC_ROLLOUTS"

TOOLTIP_OHLC_DNA_NL = (
    "Als aangevinkt: bij DNA-evolutie met echte historische OHLC/ticks past Lumina per "
    "parallelle realiteit het prijspad aan (Fase 3: stress_simulator_ohlc). Robuustere "
    "strategieën op ruwere koersen; nadeel: alleen actief wanneer er echte data geladen is. "
    "Uit: sneller, geen transformatie op de reeks."
)

TOOLTIP_NEURO_OHLC_NL = (
    "Als aangevinkt: PPO-gewichten worden per kandidaat meerdere keren geëvalueerd op "
    "verschillend gestresste OHLC (eff. aantal = parallel stress-universa). "
    "Zelfde “slechtste realiteit wint”-idee. Voordeel: realistischere zware test. "
    "Nadeel: sterk meer CPU (meerdere volledige rollouts per gewicht; kan lang duren). "
    "Uit: alleen lichtere metric-stress (Fase 2) op één rollout."
)


def _env_tristate(name: str) -> bool | None:
    raw = os.environ.get(name)
    if raw is None or str(raw).strip() == "":
        return None
    s = str(raw).strip().lower()
    if s in ("1", "true", "yes", "on"):
        return True
    if s in ("0", "false", "no", "off"):
        return False
    return None


def _load_file() -> dict[str, Any]:
    if not BOT_STRESS_CHOICES_FILE.is_file():
        return {}
    try:
        data = json.loads(BOT_STRESS_CHOICES_FILE.read_text(encoding="utf-8"))
    except Exception:
        return {}
    return data if isinstance(data, dict) else {}


def _from_yaml_ohlc_dna() -> bool:
    ev = ConfigLoader.section("evolution", default={}) or {}
    if not isinstance(ev, dict):
        return True
    return bool(ev.get("ohlc_reality_stress_enabled", True))


def _from_yaml_neuro_ohlc() -> bool:
    n = ConfigLoader.section("evolution", "neuroevolution", default={}) or {}
    if not isinstance(n, dict):
        return False
    return bool(n.get("use_ohlc_stress_rollouts", False))


def resolve_ohlc_reality_stress_enabled() -> bool:
    t = _env_tristate(ENV_OHLC_DNA_STRESS)
    if t is not None:
        return t
    data = _load_file()
    if "ohlc_reality_stress_enabled" in data:
        return bool(data.get("ohlc_reality_stress_enabled"))
    return _from_yaml_ohlc_dna()


def resolve_neuro_ohlc_stress_rollouts() -> bool:
    t = _env_tristate(ENV_NEURO_OHLC_ROLLOUTS)
    if t is not None:
        return t
    data = _load_file()
    if "use_ohlc_stress_rollouts" in data:
        return bool(data.get("use_ohlc_stress_rollouts"))
    return _from_yaml_neuro_ohlc()


def save_bot_stress_choices(
    *,
    ohlc_reality_stress_enabled: bool,
    use_ohlc_stress_rollouts: bool,
) -> None:
    """Slaat keuzes op en zet huidige omgeving (zelfde process als evolutie)."""
    ohlc = bool(ohlc_reality_stress_enabled)
    neuro = bool(use_ohlc_stress_rollouts)
    os.environ[ENV_OHLC_DNA_STRESS] = "1" if ohlc else "0"
    os.environ[ENV_NEURO_OHLC_ROLLOUTS] = "1" if neuro else "0"
    BOT_STRESS_CHOICES_FILE.parent.mkdir(parents=True, exist_ok=True)
    payload = {
        "ohlc_reality_stress_enabled": ohlc,
        "use_ohlc_stress_rollouts": neuro,
        "updated_at": datetime.now(timezone.utc).isoformat(),
    }
    BOT_STRESS_CHOICES_FILE.write_text(json.dumps(payload, indent=2), encoding="utf-8")


def apply_env_stress_flags(
    ohlc_dna: int | None,
    neuro_ohlc: int | None,
) -> None:
    """CLI: zet env alleen voor meegegeven argumenten (0 of 1)."""
    if ohlc_dna is not None:
        os.environ[ENV_OHLC_DNA_STRESS] = "1" if int(ohlc_dna) == 1 else "0"
    if neuro_ohlc is not None:
        os.environ[ENV_NEURO_OHLC_ROLLOUTS] = "1" if int(neuro_ohlc) == 1 else "0"

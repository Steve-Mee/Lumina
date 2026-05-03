"""Parallel stress-universa (multi-reality SIM): configuratie, aanbeveling en opslag.

Eindwaarde (integer 1–50) via :func:`resolve_parallel_realities`:

+---------------------------+---------------------------------------------------------+
| Bron                      | Wanneer                                                 |
+===========================+=========================================================+
| ``LUMINA_PARALLEL_REALITIES`` | Gezet in shell of in ``.env``; hoogste prioriteit.  |
| (of CLI)                  | Voorbeeld: ``python lumina_runtime.py --parallel-      |
|                           | realities 12 …`` (zie ``runtime_entrypoint``).         |
+---------------------------+---------------------------------------------------------+
| ``state/                  | Opgeslagen via dashboard of startdialoog; blijft       |
| parallel_realities_      | lokaal staan tot overschreven.                          |
| session.json``            |                                                         |
+---------------------------+---------------------------------------------------------+
| ``config.yaml``           | ``evolution.multiweek_fitness.parallel_realities``      |
|                           | (fallback; vaak 1)                                     |
+---------------------------+---------------------------------------------------------+

Headless/CI: zet ``LUMINA_SKIP_STARTUP_DIALOG=1`` zodat ``lumina_runtime`` geen tk-dialoog
opent (bijv. in pytest, ``tests/conftest.py``). Tests: ``tests/test_parallel_reality_config.py``.

Onbekende/lege env-waarde: niet als int parsebaar → volgende laag (sessie, dan yaml).
"""

from __future__ import annotations

import json
import logging
import os
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from lumina_core.config_loader import ConfigLoader

logger = logging.getLogger(__name__)

PARALLEL_REALITIES_MIN = 1
PARALLEL_REALITIES_MAX = 50
ENV_PARALLEL_REALITIES = "LUMINA_PARALLEL_REALITIES"
SESSION_FILE = Path("state/parallel_realities_session.json")

# Voor tooltips / dialoog (NL)
TOOLTIP_SHORT_NL = (
    f"Bereik: {PARALLEL_REALITIES_MIN}–{PARALLEL_REALITIES_MAX} parallelle stress-universa. "
    "Bij meerdere universa scoort elke DNA-candidaat op het slechtste scenario (robuustheid). "
    "Voordeel: minder kans op 'geluk' in één gunstige markt. "
    "Nadeel: duidelijk meer CPU-werk en langere nacht-evolutie. "
    f"Waarde {PARALLEL_REALITIES_MIN} schakelt extra stress-universa uit (snelst, minst robuust)."
)

TOOLTIP_TEMPLATE_NL = (
    f"Aantal parallelle stress-universa: min {PARALLEL_REALITIES_MIN}, max {PARALLEL_REALITIES_MAX}. "
    "Elk universum is een ander stressprofiel (black-swan, flash-crash, regime-shift, …). "
    "Fitness wordt geaggregeerd (conservatief: de slechtste casus telt sterk mee). "
    "Meer universa: robuustere strategie, minder overfitting; maar hogere CPU-belasting en langere runs. "
    "Minder of 1: sneller en lichter, minder strakke stress-test. "
    "Aanbevolen op dit systeem: {aanbevolen} (o.b.v. CPU-cores, om overbelasting te beperken)."
)


def clamp_parallel(n: int) -> int:
    return max(PARALLEL_REALITIES_MIN, min(PARALLEL_REALITIES_MAX, int(n)))


def _logical_cores() -> int:
    try:
        from lumina_core.engine.hardware_inspector import HardwareInspector

        snap = HardwareInspector.load_cached()
        if snap is not None:
            return max(1, int(snap.cpu_cores_logical))
    except Exception:
        logger.exception("parallel_reality_config failed to load cached hardware snapshot")
    return max(1, int(os.cpu_count() or 4))


def recommend_parallel_realities() -> int:
    """Aanbevolen aantal stress-universa o.b.v. CPU (~⅔ logische cores, gecapped op max 50)."""
    logical = _logical_cores()
    rec = max(1, (logical * 2) // 3)
    return min(PARALLEL_REALITIES_MAX, rec)


def format_tooltip_nl() -> str:
    return TOOLTIP_TEMPLATE_NL.format(aanbevolen=recommend_parallel_realities())


def _from_yaml() -> int:
    evolution_cfg = ConfigLoader.section("evolution", default={}) or {}
    mw_cfg = evolution_cfg.get("multiweek_fitness", {}) if isinstance(evolution_cfg, dict) else {}
    if not isinstance(mw_cfg, dict):
        return 1
    try:
        n = int(mw_cfg.get("parallel_realities", 1) or 1)
    except (TypeError, ValueError):
        return 1
    return clamp_parallel(n)


def _parse_intish(raw: str | None) -> int | None:
    if raw is None or str(raw).strip() == "":
        return None
    try:
        return int(str(raw).strip(), 10)
    except (TypeError, ValueError):
        return None


def load_session_parallel_realities() -> int | None:
    """Publiek: huidige waarde uit sessiebestand, of None."""
    return _load_session_file()


def _load_session_file() -> int | None:
    if not SESSION_FILE.is_file():
        return None
    try:
        data = json.loads(SESSION_FILE.read_text(encoding="utf-8"))
    except Exception:
        logging.exception("Unhandled broad exception fallback in lumina_core/evolution/parallel_reality_config.py:121")
        return None
    if not isinstance(data, dict):
        return None
    n = _parse_intish(data.get("parallel_realities"))
    if n is None:
        return None
    return clamp_parallel(n)


def resolve_parallel_realities() -> int:
    """Eindwaarde 1–50: env, dan sessiebestand, dan yaml."""
    env_val = _parse_intish(os.environ.get(ENV_PARALLEL_REALITIES))
    if env_val is not None:
        return clamp_parallel(env_val)

    session_val = _load_session_file()
    if session_val is not None:
        return session_val

    return _from_yaml()


def save_parallel_realities_session(value: int) -> int:
    """Persisteert keuze en zet de huidige omgeving (zelfde process als evolutie)."""
    n = clamp_parallel(value)
    os.environ[ENV_PARALLEL_REALITIES] = str(n)
    SESSION_FILE.parent.mkdir(parents=True, exist_ok=True)
    payload: dict[str, Any] = {
        "parallel_realities": n,
        "updated_at": datetime.now(timezone.utc).isoformat(),
    }
    SESSION_FILE.write_text(json.dumps(payload, indent=2), encoding="utf-8")
    return n


def apply_env_parallel_realities(value: int | str | None) -> int | None:
    """Voor CLI: zet env als waarde meegegeven; anders ongewijzigd."""
    if value is None:
        return None
    try:
        n = int(str(value).strip(), 10)
    except (TypeError, ValueError):
        return None
    n = clamp_parallel(n)
    os.environ[ENV_PARALLEL_REALITIES] = str(n)
    return n


def default_spinbox_value() -> int:
    """Voorstel voor UI: sessie, anders aanbeveling, anders yaml."""
    s = _load_session_file()
    if s is not None:
        return s
    rec = recommend_parallel_realities()
    y = _from_yaml()
    if y != 1 and y != rec:
        return y
    return rec

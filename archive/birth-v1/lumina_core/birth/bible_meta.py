"""Update daytrading bible meta-learning after birth."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from lumina_bible.bible_engine import BibleEngine

from lumina_core.birth.birth_certificate import BirthCertificateV2
from lumina_core.logging_utils import get_logger

logger = get_logger("lumina.birth.bible_meta")


def update_bible_after_birth(
    workspace_root: Path | str,
    certificate: BirthCertificateV2,
    eval_result: dict[str, Any],
) -> None:
    root = Path(workspace_root)
    bible_path = root / "state" / "lumina_daytrading_bible.json"
    if not bible_path.is_file():
        return

    reflection = (
        f"birth_v2 | oos_winrate={certificate.oos_winrate:.2%}, "
        f"sharpe={certificate.oos_sharpe:.2f}, violations={certificate.constitution_violations}"
    )

    try:
        bible_engine = BibleEngine(file_path=str(bible_path))
        layer = dict(bible_engine.evolvable_layer or {})
        meta = dict(layer.get("meta_learning", {}) if isinstance(layer.get("meta_learning"), dict) else {})
        meta["events_observed"] = int(meta.get("events_observed", 0) or 0) + 1
        meta["birth_v2"] = {
            "oos_sharpe": certificate.oos_sharpe,
            "oos_winrate": certificate.oos_winrate,
            "regimes_covered": certificate.regimes_covered,
            "policy_sha256": certificate.policy_sha256,
        }
        lessons = list(layer.get("lessons_learned", []) if isinstance(layer.get("lessons_learned"), list) else [])
        entry = "Birth v2 certificate issued with OOS validation"
        if entry not in lessons:
            lessons.append(entry)
        bible_engine.evolve(
            {
                "meta_learning": meta,
                "last_reflection": reflection,
                "lessons_learned": lessons,
            }
        )
    except Exception:
        logger.warning("birth.bible_meta.evolve_failed", exc_info=True)
        return

    prior_path = root / "state" / "birth_regime_prior.json"
    try:
        prior_path.write_text(
            json.dumps(
                {
                    "regimes_covered": certificate.regimes_covered,
                    "holdout_days": eval_result.get("holdout_days"),
                    "distribution": eval_result.get("regimes_covered"),
                },
                ensure_ascii=True,
                indent=2,
            ),
            encoding="utf-8",
        )
    except OSError:
        logger.warning("birth.bible_meta.prior_write_failed", exc_info=True)

from __future__ import annotations

import copy
import json
import os
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Any

DEFAULT_BIBLE = {
    "sacred_core": """
HUMAN PLAYBOOK - Dit is hoe een ervaren MES daytrader denkt:
1. Scalping (tape reading, MA ribbon)
2. Momentum + Pullback (buy the dip in strong trend)
3. Breakout / Opening Range Breakout (ORB)
4. Reversal / Mean Reversion / Fade
5. Range trading
6. Trend following + Retracement
7. News / Gap / Event trading (3-sterren events!)
8. VWAP trading (institutionele fair value)
9. Pure Price Action + Candlestick
10. Pivot Points + Daily High/Low

Regels:
- Altijd multi-timeframe (240/1440 voor bias)
- Alleen traden met minstens 2 confluences
- Risk 1-2% per trade, 1:2+ RR
- Geen emotie, geen revenge trading
- Leer uit elke trade (journaling)
""",
    "evolvable_layer": {
        "mtf_matrix": {"dominant_tf": "240min", "confluence_scores": {}},
        "filters": ["volume_delta > 2.0x avg", "price_above_ema_50", "adx > 22"],
        "probability_model": {"base_winrate": 0.71, "confluence_bonus": 0.24, "risk_penalty": 0.06},
        "last_reflection": "2026-03-27: v21.6 Echte Candle Aggregatie + Robuuste API Parsing",
        "lessons_learned": [],
    },
}


@dataclass(slots=True)
class BibleEngine:
    file_path: Path | str = Path("lumina_daytrading_bible.json")
    bible: dict[str, Any] | None = None

    def __post_init__(self) -> None:
        path = Path(self.file_path)
        object.__setattr__(self, "file_path", path)
        if not path:
            raise ValueError("Bible file path is required")
        self.bible = self.load()

    @property
    def evolvable_layer(self) -> dict[str, Any]:
        assert self.bible is not None
        return self.bible.setdefault("evolvable_layer", {})

    def load(self) -> dict[str, Any]:
        if self.file_path.exists():
            with self.file_path.open("r", encoding="utf-8") as handle:
                return json.load(handle)

        bible = copy.deepcopy(DEFAULT_BIBLE)
        self.file_path.write_text(json.dumps(bible, ensure_ascii=False, indent=2), encoding="utf-8")
        return bible

    def save(self, bible: dict[str, Any] | None = None) -> None:
        if bible is not None:
            self.bible = bible
        assert self.bible is not None
        self.file_path.write_text(json.dumps(self.bible, ensure_ascii=False, indent=2), encoding="utf-8")

    def evolve(self, updates: dict[str, Any]) -> None:
        self.evolvable_layer.update(updates)
        self.save()

    def add_community_reflection(self, reflection: dict[str, Any]) -> None:
        assert self.bible is not None
        evolvable = self.bible.setdefault("evolvable_layer", {})
        contributions = evolvable.setdefault("community_contributions", [])
        contributions.append(
            {
                "ts": datetime.now().isoformat(),
                "reflection": reflection.get("reflection"),
                "key_lesson": reflection.get("key_lesson"),
                "suggested_update": reflection.get("suggested_bible_update", {}),
            }
        )
        self.save()

    def evolve_from_community(self) -> dict[str, Any]:
        assert self.bible is not None
        contributions = self.evolvable_layer.get("community_contributions", [])
        if len(contributions) > 5:
            self.evolvable_layer["last_reflection"] = datetime.now().isoformat()
            self.save()
        return self.bible

    def export_public_bible(self) -> dict[str, Any]:
        assert self.bible is not None
        public = copy.deepcopy(self.bible)
        expose_sacred = os.getenv("LUMINA_BIBLE_EXPOSE_SACRED_CORE", "false").lower() == "true"
        if not expose_sacred:
            public["sacred_core"] = "<private: set LUMINA_BIBLE_EXPOSE_SACRED_CORE=true to expose>"
        return public

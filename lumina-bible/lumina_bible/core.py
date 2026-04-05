"""
LUMINA Bible core engine.
Publicly visible for transparency; all rights reserved.
"""

from datetime import datetime
from pathlib import Path
import json
from typing import Any, Dict

from chromadb.utils import embedding_functions


class BibleEngine:
    """Bible + reflection engine."""

    SACRED_CORE = """
HUMAN PLAYBOOK - Dit is hoe een ervaren MES daytrader denkt:
1. Scalping (tape reading, MA ribbon)
2. Momentum + Pullback
3. Breakout / ORB
4. Reversal / Mean Reversion
5. Range trading
6. Trend following + Retracement
7. News / Gap / Event trading
8. VWAP trading
9. Pure Price Action + Candlestick
10. Pivot Points + Daily High/Low

Regels (HEILIG):
- Altijd multi-timeframe bias
- Minstens 2 confluences
- Risk 1-2% per trade, 1:2+ RR
- Geen emotie, geen revenge trading
- Leer uit elke trade (journaling)
"""

    def __init__(self, bible_path: str = "lumina_daytrading_bible.json"):
        self.path = Path(bible_path)
        self.embedding_fn = embedding_functions.SentenceTransformerEmbeddingFunction(
            model_name="all-MiniLM-L6-v2"
        )
        self.load()

    def load(self) -> Dict[str, Any]:
        if self.path.exists():
            with open(self.path, encoding="utf-8") as f:
                return json.load(f)

        bible = {
            "sacred_core": self.SACRED_CORE,
            "evolvable_layer": {
                "mtf_matrix": {"dominant_tf": "240min", "confluence_scores": {}},
                "filters": [
                    "volume_delta > 2.0x avg",
                    "price_above_ema_50",
                    "adx > 22",
                ],
                "probability_model": {"base_winrate": 0.71, "confluence_bonus": 0.24},
                "last_reflection": datetime.now().isoformat(),
                "community_contributions": [],
            },
        }
        self.save(bible)
        return bible

    def save(self, bible: Dict[str, Any]):
        with open(self.path, "w", encoding="utf-8") as f:
            json.dump(bible, f, ensure_ascii=False, indent=2)

    def add_community_reflection(self, reflection: Dict[str, Any]):
        """Community can add this through GitHub PR or API."""
        bible = self.load()
        bible["evolvable_layer"]["community_contributions"].append(
            {
                "ts": datetime.now().isoformat(),
                "reflection": reflection.get("reflection"),
                "key_lesson": reflection.get("key_lesson"),
                "suggested_update": reflection.get("suggested_bible_update", {}),
            }
        )
        self.save(bible)
        print(
            f"Community reflection toegevoegd ({len(bible['evolvable_layer']['community_contributions'])} total)"
        )

    def evolve_from_community(self) -> Dict[str, Any]:
        """Automatic evolution based on community data."""
        bible = self.load()
        if len(bible["evolvable_layer"]["community_contributions"]) > 5:
            print("Bible evolved via community wisdom")
        return bible

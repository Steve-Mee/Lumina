from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from typing import Any

import pandas as pd

from .lumina_engine import LuminaEngine


@dataclass(slots=True)
class MemoryService:
    """Owns vector-memory persistence and world-model updates."""

    engine: LuminaEngine

    def __post_init__(self) -> None:
        if self.engine is None:
            raise ValueError("MemoryService requires a LuminaEngine")

    def _app(self):
        if self.engine.app is None:
            raise RuntimeError("LuminaEngine is not bound to runtime app")
        return self.engine.app

    def store_experience_to_vector_db(self, context: str, metadata: dict[str, Any]) -> None:
        app = self._app()
        collection = getattr(app, "collection", None)
        if collection is None:
            return
        try:
            collection.add(documents=[context], metadatas=[metadata], ids=[datetime.now().isoformat()])
        except Exception as exc:
            app.logger.error(f"Vector DB store error: {exc}")

    def retrieve_relevant_experiences(self, query: str, n_results: int = 3) -> str:
        app = self._app()
        collection = getattr(app, "collection", None)
        if collection is None:
            return "Vector memory niet beschikbaar."
        try:
            results = collection.query(query_texts=[query], n_results=n_results)
            documents = results.get("documents")
            metadatas = results.get("metadatas")
            if not documents or not metadatas or not documents[0] or not metadatas[0]:
                return "Geen relevante eerdere ervaringen gevonden."

            experiences = []
            for doc, meta in zip(documents[0], metadatas[0]):
                experiences.append(f"[{meta.get('date','')}] {doc} -> {meta.get('outcome','')}")
            return "\n".join(experiences)
        except Exception as exc:
            app.logger.error(f"Vector DB retrieve error: {exc}")
            return "Vector memory niet beschikbaar."

    def update_world_model(self, df: pd.DataFrame, regime: str, pa_summary: str) -> dict[str, Any]:
        app = self._app()
        world_model = self.engine.world_model or {
            "macro": {"vix": 18.5, "dxy": 103.2, "ten_year_yield": 4.15, "news_sentiment": "neutral"},
            "micro": {"regime": "NEUTRAL", "orderflow_bias": "balanced", "volume_profile": "fair_value", "last_update": None},
        }

        world_model["micro"]["regime"] = regime
        world_model["micro"]["orderflow_bias"] = "bullish" if df["close"].iloc[-1] > df["close"].iloc[-20:].mean() else "bearish"
        world_model["micro"]["volume_profile"] = "high_volume_node" if df["volume"].iloc[-1] > df["volume"].iloc[-20:].mean() * 1.8 else "fair_value"
        world_model["micro"]["last_update"] = datetime.now().isoformat()

        if regime == "TRENDING":
            world_model["macro"]["vix"] = max(12, world_model["macro"]["vix"] - 0.3)
        elif regime == "VOLATILE":
            world_model["macro"]["vix"] = min(35, world_model["macro"]["vix"] + 0.8)

        self.engine.world_model = world_model
        self.store_experience_to_vector_db(
            context=f"World Model Update: Regime {regime} | VIX {world_model['macro']['vix']:.1f} | DXY {world_model['macro']['dxy']:.1f}",
            metadata={"type": "world_model", "date": datetime.now().isoformat()},
        )
        print(f"[{datetime.now().strftime('%H:%M:%S')}] 🌍 World Model geüpdatet -> Regime: {regime} | VIX: {world_model['macro']['vix']:.1f}")
        return world_model

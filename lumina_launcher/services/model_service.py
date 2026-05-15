"""
LUMINA Services - Model Service
Wrapper around ModelCatalog for clean model management.
"""

from __future__ import annotations

from pathlib import Path

from lumina_core.engine.model_catalog import ModelCatalog, ModelDescriptor


class ModelService:
    def __init__(self, catalog_path: Path):
        self.catalog = ModelCatalog(catalog_path)
        self._current_key: str | None = None

    def get_catalog(self) -> ModelCatalog:
        return self.catalog

    def get_all_models(self) -> list[ModelDescriptor]:
        return self.catalog.models()

    def get_model(self, key: str) -> ModelDescriptor | None:
        return self.catalog.get(key)

    def get_recommended(self, ram_gb: float, gpu_vram_gb: float, vllm_supported: bool) -> ModelDescriptor:
        return self.catalog.recommended_for(
            ram_gb=ram_gb,
            gpu_vram_gb=gpu_vram_gb,
            vllm_supported=vllm_supported,
        )

    def get_upgrade_targets(self, current_key: str) -> list[ModelDescriptor]:
        return self.catalog.upgrade_targets(current_key)

    def get_installed_ollama_models(self) -> list[str]:
        return ModelCatalog.installed_ollama_models()

    def set_current_model(self, key: str) -> None:
        self._current_key = key

    def get_current_model(self) -> ModelDescriptor | None:
        if self._current_key:
            return self.catalog.get(self._current_key)
        return None

    def save_state(self, state_path: Path, current_key: str) -> None:
        state_path.parent.mkdir(parents=True, exist_ok=True)
        import json
        payload = {
            "catalog_version": self.catalog.version(),
            "current_model_key": current_key,
        }
        state_path.write_text(json.dumps(payload, indent=2), encoding="utf-8")

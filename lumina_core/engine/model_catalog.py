from __future__ import annotations

import json
import shutil
import subprocess
from dataclasses import dataclass
from pathlib import Path
from typing import Any


@dataclass(slots=True)
class ModelDescriptor:
    key: str
    display_name: str
    family: str
    ollama_tag: str
    parameter_size_b: float
    vram_min_gb: float
    ram_min_gb: float
    recommended_tier: str
    recommended_provider: str
    tested_by_lumina: bool
    upgrade_notes: str
    supports_unsloth: bool
    context_length: int


class ModelCatalog:
    def __init__(self, catalog_path: Path | None = None):
        self.catalog_path = catalog_path or Path("lumina_model_catalog.json")
        self.payload = self._load()

    def _load(self) -> dict[str, Any]:
        if not self.catalog_path.exists():
            return {"catalog_version": "0", "models": {}, "upgrade_path": {}}
        return json.loads(self.catalog_path.read_text(encoding="utf-8"))

    def version(self) -> str:
        return str(self.payload.get("catalog_version", "0"))

    def models(self) -> list[ModelDescriptor]:
        items = self.payload.get("models", {})
        descriptors: list[ModelDescriptor] = []
        if not isinstance(items, dict):
            return descriptors
        for key, raw in items.items():
            if not isinstance(raw, dict):
                continue
            descriptors.append(
                ModelDescriptor(
                    key=key,
                    display_name=str(raw.get("display_name", key)),
                    family=str(raw.get("family", "qwen3.5")),
                    ollama_tag=str(raw.get("ollama_tag", key)),
                    parameter_size_b=float(raw.get("parameter_size_b", 0.0)),
                    vram_min_gb=float(raw.get("vram_min_gb", 0.0)),
                    ram_min_gb=float(raw.get("ram_min_gb", 0.0)),
                    recommended_tier=str(raw.get("recommended_tier", "light")),
                    recommended_provider=str(raw.get("recommended_provider", "ollama")),
                    tested_by_lumina=bool(raw.get("tested_by_lumina", False)),
                    upgrade_notes=str(raw.get("upgrade_notes", "")),
                    supports_unsloth=bool(raw.get("supports_unsloth", False)),
                    context_length=int(raw.get("context_length", 8192)),
                )
            )
        return descriptors

    def get(self, key: str) -> ModelDescriptor | None:
        for descriptor in self.models():
            if descriptor.key == key:
                return descriptor
        return None

    def recommended_for(self, *, ram_gb: float, gpu_vram_gb: float, vllm_supported: bool) -> ModelDescriptor:
        candidates = self.models()
        compatible = [
            model
            for model in candidates
            if ram_gb >= model.ram_min_gb and gpu_vram_gb >= model.vram_min_gb
        ]
        if vllm_supported:
            preferred = [model for model in compatible if model.recommended_provider == "vllm"]
            if preferred:
                return max(preferred, key=lambda item: item.parameter_size_b)
        if compatible:
            return max(compatible, key=lambda item: item.parameter_size_b)
        return min(candidates, key=lambda item: item.parameter_size_b)

    def upgrade_targets(self, current_key: str) -> list[ModelDescriptor]:
        upgrade_path = self.payload.get("upgrade_path", {})
        raw_targets = upgrade_path.get(current_key, []) if isinstance(upgrade_path, dict) else []
        targets: list[ModelDescriptor] = []
        for key in raw_targets:
            descriptor = self.get(str(key))
            if descriptor is not None:
                targets.append(descriptor)
        return targets

    @staticmethod
    def installed_ollama_models() -> list[str]:
        if shutil.which("ollama") is None:
            return []
        try:
            completed = subprocess.run(
                ["ollama", "list"],
                capture_output=True,
                text=True,
                timeout=8,
                check=False,
            )
        except Exception:
            return []
        if completed.returncode != 0:
            return []
        lines = [line.strip() for line in completed.stdout.splitlines() if line.strip()]
        if len(lines) <= 1:
            return []
        tags: list[str] = []
        for line in lines[1:]:
            first = line.split()[0].strip()
            if first:
                tags.append(first)
        return tags
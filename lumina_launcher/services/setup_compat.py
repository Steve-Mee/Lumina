"""Re-exported deps for smart_setup monkeypatch compatibility in tests."""

from __future__ import annotations

import shutil
import subprocess

from lumina_core.engine.hardware_inspector import HardwareInspector
from lumina_core.engine.model_catalog import ModelCatalog

__all__ = ["HardwareInspector", "ModelCatalog", "shutil", "subprocess"]

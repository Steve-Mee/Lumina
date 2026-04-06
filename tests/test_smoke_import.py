import importlib.util
import os
import sys
from pathlib import Path


def _load_oop_entrypoint_module():
    module_path = Path(__file__).resolve().parents[1] / "lumina_v45.1.1.py"
    spec = importlib.util.spec_from_file_location("lumina_v45_1_1", module_path)
    if spec is None or spec.loader is None:
        raise RuntimeError("Unable to load lumina_v45.1.1.py")
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def test_smoke_import_oop_entrypoint_module():
    # Ensure import does not hard-exit when token is missing.
    os.environ.pop("CROSSTRADE_TOKEN", None)
    module = _load_oop_entrypoint_module()
    assert hasattr(module, "get_container")
    assert hasattr(module, "get_public_api")
    assert hasattr(module, "main")

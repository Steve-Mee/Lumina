import importlib.util
import sys
from pathlib import Path
from types import SimpleNamespace


def _load_oop_entrypoint_module():
    module_path = Path(__file__).resolve().parents[1] / "lumina_v45.1.1.py"
    spec = importlib.util.spec_from_file_location("lumina_v45_1_1_regression", module_path)
    if spec is None or spec.loader is None:
        raise RuntimeError("Unable to load lumina_v45.1.1.py")
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def test_get_public_api_delegates_to_bootstrap_factory(monkeypatch):
    module = _load_oop_entrypoint_module()
    expected = {"k": object()}

    dummy_container = SimpleNamespace()
    monkeypatch.setattr(module, "get_container", lambda: dummy_container)
    monkeypatch.setattr(module, "create_public_api", lambda c: expected if c is dummy_container else {})

    assert module.get_public_api() is expected


def test_get_container_is_singleton_within_module(monkeypatch):
    module = _load_oop_entrypoint_module()
    module.get_container.cache_clear()

    created = []

    def _factory():
        obj = SimpleNamespace(marker=len(created) + 1)
        created.append(obj)
        return obj

    monkeypatch.setattr(module, "create_application_container", _factory)

    first = module.get_container()
    second = module.get_container()

    assert first is second
    assert len(created) == 1
    module.get_container.cache_clear()


def test_legacy_bridge_unknown_name_raises_attribute_error(monkeypatch):
    module = _load_oop_entrypoint_module()
    monkeypatch.setattr(module, "get_container", lambda: SimpleNamespace())

    try:
        _ = module.NOT_A_REAL_SYMBOL
        raise AssertionError("Unknown legacy name should raise AttributeError")
    except AttributeError:
        pass

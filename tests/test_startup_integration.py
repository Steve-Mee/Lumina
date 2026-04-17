import importlib.util
import sys
from pathlib import Path
from types import SimpleNamespace


def _load_oop_entrypoint_module():
    module_path = Path(__file__).resolve().parents[1] / "lumina_runtime.py"
    spec = importlib.util.spec_from_file_location("lumina_runtime_bootstrap", module_path)
    if spec is None or spec.loader is None:
        raise RuntimeError("Unable to load lumina_runtime.py")
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def test_main_calls_bootstrap_then_forever_loop(monkeypatch):
    module = _load_oop_entrypoint_module()
    calls: list[str] = []

    dummy_container = SimpleNamespace(
        config=SimpleNamespace(trade_mode="paper", use_human_main_loop=False),
        swarm_symbols=["MNQ"],
        analysis_service=SimpleNamespace(run_main_loop=lambda: None),
        operations_service=SimpleNamespace(run_forever_loop=lambda: calls.append("run_forever_loop")),
    )

    monkeypatch.setattr(module, "get_container", lambda: dummy_container)
    monkeypatch.setattr(module, "bootstrap_runtime", lambda container: calls.append("bootstrap_runtime"))

    module.main()

    assert calls == ["bootstrap_runtime", "run_forever_loop"]


def test_legacy_symbol_bridge_maps_to_container_attributes(monkeypatch):
    module = _load_oop_entrypoint_module()

    dummy_container = SimpleNamespace(
        config=object(),
        engine=object(),
        analysis_service=object(),
    )
    monkeypatch.setattr(module, "get_container", lambda: dummy_container)

    assert module.CONFIG is dummy_container.config
    assert module.ENGINE is dummy_container.engine
    assert module.ANALYSIS_SERVICE is dummy_container.analysis_service

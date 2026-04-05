import importlib.util
import sys
from pathlib import Path


def _load_oop_entrypoint_module():
    module_path = Path(__file__).resolve().parents[1] / "lumina_v45.1.1.py"
    spec = importlib.util.spec_from_file_location("lumina_v45_1_1_bootstrap", module_path)
    if spec is None or spec.loader is None:
        raise RuntimeError("Unable to load lumina_v45.1.1.py")
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def test_bootstrap_runtime_calls_expected_startup_steps(monkeypatch):
    module = _load_oop_entrypoint_module()
    calls = []

    monkeypatch.setattr(module, "validate_runtime_config", lambda: True)

    def _load_historical_ohlc(self, days_back=3, limit=5000):
        calls.append(("load_historical_ohlc", days_back, limit))

    monkeypatch.setattr(type(module.MARKET_DATA_SERVICE), "load_historical_ohlc", _load_historical_ohlc)

    def _start_runtime_services(**kwargs):
        calls.append(("start_runtime_services", sorted(kwargs.keys())))

    monkeypatch.setattr(module, "start_runtime_services", _start_runtime_services)

    module.bootstrap_runtime()

    assert calls[0] == ("load_historical_ohlc", 3, 5000)
    assert calls[1][0] == "start_runtime_services"
    assert "start_daemon_fn" in calls[1][1]
    assert "supervisor_loop_fn" in calls[1][1]


def test_bootstrap_runtime_exits_when_config_invalid(monkeypatch):
    module = _load_oop_entrypoint_module()
    monkeypatch.setattr(module, "validate_runtime_config", lambda: False)

    try:
        module.bootstrap_runtime()
        raise AssertionError("bootstrap_runtime should raise SystemExit when config is invalid")
    except SystemExit as exc:
        assert exc.code == 1

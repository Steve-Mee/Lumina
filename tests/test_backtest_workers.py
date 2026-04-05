from lumina_core import backtest_workers


def test_backtest_workers_exports_expected_callables():
    assert callable(backtest_workers.run_backtest_on_snapshot)
    assert callable(backtest_workers.auto_backtester_daemon)

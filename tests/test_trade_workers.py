from lumina_core import trade_workers


def test_trade_workers_exports_expected_callables():
    assert callable(trade_workers.reflect_on_trade)
    assert callable(trade_workers.process_user_feedback)
    assert callable(trade_workers.dna_rewrite_daemon)

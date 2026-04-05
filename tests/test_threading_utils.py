from lumina_core.threading_utils import start_daemon


def test_start_daemon_runs_target():
    marker = {"ok": False}

    def _target():
        marker["ok"] = True

    t = start_daemon(_target, name="test-daemon")
    t.join(timeout=1.0)
    assert marker["ok"] is True
    assert t.daemon is True

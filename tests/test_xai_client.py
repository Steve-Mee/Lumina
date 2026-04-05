from unittest.mock import Mock, patch

from lumina_core.xai_client import post_xai_chat


class _Resp:
    def __init__(self, code):
        self.status_code = code


def test_xai_client_uses_rate_limit_callback():
    logger = Mock()
    on_rate_limited = Mock()

    with patch("lumina_core.xai_client.requests.post", side_effect=[_Resp(429), _Resp(200)]):
        r = post_xai_chat(
            payload={"model": "x", "messages": []},
            xai_key="k",
            logger=logger,
            timeout=1,
            max_retries=1,
            on_rate_limited=on_rate_limited,
            context="test_rl",
        )

    assert r is not None
    assert r.status_code == 200
    on_rate_limited.assert_called_once()


def test_xai_client_returns_none_when_key_missing():
    logger = Mock()
    r = post_xai_chat(payload={}, xai_key=None, logger=logger, context="missing_key")
    assert r is None
    assert logger.error.called

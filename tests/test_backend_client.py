"""
Tests voor BackendClient (met mocking).
"""

from unittest.mock import AsyncMock, patch

import pytest

from lumina_launcher.services.backend_client import BackendClient


@pytest.mark.unit
def test_get_leaderboard_success() -> None:
    client = BackendClient()
    with patch.object(client, "_sync_request", return_value={"leaderboard": [{"name": "Test", "pnl": 1234}]}):
        result = client.get_leaderboard()
        assert "leaderboard" in result
        assert len(result["leaderboard"]) == 1


@pytest.mark.unit
def test_get_global_wisdom_error() -> None:
    client = BackendClient()
    with patch.object(client, "_sync_request", return_value={"error": "Backend unavailable"}):
        result = client.get_global_wisdom()
        assert "error" in result


@pytest.mark.asyncio
async def test_cached_leaderboard() -> None:
    client = BackendClient()
    with patch.object(client, "get_leaderboard", return_value={"leaderboard": []}) as mock_get:
        result1 = await client.get_leaderboard_cached(ttl_seconds=60)
        result2 = await client.get_leaderboard_cached(ttl_seconds=60)
        assert result1 == result2
        assert mock_get.call_count == 1


@pytest.mark.unit
def test_get_leaderboard_sync_delegates_to_sync_request() -> None:
    client = BackendClient(base_url="http://stub")
    with patch.object(client, "_cached_sync_get", return_value={"leaderboard": [{"x": 1}]}) as m:
        out = client.get_leaderboard_sync()
    m.assert_called_once_with("leaderboard_sync", "/leaderboard", ttl_seconds=10)
    assert out["leaderboard"][0]["x"] == 1


@pytest.mark.unit
def test_get_global_wisdom_sync_delegates() -> None:
    client = BackendClient(base_url="http://stub")
    with patch.object(client, "_cached_sync_get", return_value={"top_bibles": []}) as m:
        out = client.get_global_wisdom_sync()
    m.assert_called_once_with("global_wisdom_sync", "/global_wisdom", ttl_seconds=15)
    assert out["top_bibles"] == []


@pytest.mark.asyncio
async def test_get_leaderboard_async_uses_request() -> None:
    client = BackendClient()
    with patch.object(client, "_request", new_callable=AsyncMock) as mock_request:
        mock_request.return_value = {"leaderboard": []}
        result = await client.get_leaderboard_async()
        assert result == {"leaderboard": []}
        mock_request.assert_called_once_with("GET", "/leaderboard")

"""
Tests voor BackendClient (met mocking).
"""

from unittest.mock import AsyncMock, patch

import pytest

from services.backend_client import BackendClient


@pytest.mark.asyncio
async def test_get_leaderboard_success():
    client = BackendClient()

    with patch.object(client, "_request", new_callable=AsyncMock) as mock_request:
        mock_request.return_value = {"leaderboard": [{"name": "Test", "pnl": 1234}]}
        result = await client.get_leaderboard()

        assert "leaderboard" in result
        assert len(result["leaderboard"]) == 1


@pytest.mark.asyncio
async def test_get_global_wisdom_error():
    client = BackendClient()

    with patch.object(client, "_request", new_callable=AsyncMock) as mock_request:
        mock_request.return_value = {"error": "Backend unavailable"}
        result = await client.get_global_wisdom()

        assert "error" in result


@pytest.mark.asyncio
async def test_cached_leaderboard():
    client = BackendClient()
    with patch.object(client, "get_leaderboard", new_callable=AsyncMock) as mock_get:
        mock_get.return_value = {"leaderboard": []}
        result1 = await client.get_leaderboard_cached(ttl_seconds=60)
        result2 = await client.get_leaderboard_cached(ttl_seconds=60)
        assert result1 == result2
        # Should only call once due to cache
        assert mock_get.call_count == 1

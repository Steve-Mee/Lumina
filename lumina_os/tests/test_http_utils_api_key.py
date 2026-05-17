from __future__ import annotations

from pathlib import Path

import pytest

from lumina_os.frontend import http_utils as http


@pytest.fixture(autouse=True)
def _clear_dotenv_cache() -> None:
    http._read_repo_dotenv.cache_clear()
    yield
    http._read_repo_dotenv.cache_clear()


def test_resolve_dashboard_api_key_reads_repo_dotenv(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    (tmp_path / "config.yaml").write_text("mode: sim\n", encoding="utf-8")
    (tmp_path / "lumina_os").mkdir()
    (tmp_path / ".env").write_text("LUMINA_ADMIN_API_KEY=from-dotenv-key\n", encoding="utf-8")
    monkeypatch.chdir(tmp_path)
    monkeypatch.delenv("LUMINA_ADMIN_API_KEY", raising=False)
    monkeypatch.delenv("LUMINA_BACKEND_API_KEY", raising=False)
    monkeypatch.delenv("LUMINA_DASHBOARD_API_KEY", raising=False)
    monkeypatch.delenv("X_API_KEY", raising=False)

    assert http.resolve_dashboard_api_key() == "from-dotenv-key"


def test_resolve_dashboard_api_key_prefers_explicit() -> None:
    assert http.resolve_dashboard_api_key("explicit-key") == "explicit-key"

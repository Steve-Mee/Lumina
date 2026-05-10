from __future__ import annotations

import pytest

from lumina_core.engine.ollama_model_resolve import resolve_ollama_model_tag


@pytest.mark.parametrize(
    ("requested", "installed", "expected"),
    [
        ("qwen3.5:4b", ["qwen3.5:9b", "qwen2.5:7b"], "qwen3.5:9b"),
        ("Qwen3.5:9b", ["qwen3.5:9b"], "qwen3.5:9b"),
        ("llama3:8b", ["llama3:latest"], "llama3:latest"),
        ("missing-X", ["aaa:latest"], "aaa:latest"),
    ],
)
def test_resolve_ollama_model_tag_prefers_family_match(requested: str, installed: list[str], expected: str) -> None:
    assert resolve_ollama_model_tag(requested, installed) == expected


def test_resolve_exact_when_present(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("LUMINA_OLLAMA_STRICT_MODEL", raising=False)
    installed = ["qwen3.5:9b", "qwen2.5:7b"]
    assert resolve_ollama_model_tag("qwen2.5:7b", installed) == "qwen2.5:7b"


def test_resolve_strict_env_skips_alias(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("LUMINA_OLLAMA_STRICT_MODEL", "1")
    installed = ["qwen3.5:9b"]
    assert resolve_ollama_model_tag("qwen3.5:4b", installed) == "qwen3.5:4b"

from __future__ import annotations

import pytest

from lumina_core.evolution.strategy_generator import StrategyGenerator


def test_strategy_generator_compile_and_validate_accepts_safe_code() -> None:
    generator = StrategyGenerator()
    code = (
        "def generated_strategy(context: dict) -> dict:\n"
        "    \"\"\"Safe strategy function.\"\"\"\n"
        "    close = list(context.get('close', []) or [])\n"
        "    if len(close) < 2:\n"
        "        return {'name': 'safe', 'regime_focus': 'neutral', 'signal_bias': 'neutral', 'confidence': 0.0, 'rules': ['insufficient_history']}\n"
        "    return {'name': 'safe', 'regime_focus': 'trending', 'signal_bias': 'buy', 'confidence': 0.62, 'rules': ['momentum']}\n"
    )

    result = generator.compile_and_validate(code)

    assert result.function_name == "generated_strategy"
    assert result.metadata["regime_focus"] == "trending"


def test_strategy_generator_compile_and_validate_rejects_imports() -> None:
    generator = StrategyGenerator()
    code = "import os\ndef generated_strategy(context):\n    return {'name': 'bad'}\n"

    with pytest.raises(ValueError, match="generated_strategy_unsafe"):
        generator.compile_and_validate(code)


def test_strategy_generator_generate_new_strategy_falls_back_to_template(monkeypatch: pytest.MonkeyPatch) -> None:
    generator = StrategyGenerator()
    monkeypatch.setattr(generator, "_generate_with_vllm", lambda **_kwargs: None)
    monkeypatch.setattr(generator, "_generate_with_ollama", lambda **_kwargs: None)

    code = generator.generate_new_strategy("volatility squeeze breakout with trend filter")

    assert "def generated_strategy(context: dict) -> dict" in code

from __future__ import annotations

from pathlib import Path


def test_tauri_birth_phase_shows_ppo_progress() -> None:
    root = Path(__file__).resolve().parents[1]
    birth_src = (root / "tauri-app" / "src" / "components" / "birth" / "BirthPhaseScreen.tsx").read_text(
        encoding="utf-8"
    )
    assert "ppo" in birth_src.lower() or "PPO" in birth_src
    assert "BirthPhaseScreen" in birth_src or "export function BirthPhaseScreen" in birth_src


def test_tauri_birth_phase_model_tracks_ppo_fields() -> None:
    root = Path(__file__).resolve().parents[1]
    # ppo progress extraction logic lives in the birth/ split (post frontend refactor)
    model_src = (root / "tauri-app" / "src" / "lib" / "birth" / "birthProgressExtract.ts").read_text(encoding="utf-8")
    assert "ppo" in model_src.lower()
    assert "extractPpoProgress" in model_src

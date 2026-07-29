from __future__ import annotations

from pathlib import Path


def test_tauri_birth_phase_shows_ppo_progress() -> None:
    root = Path(__file__).resolve().parents[1]
    # PPO HUD lives in Mission Control / metrics strip after birth UI split.
    surfaces = [
        root / "tauri-app" / "src" / "components" / "birth" / "BirthPhaseScreen.tsx",
        root / "tauri-app" / "src" / "components" / "birth" / "BirthMissionControl.tsx",
        root / "tauri-app" / "src" / "components" / "birth" / "BirthMetricsStrip.tsx",
    ]
    combined = "\n".join(p.read_text(encoding="utf-8") for p in surfaces if p.exists())
    assert "ppo" in combined.lower()
    screen = surfaces[0].read_text(encoding="utf-8")
    assert "BirthPhaseScreen" in screen or "export function BirthPhaseScreen" in screen


def test_tauri_birth_phase_model_tracks_ppo_fields() -> None:
    root = Path(__file__).resolve().parents[1]
    # ppo progress extraction logic lives in the birth/ split (post frontend refactor)
    model_src = (root / "tauri-app" / "src" / "lib" / "birth" / "birthProgressExtract.ts").read_text(
        encoding="utf-8"
    )
    assert "ppo" in model_src.lower()
    assert "extractPpoProgress" in model_src

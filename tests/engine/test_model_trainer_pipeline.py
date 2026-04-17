from __future__ import annotations

import json
from pathlib import Path

from lumina_core.engine.model_trainer import ModelTrainer


def test_model_trainer_builds_dataset_preview_from_thought_log(monkeypatch, tmp_path: Path) -> None:
    monkeypatch.chdir(tmp_path)
    state_dir = tmp_path / "state"
    state_dir.mkdir()
    state_dir.joinpath("lumina_thought_log.jsonl").write_text(
        '{"thought": "buy the dip"}\n{"thought": "manage risk"}\n',
        encoding="utf-8",
    )

    trainer = ModelTrainer()
    output = trainer.build_training_dataset()

    lines = output.read_text(encoding="utf-8").splitlines()
    payload = json.loads(lines[0])
    assert output.exists()
    assert payload["source"] == "thought_log"
    assert "messages" in payload
    assert "text" in payload


def test_model_trainer_builds_full_pipeline_commands(monkeypatch, tmp_path: Path) -> None:
    monkeypatch.chdir(tmp_path)
    state_dir = tmp_path / "state"
    state_dir.mkdir()
    state_dir.joinpath("lumina_thought_log.jsonl").write_text('{"thought": "x"}\n', encoding="utf-8")
    tools_dir = tmp_path / "tools" / "llama.cpp"
    tools_dir.mkdir(parents=True)
    converter = tools_dir / "convert_hf_to_gguf.py"
    converter.write_text("print('convert')\n", encoding="utf-8")

    trainer = ModelTrainer()
    pipeline = trainer.build_full_pipeline_commands(
        base_model="qwen3.5:9b",
        output_dir=tmp_path / "state" / "unsloth-output",
        model_name="lumina-qwen-custom",
    )

    assert "--model-name" in pipeline["train"]
    assert str(converter) in pipeline["export"]
    assert pipeline["register"][0] == "ollama"
    modelfile = Path(str(pipeline["modelfile"]))
    assert modelfile.exists()
    assert "FROM" in modelfile.read_text(encoding="utf-8")


def test_model_trainer_create_export_instructions_include_export_and_register(monkeypatch, tmp_path: Path) -> None:
    monkeypatch.chdir(tmp_path)
    state_dir = tmp_path / "state"
    state_dir.mkdir()
    state_dir.joinpath("lumina_thought_log.jsonl").write_text('{"thought": "x"}\n', encoding="utf-8")

    trainer = ModelTrainer()
    instructions = trainer.create_export_instructions(base_model="qwen3.5:9b", output_dir=tmp_path / "state" / "out")

    assert any("GGUF" in item for item in instructions)
    assert any("ollama create" in item for item in instructions)


def test_model_trainer_action_gate_status_blocks_windows_export(monkeypatch, tmp_path: Path) -> None:
    monkeypatch.chdir(tmp_path)
    monkeypatch.setenv("WSL_DISTRO_NAME", "")
    monkeypatch.setattr("platform.system", lambda: "Windows")
    trainer = ModelTrainer()

    gate = trainer.action_gate_status(
        gguf_path=tmp_path / "missing.gguf",
        modelfile_path=tmp_path / "missing.Modelfile",
    )

    assert gate["linux_or_wsl2"] is False
    assert gate["can_prepare_toolchain"] is False
    assert gate["can_export"] is False
    assert gate["can_register"] is False


def test_model_trainer_action_gate_status_allows_linux_export_when_converter_exists(
    monkeypatch, tmp_path: Path
) -> None:
    monkeypatch.chdir(tmp_path)
    monkeypatch.setattr("platform.system", lambda: "Linux")
    tools_dir = tmp_path / "tools" / "llama.cpp"
    tools_dir.mkdir(parents=True)
    converter = tools_dir / "convert_hf_to_gguf.py"
    converter.write_text("print('convert')\n", encoding="utf-8")
    gguf = tmp_path / "out.gguf"
    gguf.write_text("x", encoding="utf-8")
    modelfile = tmp_path / "Modelfile"
    modelfile.write_text("FROM x\n", encoding="utf-8")
    monkeypatch.setattr("shutil.which", lambda name: "/usr/bin/ollama" if name == "ollama" else None)

    trainer = ModelTrainer()
    gate = trainer.action_gate_status(gguf_path=gguf, modelfile_path=modelfile)

    assert gate["linux_or_wsl2"] is True
    assert gate["can_prepare_toolchain"] is True
    assert gate["can_export"] is True
    assert gate["can_register"] is True

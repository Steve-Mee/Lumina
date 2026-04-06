from __future__ import annotations

import json
import os
import platform
import shutil
import subprocess
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Any


@dataclass(slots=True)
class TrainingEnvironmentReport:
    supported: bool
    platform_name: str
    cuda_available: bool
    unsloth_installed: bool
    ollama_installed: bool
    reasons: list[str]

    def to_dict(self) -> dict[str, Any]:
        return {
            "supported": self.supported,
            "platform_name": self.platform_name,
            "cuda_available": self.cuda_available,
            "unsloth_installed": self.unsloth_installed,
            "ollama_installed": self.ollama_installed,
            "reasons": self.reasons,
        }


class ModelTrainer:
    STATUS_FILE = Path("state/training_pipeline_status.json")
    MODELFILE_NAME = "Modelfile"
    LLAMA_CPP_STATUS_FILE = Path("state/llama_cpp_setup.json")

    def inspect_environment(self) -> TrainingEnvironmentReport:
        reasons: list[str] = []
        platform_name = platform.system()
        unsloth_installed = self._module_available("unsloth")
        ollama_installed = shutil.which("ollama") is not None
        cuda_available = self._cuda_available()
        supported = True

        if platform_name == "Windows":
            supported = False
            reasons.append("Unsloth fine-tuning wordt niet ondersteund op Windows native; gebruik WSL2 of Linux met CUDA.")
        if not cuda_available:
            supported = False
            reasons.append("CUDA/GPU is niet beschikbaar; LoRA/QLoRA training is daarom nu niet uitvoerbaar.")
        if not unsloth_installed:
            supported = False
            reasons.append("Unsloth is niet geinstalleerd; installeer requirements_finetune.txt in een Linux/WSL2 omgeving.")
        if not ollama_installed:
            reasons.append("Ollama is niet gevonden; export naar een lokaal runtime model kan nog niet worden afgerond.")

        report = TrainingEnvironmentReport(
            supported=supported,
            platform_name=platform_name,
            cuda_available=cuda_available,
            unsloth_installed=unsloth_installed,
            ollama_installed=ollama_installed,
            reasons=reasons,
        )
        self.STATUS_FILE.parent.mkdir(parents=True, exist_ok=True)
        self.STATUS_FILE.write_text(json.dumps(report.to_dict(), indent=2), encoding="utf-8")
        return report

    def is_linux_or_wsl2(self) -> bool:
        system = platform.system()
        if system == "Linux":
            return True
        if system != "Windows":
            return False
        return bool(os.getenv("WSL_DISTRO_NAME"))

    def action_gate_status(self, *, gguf_path: Path, modelfile_path: Path) -> dict[str, Any]:
        linux_or_wsl = self.is_linux_or_wsl2()
        toolchain = self.inspect_llama_cpp_toolchain()
        ollama_installed = shutil.which("ollama") is not None
        return {
            "linux_or_wsl2": linux_or_wsl,
            "can_prepare_toolchain": linux_or_wsl,
            "can_export": linux_or_wsl and bool(toolchain.get("converter_exists")),
            "can_register": linux_or_wsl and ollama_installed and gguf_path.exists() and modelfile_path.exists(),
            "prepare_reason": "Available" if linux_or_wsl else "Use Linux or WSL2 for llama.cpp setup.",
            "export_reason": "Available"
            if linux_or_wsl and bool(toolchain.get("converter_exists"))
            else "Export requires Linux or WSL2 plus an installed llama.cpp converter.",
            "register_reason": "Available"
            if linux_or_wsl and ollama_installed and gguf_path.exists() and modelfile_path.exists()
            else "Registration requires Linux or WSL2, Ollama, and an existing GGUF export.",
        }

    def build_training_dataset(self) -> Path:
        output_path = Path("state/finetune_dataset_preview.jsonl")
        thought_log = Path("state/lumina_thought_log.jsonl")
        log_csv = Path("logs/lumina_full_log.csv")
        examples: list[str] = []
        if thought_log.exists():
            for raw_line in thought_log.read_text(encoding="utf-8", errors="replace").splitlines()[:50]:
                text = raw_line.strip()
                if not text:
                    continue
                examples.append(
                    json.dumps(
                        {
                            "source": "thought_log",
                            "messages": [
                                {"role": "system", "content": "You are Lumina trading reasoning."},
                                {"role": "user", "content": text[:1500]},
                            ],
                            "text": f"<|system|>You are Lumina trading reasoning.<|user|>{text[:1500]}",
                        },
                        ensure_ascii=True,
                    )
                )
        elif log_csv.exists():
            header, *rows = log_csv.read_text(encoding="utf-8", errors="replace").splitlines()[:20]
            for row in rows:
                examples.append(
                    json.dumps(
                        {
                            "source": "trade_log",
                            "messages": [
                                {"role": "system", "content": "You are Lumina trading reasoning."},
                                {"role": "user", "content": row[:1500]},
                            ],
                            "text": f"<|system|>You are Lumina trading reasoning.<|user|>{row[:1500]}",
                        },
                        ensure_ascii=True,
                    )
                )
        output_path.parent.mkdir(parents=True, exist_ok=True)
        output_path.write_text("\n".join(examples) + ("\n" if examples else ""), encoding="utf-8")
        return output_path

    def build_unsloth_command(self, *, base_model: str, output_dir: Path, model_name: str = "lumina-qwen-custom") -> list[str]:
        return [
            sys.executable,
            "-m",
            "lumina_core.engine.unsloth_runner",
            "--base-model",
            base_model,
            "--dataset",
            str(self.build_training_dataset()),
            "--output-dir",
            str(output_dir),
            "--model-name",
            model_name,
            "--save-merged-16bit",
        ]

    def build_gguf_export_command(self, *, merged_model_dir: Path, output_file: Path, quantization: str = "q4_k_m") -> list[str]:
        converter = self._resolve_gguf_converter()
        if converter.suffix.lower() == ".py":
            return [sys.executable, str(converter), str(merged_model_dir), "--outfile", str(output_file), "--outtype", quantization]
        return [str(converter), str(merged_model_dir), "--outfile", str(output_file), "--outtype", quantization]

    def write_modelfile(
        self,
        *,
        output_dir: Path,
        gguf_path: Path,
        model_name: str,
        context_length: int = 16384,
        temperature: float = 0.1,
    ) -> Path:
        output_dir.mkdir(parents=True, exist_ok=True)
        modelfile = output_dir / self.MODELFILE_NAME
        modelfile.write_text(
            "\n".join(
                [
                    f'FROM "{gguf_path.as_posix()}"',
                    f"PARAMETER num_ctx {context_length}",
                    f"PARAMETER temperature {temperature}",
                    'SYSTEM "You are Lumina trading reasoning. Respond in strict JSON whenever a trade decision is requested."',
                    f'TEMPLATE "{{{{ if .System }}}}<|system|>{{{{ .System }}}}{{{{ end }}}}{{{{ if .Prompt }}}}<|user|>{{{{ .Prompt }}}}{{{{ end }}}}<|assistant|>"',
                    f'# model_name={model_name}',
                ]
            )
            + "\n",
            encoding="utf-8",
        )
        return modelfile

    def build_ollama_create_command(self, *, model_name: str, modelfile: Path) -> list[str]:
        return ["ollama", "create", model_name, "-f", str(modelfile)]

    def build_full_pipeline_commands(
        self,
        *,
        base_model: str,
        output_dir: Path,
        model_name: str,
        quantization: str = "q4_k_m",
    ) -> dict[str, list[str] | str]:
        merged_dir = output_dir / "merged-16bit"
        gguf_file = output_dir / f"{model_name}.{quantization}.gguf"
        modelfile = self.write_modelfile(output_dir=output_dir, gguf_path=gguf_file, model_name=model_name)
        return {
            "train": self.build_unsloth_command(base_model=base_model, output_dir=output_dir, model_name=model_name),
            "export": self.build_gguf_export_command(merged_model_dir=merged_dir, output_file=gguf_file, quantization=quantization),
            "register": self.build_ollama_create_command(model_name=model_name, modelfile=modelfile),
            "modelfile": str(modelfile),
            "gguf": str(gguf_file),
        }

    def inspect_llama_cpp_toolchain(self) -> dict[str, Any]:
        converter = self._resolve_gguf_converter()
        quantize = Path("tools/llama.cpp/build/bin/llama-quantize")
        status_payload: dict[str, Any] = {}
        if self.LLAMA_CPP_STATUS_FILE.exists():
            try:
                status_payload = json.loads(self.LLAMA_CPP_STATUS_FILE.read_text(encoding="utf-8"))
            except Exception:
                status_payload = {}
        return {
            "converter_exists": converter.exists(),
            "converter_path": str(converter),
            "quantize_exists": quantize.exists(),
            "quantize_path": str(quantize),
            "status": status_payload,
            "setup_command": [sys.executable, "scripts/setup_llama_cpp.py"],
            "linux_or_wsl2": self.is_linux_or_wsl2(),
        }

    def run_command(self, command: list[str], *, cwd: Path | None = None, timeout: int = 0) -> tuple[bool, str]:
        try:
            completed = subprocess.run(
                command,
                cwd=str(cwd) if cwd is not None else None,
                capture_output=True,
                text=True,
                timeout=timeout if timeout > 0 else None,
                check=False,
            )
        except Exception as exc:
            return False, str(exc)
        output = completed.stdout.strip() or completed.stderr.strip() or f"Exit code {completed.returncode}"
        return completed.returncode == 0, output

    def create_export_instructions(self, *, base_model: str, output_dir: Path) -> list[str]:
        pipeline = self.build_full_pipeline_commands(base_model=base_model, output_dir=output_dir, model_name="lumina-qwen-custom")
        return [
            "1. Installeer Linux of WSL2 met NVIDIA CUDA drivers.",
            "2. Activeer een aparte fine-tuning omgeving en voer pip install -r requirements_finetune.txt uit.",
            f"3. Genereer of verrijk de dataset in {self.build_training_dataset()}.",
            f"4. Start de training met: {' '.join(pipeline['train'])}",
            f"5. Exporteer daarna naar GGUF met: {' '.join(pipeline['export'])}",
            f"6. Registreer het model in Ollama met: {' '.join(pipeline['register'])}",
        ]

    def _resolve_gguf_converter(self) -> Path:
        candidates = [
            Path(os.getenv("LUMINA_GGUF_CONVERTER", "")).expanduser() if os.getenv("LUMINA_GGUF_CONVERTER") else None,
            Path("tools/llama.cpp/convert_hf_to_gguf.py"),
            Path("tools/llama.cpp/build/bin/llama-quantize"),
        ]
        for candidate in candidates:
            if candidate is not None and candidate.exists():
                return candidate.resolve()
        return Path("tools/llama.cpp/convert_hf_to_gguf.py").resolve()

    @staticmethod
    def _module_available(module_name: str) -> bool:
        try:
            __import__(module_name)
            return True
        except Exception:
            return False

    @staticmethod
    def _cuda_available() -> bool:
        try:
            import torch  # pyright: ignore[reportMissingImports]

            return bool(torch.cuda.is_available())
        except Exception:
            return False
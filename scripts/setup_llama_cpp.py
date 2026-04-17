from __future__ import annotations

import json
import platform
import shutil
import subprocess
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
TOOLS_DIR = ROOT / "tools"
LLAMA_CPP_DIR = TOOLS_DIR / "llama.cpp"
STATUS_FILE = ROOT / "state" / "llama_cpp_setup.json"
REPO_URL = "https://github.com/ggml-org/llama.cpp.git"


def _run(command: list[str], cwd: Path | None = None) -> tuple[bool, str]:
    try:
        completed = subprocess.run(
            command,
            cwd=str(cwd) if cwd is not None else None,
            capture_output=True,
            text=True,
            check=False,
        )
    except Exception as exc:
        return False, str(exc)
    output = completed.stdout.strip() or completed.stderr.strip() or f"Exit code {completed.returncode}"
    return completed.returncode == 0, output


def _write_status(payload: dict) -> None:
    STATUS_FILE.parent.mkdir(parents=True, exist_ok=True)
    STATUS_FILE.write_text(json.dumps(payload, indent=2), encoding="utf-8")


def main() -> int:
    system = platform.system()
    if system == "Windows":
        payload = {
            "supported": False,
            "platform": system,
            "message": "Gebruik Linux of WSL2 voor llama.cpp build en GGUF export. Windows native wordt niet ondersteund door deze setupflow.",
        }
        _write_status(payload)
        print(payload["message"])
        return 1

    if shutil.which("git") is None:
        _write_status({"supported": False, "platform": system, "message": "git is vereist voor llama.cpp setup"})
        print("git is vereist voor llama.cpp setup")
        return 1

    TOOLS_DIR.mkdir(parents=True, exist_ok=True)

    if not LLAMA_CPP_DIR.exists():
        ok, output = _run(["git", "clone", REPO_URL, str(LLAMA_CPP_DIR)])
        if not ok:
            _write_status({"supported": False, "platform": system, "message": output})
            print(output)
            return 1
    else:
        ok, output = _run(["git", "pull", "--ff-only"], cwd=LLAMA_CPP_DIR)
        if not ok:
            _write_status({"supported": False, "platform": system, "message": output})
            print(output)
            return 1

    build_dir = LLAMA_CPP_DIR / "build"
    build_dir.mkdir(parents=True, exist_ok=True)

    if shutil.which("cmake") is None:
        _write_status(
            {
                "supported": False,
                "platform": system,
                "message": "cmake is vereist voor llama.cpp build. Installeer cmake en voer het script opnieuw uit.",
            }
        )
        print("cmake is vereist voor llama.cpp build")
        return 1

    configure = ["cmake", "-S", str(LLAMA_CPP_DIR), "-B", str(build_dir), "-DGGML_CUDA=ON"]
    ok, output = _run(configure)
    if not ok:
        _write_status({"supported": False, "platform": system, "message": output, "step": "configure"})
        print(output)
        return 1

    build = ["cmake", "--build", str(build_dir), "--config", "Release", "-j"]
    ok, output = _run(build)
    status = {
        "supported": ok,
        "platform": system,
        "repo": str(LLAMA_CPP_DIR),
        "converter": str(LLAMA_CPP_DIR / "convert_hf_to_gguf.py"),
        "quantize": str(build_dir / "bin" / "llama-quantize"),
        "message": output,
    }
    _write_status(status)
    print(json.dumps(status, indent=2))
    return 0 if ok else 1


if __name__ == "__main__":
    raise SystemExit(main())

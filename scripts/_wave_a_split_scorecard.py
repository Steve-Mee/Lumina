"""Wave A PR4.3 — extract compute_stage_blocker into stage_blocker.py."""
from __future__ import annotations

from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
BIRTH = ROOT / "lumina_core" / "birth"
SRC = BIRTH / "stage_scorecard.py"


def extract(lines: list[str], start: int, end: int) -> str:
    return "".join(lines[start - 1 : end])


def main() -> None:
    text = SRC.read_text(encoding="utf-8")
    lines = text.splitlines(keepends=True)

    blocker = '''"""Stage pass blocker computation for birth scorecard UI."""
from __future__ import annotations

from lumina_core.birth.config import BirthCurriculumConfig
from lumina_core.birth.curriculum import CurriculumStage, stage1_winrate_pass_threshold


'''
    blocker += extract(lines, 596, 900)
    (BIRTH / "stage_blocker.py").write_text(blocker.rstrip() + "\n", encoding="utf-8")

    # Remove compute_stage_blocker from scorecard and add re-export import.
    # Find the function block and replace with re-export.
    start_marker = "def compute_stage_blocker(\n"
    end_marker = "\ndef build_scorecard_payload(\n"
    start_idx = text.index(start_marker)
    end_idx = text.index(end_marker)

    import_line = (
        "from lumina_core.birth.stage_blocker import compute_stage_blocker  # noqa: F401\n"
    )
    # Insert import after curriculum imports block
    needle = "from lumina_core.birth.curriculum import (\n"
    # Find end of that import
    import_end = text.index(")\n", text.index(needle)) + 2
    new_text = text[:import_end] + "\n" + import_line + text[import_end:start_idx] + text[end_idx:]

    # Update module docstring slightly
    if new_text.startswith('"""Birth curriculum stage scorecard helpers'):
        new_text = new_text.replace(
            '"""Birth curriculum stage scorecard helpers for UI transparency."""',
            '"""Birth curriculum stage scorecard helpers for UI transparency.\n\n'
            "Blocker logic: ``stage_blocker.compute_stage_blocker`` (re-exported).\n"
            '"""',
            1,
        )

    SRC.write_text(new_text, encoding="utf-8")
    print("stage_scorecard split done")
    for name in ("stage_scorecard.py", "stage_blocker.py"):
        n = len((BIRTH / name).read_text(encoding="utf-8").splitlines())
        print(f"  {name}: {n}")


if __name__ == "__main__":
    main()

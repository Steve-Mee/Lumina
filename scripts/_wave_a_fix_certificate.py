"""Fix certificate extract: rename leftover self params + monkeypatch bridges."""
from __future__ import annotations

import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
BIRTH = ROOT / "lumina_core" / "birth"


def fix_params(path: Path) -> None:
    t = path.read_text(encoding="utf-8")
    replacements = [
        ("def ensure_holdout_preflight(\n    self,", "def ensure_holdout_preflight(\n    pipeline,"),
        ("def run_certificate_remediation(\n    self,", "def run_certificate_remediation(\n    pipeline,"),
        ("def run_certificate_runway_stages(\n    self,", "def run_certificate_runway_stages(\n    pipeline,"),
        (
            "def fail_certificate_with_runway_checkpoint(\n    self,",
            "def fail_certificate_with_runway_checkpoint(\n    pipeline,",
        ),
        ("def bootstrap_runway_stage5(self,", "def bootstrap_runway_stage5(pipeline,"),
    ]
    for a, b in replacements:
        t = t.replace(a, b)
    path.write_text(t, encoding="utf-8")
    print(path.name, "params fixed")


def inject_cp_calls(path: Path, symbols: list[str]) -> None:
    t = path.read_text(encoding="utf-8")
    if "certificate_patch_bridge" not in t:
        t = t.replace(
            "from __future__ import annotations\n",
            "from __future__ import annotations\n\n"
            "from lumina_core.birth.certificate_patch_bridge import cp_attr\n",
            1,
        )
    for sym in symbols:
        # Replace call sites: word(  but not import lines containing the name without call
        # Use negative lookbehind for def _ and for "import "
        pattern = rf"(?<![.\w]){sym}\("
        repl = f'cp_attr("{sym}", {sym})('
        # Avoid double-wrapping
        t2 = []
        i = 0
        for m in re.finditer(pattern, t):
            start = m.start()
            # skip if already cp_attr wrapped: look back ~40 chars
            lookback = t[max(0, start - 40) : start]
            if f'cp_attr("{sym}"' in lookback or f"cp_attr('{sym}'" in lookback:
                continue
            # skip import from lines
            line_start = t.rfind("\n", 0, start) + 1
            line = t[line_start : t.find("\n", start)]
            if line.lstrip().startswith("from ") or line.lstrip().startswith("import "):
                continue
            t2.append((start, m.end(), repl))
        # apply from end
        for start, end, r in reversed(t2):
            t = t[:start] + r + t[end:]
    path.write_text(t, encoding="utf-8")
    print(path.name, "cp_attr wired for", symbols)


def main() -> None:
    for name in (
        "certificate_preflight.py",
        "certificate_remediation.py",
        "certificate_runway.py",
    ):
        fix_params(BIRTH / name)

    inject_cp_calls(
        BIRTH / "certificate_preflight.py",
        ["assess_split_preflight", "expand_birth_data", "enrich_ticks_with_news"],
    )
    inject_cp_calls(
        BIRTH / "certificate_remediation.py",
        [
            "expand_birth_data",
            "enrich_ticks_with_news",
            "run_policy_rollout",
            "evaluate_holdout_certificate",
        ],
    )
    inject_cp_calls(
        BIRTH / "certificate_runway.py",
        ["evaluate_holdout_certificate"],
    )

    # Also patch conftest new sites
    conf = ROOT / "tests" / "birth" / "conftest.py"
    ct = conf.read_text(encoding="utf-8")
    extra = [
        '        "lumina_core.birth.certificate_remediation.run_policy_rollout",\n',
    ]
    needle = '        "lumina_core.birth.certificate_pipeline.run_policy_rollout",\n'
    if "certificate_remediation.run_policy_rollout" not in ct and needle in ct:
        ct = ct.replace(needle, needle + extra[0])
        conf.write_text(ct, encoding="utf-8")
        print("conftest updated")

    for name in (
        "certificate_preflight.py",
        "certificate_remediation.py",
        "certificate_runway.py",
    ):
        t = (BIRTH / name).read_text(encoding="utf-8")
        assert "    self," not in t, name
        print(name, "ok lines", len(t.splitlines()))


if __name__ == "__main__":
    main()

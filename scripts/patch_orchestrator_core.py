"""Replace extracted methods in orchestrator_core.py with thin delegates (Fase 5B)."""

from __future__ import annotations

from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "lumina_core" / "evolution" / "orchestrator_core.py"

RUN_SINGLE_DELEGATE = '''    def _run_single_generation(
        self,
        *,
        generation_offset: int,
        mode: str,
        explicit_human_approval: bool,
        require_human_approval: bool,
        real_promotion_approvals: Sequence[SignedApproval] | None,
        base_metrics: dict[str, Any],
        sim_days: int,
    ) -> GenerationResult:
        from lumina_core.evolution.generation_runner import run_single_generation

        return run_single_generation(
            self,
            generation_offset=generation_offset,
            mode=mode,
            explicit_human_approval=explicit_human_approval,
            require_human_approval=require_human_approval,
            real_promotion_approvals=real_promotion_approvals,
            base_metrics=base_metrics,
            sim_days=sim_days,
        )

'''

BOOTSTRAP_DELEGATE = '''    def _bootstrap_active_dna(self, *, base_metrics: dict[str, Any]) -> PolicyDNA:
        from lumina_core.evolution.birth_gen0_bootstrap import bootstrap_active_dna

        return bootstrap_active_dna(self, base_metrics=base_metrics)

'''


def main() -> None:
    text = SRC.read_text(encoding="utf-8")
    lines = text.splitlines(keepends=True)

    # _run_single_generation: lines 393-848 (1-indexed)
    run_start = 392
    run_end = 848
    lines[run_start:run_end] = [RUN_SINGLE_DELEGATE]

    # Re-find _bootstrap_active_dna after length change
    joined = "".join(lines)
    boot_marker = "    def _bootstrap_active_dna(self"
    boot_start = joined.index(boot_marker)
    boot_line = joined[:boot_start].count("\n")
    # find end of method (next def or @staticmethod at same indent)
    rest = joined[boot_start:].splitlines(keepends=True)
    boot_end_line = boot_line
    for i, line in enumerate(rest[1:], start=1):
        if line.startswith("    def ") or line.startswith("    @staticmethod"):
            boot_end_line = boot_line + i
            break
    else:
        raise RuntimeError("_bootstrap_active_dna end not found")

    lines = joined.splitlines(keepends=True)
    lines[boot_line:boot_end_line] = [BOOTSTRAP_DELEGATE]

    out = "".join(lines)
    out = out.replace(
        "from lumina_core.birth.dna_handoff import resolve_birth_gen0_dna\n",
        "",
    )
    SRC.write_text(out, encoding="utf-8")
    print(f"Patched {SRC} -> {len(out.splitlines())} lines")


if __name__ == "__main__":
    main()
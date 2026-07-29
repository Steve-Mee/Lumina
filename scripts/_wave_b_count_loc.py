from pathlib import Path

files = [
    "lumina_core/birth/certificate_pipeline.py",
    "lumina_core/birth/certificate_evaluate.py",
    "lumina_core/birth/starship_edgescore.py",
    "lumina_core/birth/starship_edgescore_core.py",
    "lumina_core/birth/starship_edgescore_champion.py",
    "lumina_core/birth/starship_edgescore_stage1.py",
    "lumina_core/birth/starship_edgescore_stage2.py",
    "lumina_core/birth/starship_edgescore_stage3.py",
    "lumina_core/birth/plateau_terminal.py",
    "lumina_core/birth/plateau_terminal_ladder.py",
    "lumina_core/birth/plateau_terminal_traps.py",
    "lumina_core/evolution/approval_twin_bus.py",
    "lumina_core/evolution/approval_twin_bus_observe.py",
    "lumina_core/evolution/approval_twin_bus_publish.py",
    "lumina_core/evolution/approval_twin_evaluators.py",
    "lumina_core/evolution/approval_twin_eval_dna.py",
    "lumina_core/evolution/approval_twin_eval_code.py",
    "lumina_core/evolution/approval_twin_eval_shadow.py",
]
for f in files:
    p = Path(f)
    print(f"{p}: {len(p.read_text(encoding='utf-8').splitlines())}")

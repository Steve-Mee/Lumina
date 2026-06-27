# Anti-Patterns

Deze anti-patterns zijn afgeleid uit de echte geschiedenis van Lumina (refactors, resets, monolithische hotspots, legacy compat lagen, etc.). Ze zijn bedoeld als scherpe waarschuwingen, niet als vage adviezen.

## High-Risk Anti-Patterns

- **Hiding or softening risk parameters** om backtests mooier te maken.
- **Overfitting** zonder serieuze out-of-sample validatie en regime awareness.
- **Directe wijzigingen in Real mode** zonder voorafgaande validatie in SIM/Paper.
- **God files / god modules** — `lumina_launcher.py` groeide herhaaldelijk boven de 3000+ regels. `LuminaEngine` werd een monolith met verantwoordelijkheden over PnL, RL, backtesting, risk, dream state, etc.
- **Prolonged legacy compat layers** in kritieke paden (engine, risk, meta-agent). "Tijdelijk" werd vaak permanent en verhoogde regressierisico significant.
- **Tight coupling** tussen strategie en risk management.

## Process Anti-Patterns

- Kernlogica wijzigen zonder reasoning + evidence te documenteren.
- In-sample geoptimaliseerde parameters behandelen als robuust.
- Transaction costs, slippage en execution realiteit negeren in backtests.
- Complexiteit toevoegen zonder duidelijke evolutionaire meerwaarde.
- **Plan Mode omzeilen** bij significante risk- of execution-wijzigingen.
- **Frequente full state resets** als workaround (duizenden bestanden in backups/reset_* mappen) in plaats van robuuste migratiepaden.
- **Big-bang refactors** in plaats van incrementele decompositie van monoliths.
- Nieuwe complexe lagen introduceren (Blackboard, Meta Orchestrator, Neural Command Deck) terwijl oude hotspots onaangeroerd bleven.

## Cultural Anti-Patterns

- Performance chasing ten koste van truth-seeking.
- Angst voor kleine, gecontroleerde experimenten in SIM/Paper.
- Technical debt opbouwen die toekomstige evolutie moeilijker maakt.
- Op intuïtie vertrouwen in plaats van evidence.
- **Ambitieuze nieuwe systemen bouwen op vieze fundamenten** — herhaaldelijk nieuwe lagen toevoegen terwijl core monoliths en legacy debt bleven liggen.
- **God-file groei als onvermijdelijk** behandelen in plaats van vroege modulariteit af te dwingen.
- Te veel tolerantie voor "tijdelijke" compat lagen die permanent werden.
- **Reset-cultuur boven resilience** — liever state wissen dan investeren in migraties en backward-compatible evolutie van systeemstaat.

---

Deze lijst wordt actief onderhouden via het Recursive Self-Improvement Protocol. Nieuwe pijnlijke lessen uit de praktijk worden hier toegevoegd.
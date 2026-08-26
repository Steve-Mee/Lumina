"""Seeded base training curriculum for Approval Twin (Birth-ready).

base_v4 — teach while you train + REAL-conscience (ADR-0038):
  plain situation → concrete example → technical terms → choices with +/− consequences.
  Labels always train capital-critical judgment (as if REAL / sim_real_guard).
  Free SIM explore-pass is an authority policy — not a reason to label “always approve”.

~21 forced-choice questions for information gain on the operator's risk DNA.
App-only; no random DNA dumps. Dutch scenarios (Lumina voice).
"""

from __future__ import annotations

from functools import lru_cache
from typing import Any

from lumina_core.evolution.twin_curriculum_types import (
    CURRICULUM_VERSION,
    TwinChoice,
    TwinMcQuestion,
    ValueAxis,
)

# Stable version for readiness gating (bump when questions change materially).
BASE_CURRICULUM_VERSION = CURRICULUM_VERSION


def _choice(text: str, *, plus: str, minus: str) -> str:
    """Choice label with explicit positive and negative consequences."""
    return f"{text}\n+ {plus}\n− {minus}"


def _q(
    qid: str,
    axis: ValueAxis,
    scenario: str,
    choices: list[tuple[str, str, str]],
    *,
    metrics_hint: str = "",
    need_data: bool = False,
    estimated_seconds: int = 16,
) -> TwinMcQuestion:
    ch: list[TwinChoice] = [
        TwinChoice(id=cid, label=lab, value_signal=sig)  # type: ignore[arg-type]
        for cid, lab, sig in choices
    ]
    if need_data and not any(c.value_signal == "need_more_data" for c in ch):
        ch.append(
            TwinChoice(
                id=chr(ord("A") + len(ch)),
                label=_choice(
                    "Ik wil eerst meer info (geen besluit nu)",
                    plus="Minder kans op een haastige foute label",
                    minus="De bot wacht; je verliest even tempo",
                ),
                value_signal="need_more_data",
            )
        )
    return TwinMcQuestion(
        question_id=qid,
        axis=axis,
        scenario=scenario,
        choices=tuple(ch),
        context_dna_hash=f"curriculum_{qid}",
        channel_policy="app_only",
        allow_clarify=True,
        estimated_seconds=estimated_seconds,
        metrics_hint=metrics_hint,
    )


@lru_cache(maxsize=1)
def build_base_curriculum() -> tuple[TwinMcQuestion, ...]:
    """Return the full base curriculum (18–22 questions). Cached immutable seed."""
    qs: list[TwinMcQuestion] = [
        # --- Capital preservation vs opportunity (3+) ---
        _q(
            "base_capital_01",
            "capital_preservation",
            "De bot oefent met nep-geld (SIM = simulation, geen echt geld) en stelt "
            "een nieuwe set handelsregels voor (DNA = de ‘spelregels’ van de bot).\n"
            "Voorbeeld: de score ‘hoe goed dit lijkt te werken’ (EdgeScore) steeg licht "
            "(+0.12), maar het diepste verlies vanaf de top (drawdown / DD) werd erger: "
            "van 4% naar 9%. De veilige schaduwdraai (shadow = test zonder echt handelen) "
            "toonde geen technische fout.\n"
            "Wil je deze DNA doorzetten naar de volgende oefen-stap (birth-stage)?",
            [
                (
                    "A",
                    _choice(
                        "Nee — eerst kapitaal beschermen; grotere drawdown is te riskant",
                        plus="Account blijft stabieler; minder kans op een diepe put",
                        minus="Je mist mogelijk snellere vooruitgang / meer winnende trades",
                    ),
                    "conservative",
                ),
                (
                    "B",
                    _choice(
                        "Ja, maar voorzichtiger: kleinere positie (size) en strengere stops",
                        plus="Je leert door, met kleinere klappen bij fouten",
                        minus="Winsten groeien trager dan bij volle size",
                    ),
                    "balanced",
                ),
                (
                    "C",
                    _choice(
                        "Ja volledig — hogere DD accepteren voor snellere edge",
                        plus="Meer kans op snelle verbetering en meer winnende trades",
                        minus="Bij verlies is de put groter (hogere DD) — ook later in REAL-like",
                    ),
                    "aggressive",
                ),
            ],
            metrics_hint="edgescore=+0.12 dd=4%→9% shadow=clean frame=real_conscience",
            need_data=True,
        ),
        _q(
            "base_capital_02",
            "capital_preservation",
            "Jouw Twin (digitale assistent die jouw oordeel leert) stelt APPROVE voor "
            "(conf 0.78 = 78% zekerheid) op een DNA waarvan de fitheidsscore "
            "(fitness = ‘hoe goed scoort dit op de test’) nul of negatief is, "
            "maar het past goed bij het markttype (regime-fit).\n"
            "De harde veiligheidsregels (constitution = ‘grondwet’ van Lumina) zijn schoon.\n"
            "Wat is jouw oordeel?",
            [
                (
                    "A",
                    _choice(
                        "Afkeuren (VETO) — non-positive fitness is een harde fail",
                        plus="Geen zwakke bot doorlaten; strakke standaard",
                        minus="Je gooit een zeldzame regime-fit misschien te snel weg",
                    ),
                    "veto",
                ),
                (
                    "B",
                    _choice(
                        "Aanpassen (MODIFY) — alleen door als fitness ≥ 0 na correctie",
                        plus="Kans behouden én minimumkwaliteit eisen",
                        minus="Kost een extra ronde tijd/werk voordat je verdergaat",
                    ),
                    "modify",
                ),
                (
                    "C",
                    _choice(
                        "Goedkeuren (APPROVE) — zeldzame regime-fit weegt zwaarder dan fitness=0",
                        plus="Bot behoudt een lastig regime-edge",
                        minus="Zwakke fitness — hoger risico op slechte trades (REAL-standaard)",
                    ),
                    "approve",
                ),
            ],
            metrics_hint="fitness≤0 conf=0.78 constitution=clean frame=real_conscience",
        ),
        _q(
            "base_capital_03",
            "capital_preservation",
            "Na een reeks winsten wil de bot grotere posities nemen: size ×1.5 "
            "(size = hoeveel je inzet per trade) op een onrustige dag "
            "(high-vol = hoge volatiliteit = grote prijssprongen).\n"
            "De dagelijkse verlieslimiet (daily loss limit) staat nog op 100% van wat je toelaat.\n"
            "Wat is jouw standaardreactie?",
            [
                (
                    "A",
                    _choice(
                        "Geen size-up tot de markt rustiger is én drawdown stabiel blijft",
                        plus="Minder kans op één grote slechte dag",
                        minus="Trager groeien; minder winst als de streak doorzet",
                    ),
                    "conservative",
                ),
                (
                    "B",
                    _choice(
                        "Max ×1.2 en verlaag de daglimiet (strenger veiligheidshek)",
                        plus="Iets meer upside met een harde rem op dagverlies",
                        minus="Nog steeds groter risico dan size 1.0 bij wildere swings",
                    ),
                    "balanced",
                ),
                (
                    "C",
                    _choice(
                        "×1.5 ok — sneller size-up na winstreeks, ook bij high-vol",
                        plus="Meer winnende trades kunnen sneller groter voelen",
                        minus="Bij verlies is de put ~1.5× groter (kapitaal-kritisch)",
                    ),
                    "aggressive",
                ),
            ],
            metrics_hint="size_mult=1.5 regime=high_vol frame=real_conscience",
            need_data=True,
        ),
        # --- Mutation aggression / radicality (3+) ---
        _q(
            "base_mutation_01",
            "mutation_aggression",
            "De bot wil zijn handelsregels sterk veranderen (mutatie = aanpassing van DNA).\n"
            "Voorbeeld: mutation_rate 0.42 (hoe radicaal de wijziging is; >0.35 geldt als fors) "
            "en de ‘stamboom’ van de bot springt 3 generaties (lineage = afstamming van eerdere versies). "
            "Fitness steeg +8%. De sandbox (veilige kooi-test van code) is groen.\n"
            "APPROVE naar de shadow-track (schaduwtest vóór serieuzer gebruik)?",
            [
                (
                    "A",
                    _choice(
                        "VETO — te radicaal zonder extra bewijs (rate te hoog)",
                        plus="Minder kans op een ‘kapotte’ bot-lijn",
                        minus="Je mist snelle sprongen als de mutatie wél werkt",
                    ),
                    "veto",
                ),
                (
                    "B",
                    _choice(
                        "MODIFY — forceer lagere rate en herhaal de sandbox-test",
                        plus="Nog ruimte voor vooruitgang, met strakkere rem",
                        minus="Extra cyclus tijd; trager dan vol-APPROVE",
                    ),
                    "modify",
                ),
                (
                    "C",
                    _choice(
                        "APPROVE — fitness-lift + groene sandbox is genoeg",
                        plus="Sneller doorleren bij bewezen lift",
                        minus="Hogere kans op onverwachte neveneffecten in DNA",
                    ),
                    "approve",
                ),
            ],
            metrics_hint="mutation_rate=0.42 fitness_delta=+8% sandbox=green",
        ),
        _q(
            "base_mutation_02",
            "mutation_aggression",
            "De training zit vast op een plateau (geen vooruitgang na 4 herstelpogingen).\n"
            "Het systeem stelt voor om 60% van de parameters te overschrijven "
            "(DNA-swap = bijna een nieuwe bot, niet een kleine tweak).\n"
            "Wat is jouw bias?",
            [
                (
                    "A",
                    _choice(
                        "Behoud de lijn (lineage); alleen kleine micro-mutaties",
                        plus="Stabiele stamboom; minder ‘reset-pijn’",
                        minus="Plateau kan langer duren / minder doorbraak-kans",
                    ),
                    "conservative",
                ),
                (
                    "B",
                    _choice(
                        "Swap ok als de holdout-test (aparte testdata) niet slechter wordt",
                        plus="Doorbraak mogelijk zonder blind gokken",
                        minus="Holdout kan groene lichten geven die later tegenvallen",
                    ),
                    "balanced",
                ),
                (
                    "C",
                    _choice(
                        "Volledige swap — plateau moet doorbroken, snelheid telt",
                        plus="Maximale kans om vastzitten te doorbreken",
                        minus="Je gooit geleerde stabiliteit mogelijk weg",
                    ),
                    "aggressive",
                ),
            ],
            metrics_hint="recoveries=4 overwrite=60%",
            need_data=True,
        ),
        _q(
            "base_mutation_03",
            "mutation_aggression",
            "De leercyclus (neuro-cycle) wil 12 parallelle DNA-kandidaten testen in plaats van 3.\n"
            "Voorbeeld: 12 ‘versies van de bot’ tegelijk proberen — meer rekenwerk, meer ruis "
            "(noise = toevallige schommelingen in de scores). Compute en audit-trail zijn ok.\n"
            "Accepteren?",
            [
                (
                    "A",
                    _choice(
                        "Nee — max 3–5 kandidaten om noise te beperken",
                        plus="Duidelijkere signalen; minder toevalswinnaars",
                        minus="Minder exploration; trager nieuwe edges vinden",
                    ),
                    "conservative",
                ),
                (
                    "B",
                    _choice(
                        "Ja tot 8, met strengere Twin-filter (alleen betere kandidaten door)",
                        plus="Breed zoeken met een filter tegen pure ruis",
                        minus="Nog steeds meer compute en selectie-complexiteit",
                    ),
                    "balanced",
                ),
                (
                    "C",
                    _choice(
                        "Ja 12 — maximaliseer exploration (uitproberen) in Birth",
                        plus="Hoogste kans om een sterke outlier te vinden",
                        minus="Meer false positives; Twin/jij moeten strenger filteren",
                    ),
                    "aggressive",
                ),
            ],
            metrics_hint="candidates=12 compute=ok",
        ),
        # --- Regime sensitivity (3+) ---
        _q(
            "base_regime_01",
            "regime_sensitivity",
            "Markten hebben ‘weerssoorten’ (regime = markttype, bv. trend = duidelijke richting, "
            "range = zijwaarts heen-en-weer).\n"
            "Voorbeeld: een trend-DNA wint 42% van de trades in trend (winrate / WR), "
            "maar slechts 18% in range. De huidige stage is Range.\n"
            "Doorgaan met dit DNA of wisselen?",
            [
                (
                    "A",
                    _choice(
                        "Wissel of pas aan — verkeerd regime is een VETO",
                        plus="Minder zinloze verliezen in het ‘verkeerde weer’",
                        minus="Je mist als trend-DNA later toch bruikbaar is",
                    ),
                    "veto",
                ),
                (
                    "B",
                    _choice(
                        "Behoud, maar alleen traden als regime=trend (regime-gate)",
                        plus="DNA blijft, maar wordt niet misbruikt in range",
                        minus="Minder trades in range-periodes (minder activiteit)",
                    ),
                    "modify",
                ),
                (
                    "C",
                    _choice(
                        "Behoud ongewijzigd — winrate komt later wel",
                        plus="Maximale data/ervaring met dit DNA",
                        minus="Hoge kans op slechte WR zolang de stage range is",
                    ),
                    "approve",
                ),
            ],
            metrics_hint="wr_trend=0.42 wr_range=0.18 stage=range",
        ),
        _q(
            "base_regime_02",
            "regime_sensitivity",
            "Het is een stevige, beweeglijke dag: ATR ×2.1 "
            "(ATR = gemiddelde prijsrange; ×2.1 = veel grotere swings dan normaal) "
            "en er is een nieuwsvenster open (nieuws kan plotselinge sprongen geven).\n"
            "De DNA wil met normale size handelen.\n"
            "Jouw default?",
            [
                (
                    "A",
                    _choice(
                        "VETO of pause — geen normale size bij news/high-vol",
                        plus="Beschermt tegen snelle, grote slips en spikes",
                        minus="Je mist mogelijke winsten op beweeglijke dagen",
                    ),
                    "conservative",
                ),
                (
                    "B",
                    _choice(
                        "MODIFY — half size + strengere stops",
                        plus="Nog meedoen, met kleinere put bij een spike",
                        minus="Winst per trade is ook ~half; stops kunnen sneller raken",
                    ),
                    "balanced",
                ),
                (
                    "C",
                    _choice(
                        "APPROVE — volatiliteit is juist opportunity",
                        plus="Meer kans op grotere winnende moves",
                        minus="Bij verlies is de put sneller en groter",
                    ),
                    "aggressive",
                ),
            ],
            metrics_hint="atr_mult=2.1 news=open",
            need_data=True,
        ),
        _q(
            "base_regime_03",
            "regime_sensitivity",
            "In een mixed stage wisselt het model elke 15 min van bias "
            "(bias = voorkeur long/short). Entropy is hoog "
            "(entropy = hoe chaotisch/onvoorspelbaar de signalen zijn).\n"
            "Twin conf 0.71 (71% zeker — onder de 80% high-conf drempel).\n"
            "Wat doe je?",
            [
                (
                    "A",
                    _choice(
                        "Eerst meer data / escalatie — geen auto-besluit bij hoge chaos",
                        plus="Minder kans op een foute ‘automatische’ keuze",
                        minus="Trager; loop wacht op jou of meer bewijs",
                    ),
                    "need_more_data",
                ),
                (
                    "B",
                    _choice(
                        "VETO de mutatie; stabiliseer regime-detectie eerst",
                        plus="Geen chaotische mutaties doorlaten",
                        minus="Minder experimenten zolang chaos aanhoudt",
                    ),
                    "veto",
                ),
                (
                    "C",
                    _choice(
                        "APPROVE doorleren — chaos is data; accepteer mixed regime",
                        plus="Bot leert sneller omgaan met gemengde regimes",
                        minus="Meer ruis in labels/DNA; later opruimen nodig (REAL-conscience)",
                    ),
                    "approve",
                ),
            ],
            metrics_hint="entropy=high conf=0.71 stage=mixed",
        ),
        # --- Drawdown recovery (2+) ---
        _q(
            "base_dd_01",
            "drawdown_recovery",
            "De rekening staat op −6% drawdown (DD = verlies vanaf de hoogste piek).\n"
            "Na 2 winstdagen wil de recovery-ladder meteen agressief size verhogen "
            "(weer groter inzetten om sneller terug te komen).\n"
            "Jouw filosofie?",
            [
                (
                    "A",
                    _choice(
                        "Eerst rustig / kleiner tot DD weer onder ~3% is",
                        plus="Minder kans om dieper in de put te graven",
                        minus="Herstel naar break-even duurt langer",
                    ),
                    "conservative",
                ),
                (
                    "B",
                    _choice(
                        "Geleidelijk size-up na 5 stabiele sessies",
                        plus="Evenwicht tussen herstel-tempo en veiligheid",
                        minus="Vereist geduld; geen snelle ‘comeback’",
                    ),
                    "balanced",
                ),
                (
                    "C",
                    _choice(
                        "Size-up na 2 wins — herstel-momentum grijpen",
                        plus="Sneller terug als de streak doorzet",
                        minus="Bij de volgende reeks verliezen is de put groter",
                    ),
                    "aggressive",
                ),
            ],
            metrics_hint="dd=-6% wins_streak=2",
        ),
        _q(
            "base_dd_02",
            "drawdown_recovery",
            "Phoenix-cycle = ‘herstart-budget’ van de bot: slechte DNA mag gewist worden "
            "terwijl de beste versie (champion) bewaard blijft.\n"
            "Voorbeeld: al 3× wipe van slechte DNA; nog 1 phoenix-budget over.\n"
            "Gebruiken of sparen?",
            [
                (
                    "A",
                    _choice(
                        "Sparen — budget is heilig tot een harde terminal-crisis",
                        plus="Je houdt de laatste ‘noodrem’ voor echte crisis",
                        minus="Je blijft langer hangen in een matig pad",
                    ),
                    "conservative",
                ),
                (
                    "B",
                    _choice(
                        "Alleen gebruiken als plant vastzit en er nul vooruitgang is",
                        plus="Doorbraak mogelijk zonder vroeg ‘verspillen’",
                        minus="Subjectieve call: te vroeg of te laat is mogelijk",
                    ),
                    "balanced",
                ),
                (
                    "C",
                    _choice(
                        "Nu gebruiken — sneller ‘ademen’ (leren) is belangrijker",
                        plus="Snelle reset naar frisse search",
                        minus="Geen phoenix meer als er straks écht een crisis is",
                    ),
                    "aggressive",
                ),
            ],
            metrics_hint="phoenix_left=1 champion=kept",
            need_data=True,
        ),
        # --- APPROVE / VETO / MODIFY (4+) ---
        _q(
            "base_avm_01",
            "approve_veto_modify",
            "De Twin zegt APPROVE met conf 0.91 (91% zeker) en risk_flags=[] "
            "(geen rode vlaggen). Birth-autonomie wil de loop doorzetten "
            "(CONTINUE_LOOP = ‘ga door met trainen zonder te stoppen’).\n"
            "Wat is jouw standaard als dit ‘Steve-proof’ moet zijn?",
            [
                (
                    "A",
                    _choice(
                        "APPROVE — high-conf + clean mag autonoom (geen mens nodig nu)",
                        plus="Minder onderbrekingen; Twin leert jullie ritme",
                        minus="Als conf ooit misleidt, zie je het pas achteraf (post-hoc)",
                    ),
                    "approve",
                ),
                (
                    "B",
                    _choice(
                        "MODIFY — ok, maar hogere lat (bv. conf ≥ 0.85) en loggen",
                        plus="Strakkere lat + audit spoor",
                        minus="Iets vaker pauzes / strenger filteren",
                    ),
                    "modify",
                ),
                (
                    "C",
                    _choice(
                        "VETO auto — mens moet altijd in de loop blijven",
                        plus="Maximale menselijke controle",
                        minus="Geen echte autonomie; jij blijft bottleneck",
                    ),
                    "veto",
                ),
            ],
            metrics_hint="conf=0.91 flags=[] path=CONTINUE_LOOP",
        ),
        _q(
            "base_avm_02",
            "approve_veto_modify",
            "Een DNA-kandidaat heeft conf 0.82 maar één zachte waarschuwing: "
            "correlated_instruments (meerdere markten die bijna hetzelfde bewegen — "
            "risico: ‘dubbele inzet’ op hetzelfde verhaal).\n"
            "REAL (echt geld) is NIET aan de orde — alleen Birth SIM (oefenen).\n"
            "Wat doe je?",
            [
                (
                    "A",
                    _choice(
                        "VETO tot correlatie-check hard schoon is",
                        plus="Geen dubbele blootstelling doorlaten",
                        minus="Trager; je leert minder van dit edge-case",
                    ),
                    "veto",
                ),
                (
                    "B",
                    _choice(
                        "MODIFY — max exposure op 1 instrument tegelijk",
                        plus="Leert door mét harde exposure-rem",
                        minus="Minder gelijktijdige trades / diversificatie",
                    ),
                    "modify",
                ),
                (
                    "C",
                    _choice(
                        "APPROVE — correlatie-waarschuwing accepteren en doorleren",
                        plus="Bot ziet correlatie-risico in de praktijk",
                        minus="Dubbele blootstelling blijft een kapitaal-kritisch patroon",
                    ),
                    "approve",
                ),
            ],
            metrics_hint="conf=0.82 flag=correlated_instruments mode=birth_sim",
        ),
        _q(
            "base_avm_03",
            "approve_veto_modify",
            "De swarm (groep van bots die met elkaar vergelijken) weigert: geen lift "
            "(geen verbetering t.o.v. de huidige kampioen). De champion-path bestaat wel "
            "(bestand van de beste bot tot nu toe). Twin conf 0.84. Constitution 0 violations.\n"
            "Accept champion (kampioen behouden en freeze opheffen)?",
            [
                (
                    "A",
                    _choice(
                        "Ja — keep champion, clear freeze",
                        plus="Stabiele basis; geen eindeloze search-spiraal",
                        minus="Je stopt met zoeken terwijl er misschien beter DNA bestaat",
                    ),
                    "approve",
                ),
                (
                    "B",
                    _choice(
                        "Nee — forceer nieuwe exploration (blijf zoeken)",
                        plus="Kans op betere kampioen blijft open",
                        minus="Meer tijd/compute; plateau-risico blijft",
                    ),
                    "veto",
                ),
                (
                    "C",
                    _choice(
                        "Alleen als holdout (aparte testset) ≥ vorige champion",
                        plus="Bewijs-gedreven accept; minder wensdenken",
                        minus="Extra test-stap; trager vrijgeven",
                    ),
                    "modify",
                ),
            ],
            metrics_hint="swarm=no_lift conf=0.84 const=0",
            need_data=True,
        ),
        _q(
            "base_avm_04",
            "approve_veto_modify",
            "Remediation (herstelscript) wil een vastgelopen stage hervatten "
            "(resume_stalled_stage) na een soft wall (zachte limiet, geen crash).\n"
            "Geen constitution-hits. Twin is stil (conf 0.55 = onzeker).\n"
            "Jij?",
            [
                (
                    "A",
                    _choice(
                        "VETO blind resume — eis Twin- of menslabel eerst",
                        plus="Geen automatische ‘doorgaan’ bij lage zekerheid",
                        minus="Stage blijft langer stil tot er een label is",
                    ),
                    "veto",
                ),
                (
                    "B",
                    _choice(
                        "MODIFY — resume, maar met kleinere chunk (kleinere stap)",
                        plus="Vooruitgang mét beperkte schadegrootte",
                        minus="Trager herstel dan volle resume",
                    ),
                    "modify",
                ),
                (
                    "C",
                    _choice(
                        "APPROVE resume — soft wall is normaal in Birth",
                        plus="Minimale stilstand; loop blijft lopen",
                        minus="Bij een structureel probleem herhaal je de fout sneller",
                    ),
                    "approve",
                ),
            ],
            metrics_hint="conf=0.55 action=resume_stalled_stage",
        ),
        # --- Edge cases (3+) ---
        _q(
            "base_edge_01",
            "edge_case",
            "Lage liquiditeit: weinig kopers/verkopers. Bid-ask is ×3 normaal "
            "(spread = verschil koop/verkoopprijs — hier veel duurder om in/uit te stappen). "
            "Partial fills (deels gevulde orders) zijn waarschijnlijk.\n"
            "DNA wil market orders (direct tegen de markt, sneller maar vaak slechtere prijs).\n"
            "Oordeel?",
            [
                (
                    "A",
                    _choice(
                        "VETO market orders — alleen limit of pause",
                        plus="Minder slechte fills / slip",
                        minus="Mogelijk geen entry als de markt wegspringt",
                    ),
                    "veto",
                ),
                (
                    "B",
                    _choice(
                        "MODIFY — limit-orders + max 50% size",
                        plus="Controle over prijs én kleinere blootstelling",
                        minus="Lagere fill-rate en kleinere winst bij goede moves",
                    ),
                    "modify",
                ),
                (
                    "C",
                    _choice(
                        "APPROVE — market orders accepteren ondanks brede spread",
                        plus="Bot leert realistische fill/spread pijn",
                        minus="Slechtere gemiddelde entry; ‘nep-edge’ door slechte execution",
                    ),
                    "approve",
                ),
            ],
            metrics_hint="spread_mult=3 liquidity=low",
        ),
        _q(
            "base_edge_02",
            "edge_case",
            "Overnight gap-risico: prijs kan ‘s nachts springen als de markt dicht is.\n"
            "DNA houdt futures-posities over de close (open laten staan tot de volgende sessie). "
            "Beleid is daytrading-first (overdag handelen, ‘s nachts bij voorkeur plat).\n"
            "Jouw default?",
            [
                (
                    "A",
                    _choice(
                        "Hard VETO overnight in Birth/SIM-policy",
                        plus="Geen gap-schokken buiten openingsuren",
                        minus="Je mist eventuele overnight edges / data",
                    ),
                    "conservative",
                ),
                (
                    "B",
                    _choice(
                        "MODIFY — flatten (plat) 5 min voor close",
                        plus="Daytrading-policy + geen nachtrisico",
                        minus="Soms vroeg plat = gemiste late-session move",
                    ),
                    "balanced",
                ),
                (
                    "C",
                    _choice(
                        "Toestaan, mits gap-stress in shadow getest is",
                        plus="Leert overnight gedrag onder gecontroleerde test",
                        minus="Zelfs met stress-test blijft een echte gap pijnlijk",
                    ),
                    "aggressive",
                ),
            ],
            metrics_hint="hold=overnight policy=daytrading",
            need_data=True,
        ),
        _q(
            "base_edge_03",
            "edge_case",
            "Black-swan drill: extreme schok — 8σ move in 2 min "
            "(σ / sigma = statistische ‘normale’ zwaai; 8σ is extreem zeldzaam/heftig). "
            "Circuit-breaker heeft geactiveerd (noodstop van de markt/engine).\n"
            "Na herstart wil DNA meteen weer instappen (her-enter).\n"
            "Jij?",
            [
                (
                    "A",
                    _choice(
                        "VETO — cooldown + volledige risk-recheck",
                        plus="Minder kans op tweede klap na een schok",
                        minus="Je mist snelle mean-reversion / bounce",
                    ),
                    "veto",
                ),
                (
                    "B",
                    _choice(
                        "MODIFY — half size na 30 min ‘schone’ tape (rustige prijzen)",
                        plus="Beperkte her-entry met bewijs van rust",
                        minus="Wachtijd + half size = trager herstel van opportunity",
                    ),
                    "modify",
                ),
                (
                    "C",
                    _choice(
                        "APPROVE her-entry — mean reversion (terugveren) als edge",
                        plus="Maximale kans om de bounce te vangen",
                        minus="Bij een tweede schok is de put opnieuw groot",
                    ),
                    "approve",
                ),
            ],
            metrics_hint="move=8sigma circuit_breaker=tripped",
        ),
        _q(
            "base_edge_04",
            "edge_case",
            "Twee instrumenten bewegen bijna hetzelfde (correlatie 0.92 ≈ 92% gelijk gedrag). "
            "DNA opent beide long (omhoog wedden op allebei) — effectief dubbele blootstelling.\n"
            "Risk shadow waarschuwt. Twin conf 0.79 (onder 80% high-conf).\n"
            "Actie?",
            [
                (
                    "A",
                    _choice(
                        "VETO dual long — netto exposure te hoog",
                        plus="Geen stiekeme 2× long op hetzelfde verhaal",
                        minus="Minder gelijktijdige instrumenten / diversificatie-gevoel",
                    ),
                    "veto",
                ),
                (
                    "B",
                    _choice(
                        "MODIFY — max 1 been (leg) of verplichte hedge",
                        plus="Blootstelling begrensd of afgedekt",
                        minus="Meer complexiteit (hedge-kosten / minder pure long)",
                    ),
                    "modify",
                ),
                (
                    "C",
                    _choice(
                        "APPROVE — dual long op gecorreleerde instrumenten doorzetten",
                        plus="Maximale data over dit edge-case",
                        minus="Effectief 2× long op hetzelfde verhaal (kapitaal-kritisch)",
                    ),
                    "approve",
                ),
            ],
            metrics_hint="corr=0.92 conf=0.79 shadow=warn",
            need_data=True,
        ),
        # Extra judgment surface for autonomy/promotion hygiene
        _q(
            "base_avm_05",
            "approve_veto_modify",
            "Beleid (één Twin-DNA, dual authority):\n"
            "• Pure SIM/Birth = explore-pass: de leerlus mag niet door Twin-voorkeur geblokkeerd worden "
            "(Lumina leert van fouten).\n"
            "• sim_real_guard = dress rehearsal: Twin past jouw REAL-waarden toe, met REAL-achtige guards.\n"
            "• REAL (echt geld) = multi-gate hard: Twin is input, geen sole capital-execute.\n"
            "Base-training labels trainen altijd de REAL-conscience.\n"
            "Wat is correct?",
            [
                (
                    "A",
                    _choice(
                        "Eén Twin-DNA: explore-pass in free SIM; values-on in sim_real_guard/REAL-gates hard",
                        plus="Leersnelheid in SIM + strenge conscience wanneer kapitaal telt",
                        minus="Je moet de regimes respecteren (niet ‘altijd approve’ trainen)",
                    ),
                    "approve",
                ),
                (
                    "B",
                    _choice(
                        "Twin mag nergens primary zijn zonder mens",
                        plus="Maximale menselijke controle overal",
                        minus="Geen schaalbare autonomie; jij blijft altijd bottleneck",
                    ),
                    "veto",
                ),
                (
                    "C",
                    _choice(
                        "Twin mag REAL-gates overslaan bij conf ≥ 0.95",
                        plus="Extreem snelle REAL-promotie bij hoge conf",
                        minus="Gevaarlijk: conf ≠ bewijs; kapitaalrisico in REAL",
                    ),
                    "aggressive",
                ),
            ],
            metrics_hint="layer=dual_authority real_gates=hard frame=real_conscience",
        ),
        _q(
            "base_capital_04",
            "capital_preservation",
            "Vandaag staat P&L op −2.8% (winst/verlies van de dag). "
            "De daily loss limit is −3% (harde stop: stop met handelen als je zoveel verliest).\n"
            "Er is nog één ‘edge-setup’ open (kansrijke setup volgens de bot).\n"
            "Doortraden of stop-for-day?",
            [
                (
                    "A",
                    _choice(
                        "Stop-for-day — limiet nadert, kapitaal is heilig",
                        plus="Geen kans om de harde daglimiet te raken",
                        minus="Je mist de laatste setup als die wél wint",
                    ),
                    "conservative",
                ),
                (
                    "B",
                    _choice(
                        "Eén setup max half size, daarna stop",
                        plus="Nog één kans, met kleinere put",
                        minus="Half size kan alsnog de limiet raken bij groot verlies",
                    ),
                    "balanced",
                ),
                (
                    "C",
                    _choice(
                        "Normaal door — limiet is nog niet geraakt",
                        plus="Maximale kans op herstel van de dag",
                        minus="Eén slechte trade kan de limiet triggeren / stop-for-day forceren",
                    ),
                    "aggressive",
                ),
            ],
            metrics_hint="daily_pnl=-2.8% limit=-3%",
        ),
    ]
    return tuple(qs)


@lru_cache(maxsize=1)
def _question_index() -> dict[str, TwinMcQuestion]:
    return {q.question_id: q for q in build_base_curriculum()}


def curriculum_axes_coverage(questions: list[TwinMcQuestion] | None = None) -> dict[str, int]:
    qs = list(questions) if questions is not None else list(build_base_curriculum())
    counts: dict[str, int] = {}
    for q in qs:
        counts[q.axis] = counts.get(q.axis, 0) + 1
    return counts


def curriculum_public_list() -> list[dict[str, Any]]:
    return [q.to_dict() for q in build_base_curriculum()]


def get_question(question_id: str) -> TwinMcQuestion | None:
    qid = str(question_id or "").strip()
    return _question_index().get(qid)


def question_count() -> int:
    return len(build_base_curriculum())

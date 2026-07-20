**LUMINA**

**EXECUTION FABRIC**

*Native Direct Integration with NinjaTrader 8*

Complete Engineering Blueprint, Architecture Specification

& Safety Framework for Self-Evolving AI Daytrading

**Version 1.0 \| July 2026**

Status: Ready for Engineering Implementation

***« Capital Preservation as Absolute Priority »***

First Principles • Radical Simplicity • Boundary Pushing • 100% Honesty

**INTERNAL --- LUMINA ENGINEERING TEAM**

Table of Contents

1\. Executive Summary & Visie

1.1 Core Message

Dit document definieert de complete architectuur, specificatie en implementatie roadmap voor de **LUMINA Execution Fabric** --- de native, directe, high-performance en ultra-betrouwbare koppeling tussen het LUMINA AI-organisme en NinjaTrader 8, zonder enige tussenliggende cloud of derde partij (zoals CrossTrade).

Dit is geen simpele \"bridge\". Dit is een **purpose-built execution plane** dat integraal deel uitmaakt van LUMINA\'s zelf-lerende, zelf-evoluerende natuur. Het is ontworpen vanuit First Principles met één niet-onderhandelbare prioriteit: **kapitaalbehoud als absolute voorwaarde**.

1.2 Why This Project Exists (First Principles)

-   **Kosten & Efficiëntie:** CrossTrade introduceert onnodige cloud-hops, latency en abonnementskosten. Voor een high-frequency daytrading organisme is dit suboptimaal.

-   **Latency & Determinisme:** Lokale IPC (gRPC over localhost) reduceert latency met factor 10-50x en elimineert jitter. Dit is meetbaar voordeel in daytrading edge.

-   **Controle & Evolutie:** Volledige ownership betekent dat de Fabric zelf kan evolueren samen met LUMINA\'s AI (parameters, monitoring, self-healing logica).

-   **Betrouwbaarheid op Nummer 1 Niveau:** We bouwen geen \"goed genoeg\" oplossing. We bouwen de meest betrouwbare execution laag die een AI-daytrader kan hebben --- met fail-safes die proactief kapitaal beschermen, ook als de AI-brain crasht of de verbinding verbreekt.

1.3 The Musk Challenge We Accept

\"Hoe maken we dit onverslaanbaar?\" --- We maken de LUMINA Execution Fabric zo performant, zo observeerbaar en zo inherent veilig dat het een competitieve moat wordt. Andere AI-trading projecten zullen dit willen kopiëren. Wij zijn de eersten die het perfect doen.

2\. Huidige Situatie & Beperkingen van CrossTrade

2.1 Wat CrossTrade Precies Is

CrossTrade is een commerciële suite bestaande uit een NT8 Add-On (lokaal) + een cloud-gemediëerde REST + WebSocket API. De externe applicatie (LUMINA) praat met de CrossTrade cloud, die de request doorstuurt naar de lokale Add-On in NT8. Dit is slim voor remote access en webhooks, maar introduceert:

-   Extra network hop (internet latency + jitter)

-   Afhankelijkheid van CrossTrade uptime, rate limits en pricing

-   Minder directe controle over timing en gedrag

-   Geen native integratie met LUMINA\'s self-evolving telemetry

2.2 Waarom Direct Beter Is voor LUMINA

LUMINA is een **zelf-lerend, zelf-evoluerend organisme** dat in SIM/Paper trading onbeperkt kan experimenteren en in real trading kapitaalbehoud als heilige graal heeft. Een cloud-tussenlaag past daar niet bij. Een directe, lokale, observeerbare en self-healing Fabric wel.

3\. Eerste Principes & Design Filosofie voor LUMINA

3.1 De Fundamentele Waarheden

1.  **Trading execution is een kritieke, stateful, low-tolerance operatie.** Fouten kosten echt geld. Daarom moet de execution laag onafhankelijk kunnen opereren van de AI-brain bij falen.

2.  **De bron van waarheid voor posities en orders ligt in NinjaTrader / broker.** De Fabric moet altijd de actuele staat kunnen reconciliëren.

3.  **Disconnect = potentieel gevaarlijke staat.** De default response moet conservatief en veilig zijn (cancel + flatten logica), met duidelijke configuratie en logging.

4.  **LUMINA evolueert.** De Fabric moet ontworpen zijn voor evolutie: versioning, telemetry die de AI kan consumeren, en parameters die later door LUMINA zelf getuned kunnen worden.

3.2 Design Principes (LUMINA-specifiek)

-   **Radicale Eenvoud:** Minimal viable contract eerst (core order + market data + heartbeat + safety). Itereer snel.

-   **Defense in Depth:** Meerdere lagen van validatie en fail-safe (Brain → Fabric → NT internals → Broker).

-   **Observability as First-Class Citizen:** Iedere belangrijke gebeurtenis (order, reconnect, timeout, flatten) is gelogd en meetbaar. LUMINA kan dit gebruiken voor self-improvement.

-   **Localhost Only + Strong Typing:** Geen externe exposure. gRPC + Protobuf voor type-veiligheid en evolutie.

-   **Capital Preservation Defaults:** Aggressieve, veilige defaults bij disconnect/timeout. Mens/AI kan later versoepelen op basis van data.

4\. Aanbevolen Architectuur --- De Perfecte LUMINA Execution Fabric

4.1 High-Level Overzicht

De architectuur bestaat uit drie hoofdcomponenten die samen één organisme vormen:

  ------------------------------------------- -------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------
  **Component**                               **Verantwoordelijkheid & Rationale**

  **LUMINA Brain (Python)**                   AI decision engine, self-learning models, strategy evolution, signal generation. Blijft volledig in Python ecosysteem voor maximale ML flexibiliteit en compute power.

  **LUMINA Execution Fabric (C# AddOn)**      Native NinjaScript AddOn in NT8. Beheert lokale gRPC server, order execution, market data streaming, state reconciliation, en --- cruciaal --- alle safety/fail-safe logica onafhankelijk van de Brain.

  **Communication Layer (gRPC + Protobuf)**   Bidirectional streaming over localhost. Sterk getypeerd, versioned, efficiënt. Ondersteunt market data push, command request-reply, heartbeats en events. Gekozen boven ZeroMQ voor betere structuur, tooling en lange-termijn maintainability.
  ------------------------------------------- -------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------

4.2 Waarom gRPC (en geen alternatief)?

-   **Bidirectional streaming:** Perfect voor real-time market data push vanuit NT + commando\'s vanuit Brain.

-   **Code generation & sterke typing:** Eén .proto definitie → perfecte Python én C# clients/servers. Minder bugs.

-   **Versioning & evolutie:** Proto supports backward compatibility --- cruciaal omdat LUMINA evolueert.

-   **Performance:** HTTP/2 + binary = uitstekend voor daytrading volumes (ticks/bars van enkele instrumenten).

-   **Tooling & community:** Uitstekende debugging (grpcurl, BloomRPC/Postman), monitoring, etc.

*Alternatief overwogen:* ZeroMQ is lichter en potentieel sneller voor pure HFT, maar mist de structuur en evolutie-garanties die wij nodig hebben voor een production trading organisme. gRPC is de juiste 80/20 keuze voor LUMINA.

4.3 Safety & Risk Engine (Core van Kapitaalbehoud)

De Fabric bevat een onafhankelijke **Safety & Risk Engine** die altijd actief is, ook als de Brain offline is. Dit is de belangrijkste innovatie ten opzichte van een simpele bridge.

-   Pre-trade checks: max position size per instrument, daily loss limit, order rate limits, reduce-only flags.

-   Watchdog timer op heartbeats van Brain.

-   Configurable Safe Mode policies (zie sectie 6).

-   Automatische cancel/flatten logica met timeouts.

-   Immutable audit log van alle beslissingen en acties.

5\. Gedetailleerd Technisch Design

5.1 Protocol Overzicht (gRPC Services)

De Fabric exposeert één primaire gRPC service met bidirectional streaming voor real-time interactie en unary calls voor queries.

Core RPCs (conceptueel)

-   **TradingStream (bidirectional streaming):** Brain ↔ Fabric. Brain stuurt commands (PlaceOrder, Cancel, Flatten, etc.). Fabric stuurt events (OrderUpdate, PositionUpdate, MarketDataTick/Bar, Heartbeat, Alerts).

-   **GetAccountState (unary):** Huidige posities, orders, buying power, P&L.

-   **RequestHistoricalData (unary):** Voor backtesting of model input.

-   **SetRiskParameters / GetRiskParameters:** Dynamische configuratie van safety limits (later door LUMINA tunebaar).

5.2 Belangrijke Bericht Types (Protobuf Concept)

Alle messages zijn sterk getypeerd en versioned. Belangrijke velden:

  ----------------------- --------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------
  **Message Type**        **Doel & Kritieke Velden**

  **Heartbeat**           sequence_number, timestamp, brain_status, last_known_state_hash. Wordt elke 1-2 seconden gestuurd.

  **PlaceOrderCommand**   client_order_id (UUID, idempotent), instrument, action (Buy/Sell), quantity, order_type (Market/Limit/Stop), price, stop_price, time_in_force, reduce_only, protected (niet automatisch cancellen bij disconnect).

  **OrderEvent**          client_order_id, nt_order_id, state (Submitted/Working/Filled/PartiallyFilled/Cancelled/Rejected), filled_qty, avg_fill_price, timestamp, rejection_reason.

  **MarketDataUpdate**    instrument, timestamp, last, bid, ask, volume (of bar: open/high/low/close/volume). Streaming push model.

  **StateSyncResponse**   Volledige snapshot: open orders, current positions per instrument, account metrics. Wordt periodiek of op verzoek gestuurd voor reconciliation.

  **SafetyAlert**         alert_type (HeartbeatTimeout, OrderRejected, PositionLimitBreached, SafeModeEntered), severity, message, recommended_action, timestamp.
  ----------------------- --------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------

5.3 Connection Lifecycle & State Management

5.  **Connect & Auth:** Eenvoudige lokale auth (shared secret of token in config file). Geen cloud.

6.  **Initial State Sync:** Bij connect stuurt Fabric direct volledige state (posities, working orders).

7.  **Heartbeat & Watchdog:** Beide kanten sturen heartbeats. Fabric heeft harde timeout (default 5s).

8.  **Graceful Disconnect:** Explicit disconnect → Fabric triggert configured disconnect policy (meestal cancel + optioneel flatten).

9.  **Reconnect & Recovery:** Bij reconnect → volledige state sync + event replay indien nodig. Idempotent design voorkomt dubbele orders.

5.4 Order Management & Idempotency

Elke order krijgt een **client_order_id (UUID v4 gegenereerd door Brain)**. De Fabric garandeert dat dezelfde client_order_id nooit dubbel wordt uitgevoerd. NT order IDs worden gekoppeld voor reconciliation.

Alle order acties (place, modify, cancel) zijn idempotent waar mogelijk. Fabric houdt een interne order state machine bij die altijd consistent is met NT.

6\. Fail-Safes, Disconnect Handling & Kapitaalbehoud Framework

**DIT IS DE BELANGRIJKSTE SECTIE VAN DIT DOCUMENT.**

In trading system design is de handling van disconnects en timeouts vaak de zwakste schakel. Wij maken het de sterkste. De default policy is **conservatief en proactief beschermend**. Alles is configureerbaar, maar de veilige defaults staan centraal.

6.1 Disconnect & Timeout Safety Matrix

De onderstaande matrix definieert exact wat er gebeurt in elke faal-scenario. Dit is geïmplementeerd in de Safety & Risk Engine van de Fabric.

  ----------------------------------------- -------------------------------- ------------------------------------------------------------------------------------------------------------------------- ------------------------------------------------------------------------------------------------------------------------------------------------------------------------
  **Scenario**                              **Detectie**                     **Immediate Action (Fabric)**                                                                                             **Secondary / Configurable**

  Brain Heartbeat Timeout (default 5s)      Fabric watchdog timer            1\. Cancel ALL working orders (behalve protected orders) 2. Enter SAFE MODE (reject nieuwe orders) 3. Log + SafetyAlert   Na extra 10s (totaal 15s): Indien net position ≠ 0 → issue Flatten orders (met max size & reduce-only waar mogelijk). Notificatie + optioneel human intervention flag.

  Explicit Brain Disconnect (graceful)      gRPC close                       Same as above (cancel + Safe Mode)                                                                                        Optioneel: Flatten direct of na timeout. Policy per instrument configureerbaar.

  Fabric verliest interne NT connectie      NT API exceptions / event loss   1\. Stop alle nieuwe execution 2. Attempt reconnect (exponential backoff) 3. Reject Brain commands met error              Na 30s falen: Alert + go to FULL SAFE MODE. Human operator moet handmatig interveniëren.

  Brain crasht / herstart (reconnect)       Nieuwe connectie + state sync    Volledige StateSync + event replay check. Idempotent → geen dubbele orders.                                               Brain vraagt actieve orders/posities op en reconcilieert intern model.

  Netwerk / localhost probleem (zeldzaam)   gRPC transport error             Reconnect attempt + buffer commands indien mogelijk                                                                       Na timeout: Safe Mode + alert. Omdat localhost: extreem zeldzaam.
  ----------------------------------------- -------------------------------- ------------------------------------------------------------------------------------------------------------------------- ------------------------------------------------------------------------------------------------------------------------------------------------------------------------

6.2 Protected Orders & Reduce-Only Logica

Orders kunnen gemarkeerd worden als **protected** (niet automatisch cancellen bij disconnect) of **reduce-only**. Dit is nuttig voor bracket orders of core positions die de AI wil behouden. De Safety Engine respecteert deze flags, maar waarschuwt bij langdurige disconnect.

6.3 Safe Mode States

-   **NORMAL:** Volledige operatie.

-   **SAFE_MODE:** Geen nieuwe orders geaccepteerd van Brain. Bestaande working orders worden gecanceld (behalve protected). Posities worden beheerd volgens policy.

-   **FULL_SAFE / MANUAL:** Alleen human operator of expliciete override kan orders plaatsen. Wordt geactiveerd bij ernstige of langdurige problemen.

6.4 Aanbevolen Default Policies voor Daytrading

1.  **Heartbeat timeout: 5 seconden** (agressief maar passend voor daytrading).

2.  **Cancel all working orders direct bij timeout.**

3.  **Flatten posities na extra 10-15 seconden** (configureerbaar per instrument of globaal).

4.  **Daily loss limit & max position size checks** altijd actief in Fabric, onafhankelijk van Brain beslissingen.

5.  **Alle safety acties + rationale worden gelogd** en gestuurd als SafetyAlert naar monitoring.

6.5 Audit Logging & Post-Incident Analyse

Iedere order, cancel, flatten, timeout, reconnect en safety decision wordt vastgelegd met timestamp, sequence number, client_order_id en rationale. Dit log is immutable en queryable --- zowel voor compliance als voor LUMINA\'s self-learning (\"wat gebeurde er toen de connectie wegviel en hoe reageerde het systeem?\").

7\. Betrouwbaarheid, Testing & Validatie Strategie

7.1 Filosofie: Boring Reliable

We streven naar \"boring reliable\" --- het systeem faalt zelden, en als het faalt, doet het dat op een voorspelbare, veilige manier met volledige observability. Geen verrassingen in live trading.

7.2 Testing Pyramid voor de Fabric

-   **Unit tests:** Order state machine, idempotency logic, safety policy engine.

-   **Integration tests:** gRPC layer + NT simulator (mock of real NT in SIM).

-   **Chaos Engineering:** Verplichte tests: random disconnects, heartbeat drops, NT restart mid-trade, high message volume, slow consumer.

-   **End-to-End in SIM/Paper:** Lange runs (dagen/weken) met LUMINA strategieën. Meet order success rate, max adverse excursion tijdens failures, recovery time.

-   **Failure Injection + Recovery Validation:** Elke safety policy moet expliciet getest en gedocumenteerd worden.

7.3 Key Performance & Reliability Metrics

-   Order placement success rate \> 99.9% (exclusief market rejects)

-   Reconnect success rate 100% binnen 10s na herstel

-   p99 roundtrip latency (command → ack) \< 5ms lokaal

-   Zero \"zombie orders\" of onverklaarde posities na disconnect scenarios

-   Full state reconciliation binnen 2s na reconnect

8\. Implementatie Roadmap & Fasen

Fase 0 --- Foundation & POC (2-3 weken)

-   Setup dev environment (NT8 + Visual Studio + Python gRPC)

-   Minimal AddOn + gRPC server skeleton

-   Basic PlaceOrder + Heartbeat + MarketData stream

-   Eerste disconnect simulation + basic cancel policy

-   **Success criterion:** E2E order placement vanuit Python in NT SIM werkt betrouwbaar.

Fase 1 --- Core MVP met Safety (3-4 weken)

-   Volledige order lifecycle (place/modify/cancel/flatten)

-   State reconciliation + periodic sync

-   Heartbeat watchdog + Safe Mode + configurable cancel/flatten policy

-   Audit logging + basic SafetyAlerts

-   **Success criterion:** Chaos tests (disconnect, restart) tonen correcte, veilige responses. Geen verloren orders/posities.

Fase 2 --- Production Hardening & Observability (3-4 weken)

-   Pre-trade risk engine (position limits, daily loss, rate limits)

-   Protected orders + reduce-only support

-   Prometheus metrics + structured logging + dashboard

-   Performance tuning (batching, efficient market data)

-   Uitgebreide documentatie + runbooks voor operators

-   **Success criterion:** Klaar voor langdurige Paper trading met LUMINA strategieën.

Fase 3 --- Advanced & Self-Evolution (doorlopend)

-   High-level intent interface (\"long bias X contracts met risk params\")

-   Dynamic risk parameters tunable by LUMINA

-   Advanced order types & ATM strategy integration indien relevant

-   Multi-account support (later)

-   Self-healing enhancements op basis van LUMINA learnings

9\. Risico\'s, Aannames & Mitigaties

  ---------------------------------------------- --------------------------------------------------------------------------------------------------------------------------------------------------------
  **Risico / Aanname**                           **Mitigatie / Opmerking**

  NT8 AddOn development complexiteit             Fase 0 POC valideert dit snel. Ervaren C# developer met NT ervaring aanbevolen. Documentatie en community resources zijn beschikbaar.

  NT updates breken AddOn                        Standaard risico bij NT extensies. Goede versie pinning + regression tests per NT update. Fabric design houdt rekening met mogelijke breaking changes.

  Safety policy te agressief → gemiste trades    Policies zijn configureerbaar. Start conservatief in SIM/Paper, meet impact, versoepel op basis van data. LUMINA kan later optimaliseren.

  Brain & Fabric state divergence                Periodieke full StateSync + client_order_id tracking + reconciliation logic bij reconnect. Idempotent design.

  Performance bottleneck bij hoge tick volumes   Daytrading focus (beperkt aantal instrumenten). gRPC + eventuele batching/ compression. Meet & optimaliseer in Fase 2.
  ---------------------------------------------- --------------------------------------------------------------------------------------------------------------------------------------------------------

10\. Appendices

Appendix A: Glossary

-   **Fabric:** LUMINA Execution Fabric --- de C# AddOn + gRPC laag.

-   **Brain:** LUMINA\'s AI decision / learning component (Python).

-   **Safe Mode:** Staat waarin Fabric geen nieuwe orders accepteert en protectieve acties uitvoert.

-   **Protected Order:** Order die niet automatisch gecanceld wordt bij disconnect.

-   **client_order_id:** UUID gegenereerd door Brain voor idempotentie en tracing.

Appendix B: Referenties

-   NinjaTrader 8 AddOn Development Guide

-   NinjaTrader DLL Interface Documentation

-   gRPC Best Practices & Performance Tuning (official docs)

-   Common patterns in professional prop trading execution systems (FIX Cancel on Disconnect analogs)

Appendix C: Volgende Stappen voor Engineering Team

10. Review dit document volledig en identificeer vragen/risico\'s.

11. Benoem lead developer(s) voor Fase 0 (C# NT + Python gRPC ervaring).

12. Start Fase 0 POC direct na akkoord.

13. Wekelijkse sync met LUMINA core team over voortgang en safety beleid.

14. Documenteer alle beslissingen en meetresultaten in dit levende document (versiebeheer).

**--- Einde van Blueprint v1.0 ---**

*LUMINA --- Het objectief beste zelf-lerende AI-daytrading organisme.*

*Niks is onmogelijk. We bouwen wat nog nooit iemand heeft gezien --- én dat écht werkt.*

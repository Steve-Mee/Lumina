# Waarom we bepaalde zaken bewust niet volledig "repareren"

Lumina is een **experimenteel levend organisme**, geen conventionele trading engine.  
Hieronder staan de ontwerpkeuzes die we bewust behouden, ook al worden ze door het panel als "problemen" gezien. Dit doen we om de unieke identiteit en experimentele kracht van Lumina te beschermen.

## 1. Flexibiliteit in SIM-modus (niet alles fail-closed)
**Waarom we dit behouden:**  
In SIM moet Lumina radicaal kunnen experimenteren, falen en leren. Te strenge fail-closed regels in SIM doden de creativiteit en het "organisme"-karakter.  
**Panel-advies:** We accepteren dat SIM soms "onveilig" gedrag toont. Dit is een bewuste keuze.

## 2. Bepaalde legacy compat-laag in `engine/`
**Waarom we dit behouden:**  
Sommige oude paden in `engine/` dienen als **veilige fallback** voor experimentele agenten en LLM-redenering. Volledige verwijdering zou nieuwe experimenten breken.  
**Panel-advies:** We migreren stapsgewijs, maar houden een minimale compat-laag zolang het experiment loopt.

## 3. Niet alles strikt getypeerd in experimentele lagen
**Waarom we dit behouden:**  
De meta-agent, dream engine en sommige LLM-interacties hebben baat bij enige "losheid" om emergent gedrag mogelijk te maken. Te strenge Pydantic contracts kunnen innovatie remmen.  
**Panel-advies:** Alleen kritieke execution- en risk-topics worden 100% strict. Experimentele lagen houden `extra="allow"` met duidelijke waarschuwing.

## 4. Enkele brede except-blokken in niet-kritieke paden
**Waarom we dit behouden:**  
In de creatieve en evolutionaire lagen (meta-agent, proposal generator) willen we soms "fail-soft" gedrag om het organisme te laten herstellen en verder te evolueren.  
**Panel-advies:** Alleen in REAL en kritieke governance-paden wordt alles fail-closed en expliciet gelogd.

---

**Kort samengevat:**  
We kiezen bewust voor **"veilige experimenteerruimte"** in plaats van "volledige corporate veiligheid". Dit is geen nalatigheid, maar een bewuste ontwerpfilosofie.
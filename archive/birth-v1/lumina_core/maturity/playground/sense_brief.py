"""Dutch Eerste-stappen instrument. Measurement only. Not a pass.

The operator sees what she is doing and what, if anything, she waits for.
A 240-minute candle is not the start of looking. Shadows are not orders.
"""
from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from lumina_core.birth.foundation_metrics import S3_OCCUPANCY_MAX, S3_OCCUPANCY_MIN
from lumina_core.maturity.playground.sense_brief_fields import (
    action as _action,
    age_words as _age_words,
    bar_book_operator_alert,
    chicago as _chicago,
    frozen_minutes as _frozen_minutes,
    gap_line as _gap_line,
    last_moment as _last_moment,
    listing as _listing,
    n_p as _n_p,
    occupancy as _occupancy,
    price as _price,
    read_json as _read_json,
)
from lumina_core.maturity.playground.sense_candles import parse_utc
from lumina_core.maturity.playground.sense_lab import load_sense

STALL_SEC = 30 * 60
FROZEN_MIN = 10
MAX_ALERTS = 8


def build_sense_brief(
    workspace_root: Path | str,
    *,
    running: bool = False,
    now: datetime | None = None,
) -> dict[str, Any]:
    """Cockpit fields. pass_now stays false. running is the Playground runner."""
    from lumina_core.maturity.playground.crawl import CRAWL_REL, crawl_totals
    from lumina_core.maturity.playground.envelope import envelope_sealed_for_pass
    from lumina_core.maturity.playground.habitat import OCCUPANCY_REL
    from lumina_core.maturity.playground.progress import load_playground_progress

    root = Path(workspace_root)
    moment = now if now is not None else datetime.now(timezone.utc)
    if moment.tzinfo is None:
        moment = moment.replace(tzinfo=timezone.utc)
    state = load_sense(root)
    closes = [row for row in list(state.get("closes") or []) if isinstance(row, dict)]
    decisions = int(state.get("decision_bars") or 0)
    flats = int(state.get("flat_bars") or 0)
    action = _action(state.get("last_action0"))
    progress = load_playground_progress(root)
    crawl = _read_json(root / CRAWL_REL)
    totals = crawl_totals(root)
    occupancy = _occupancy(progress, root / OCCUPANCY_REL)
    sealed = envelope_sealed_for_pass(root)
    paused = progress.get("paused") is True
    pending = crawl.get("pending_unfilled") is True
    reject = str(crawl.get("reject_reason") or "").strip()
    headline = _headline(
        decisions=decisions,
        flats=flats,
        action=action,
        paused=paused,
        pending=pending,
        closes=closes,
    )
    waiting = _waiting(
        sealed=sealed,
        paused=paused,
        pending=pending,
        decisions=decisions,
        flats=flats,
        n_p=_n_p(progress),
    )
    clock = _clock_line(
        closes=closes,
        progress=progress,
        decisions=decisions,
        running=running,
        paused=paused,
        now=moment,
    )
    market = _market_line(root=root, closes=closes, progress=progress, crawl=crawl, now=moment)
    alerts = _alerts(
        root=root,
        closes=closes,
        occupancy=occupancy,
        decisions=decisions,
        totals=totals,
        verdict=str(state.get("audit_verdict") or ""),
        geometry=str(state.get("geometry") or ""),
        reject=reject,
    )
    tone = _tone(
        running=running,
        paused=paused,
        sealed=sealed,
        closes=closes,
        now=moment,
        alerts=alerts,
        market=market,
    )
    from lumina_core.maturity.playground.demo_cash import refill_needed, refill_sentence, seal_cash

    school = _school_view(root)
    research = _research_line(school)
    if research:
        headline = research
    if school is not None and int(school["minute_count"]) > 0:
        clock = f"Archief {int(school['minute_count'])} minuten. {clock}"
        if decisions <= 0:
            waiting = (
                f"Zij zoekt in {int(school['minute_count'])} archiefminuten. "
                "De SIM-feed heeft nog geen nieuwe minuut. Het papier stopt daar niet voor."
            )
    alerts = _school_alerts(root, alerts, school, verdict=str(state.get("audit_verdict") or ""))
    paper = _paper_line(school)
    venue = _venue_line(crawl=crawl, progress=progress, closes=closes, now=moment)
    lines = [headline, waiting, clock, market, *alerts]
    cash = seal_cash(root)
    if refill_needed(cash):
        lines.insert(0, refill_sentence(cash))
    if paper:
        lines.append(paper)
    if venue:
        lines.append(venue)
    return {
        "pass_now": False,
        "headline": headline,
        "waiting": waiting,
        "clock": clock,
        "market": market,
        "paper": paper,
        "venue": venue,
        "alerts": alerts,
        "tone": tone,
        "lines": [line for line in lines if line],
    }


def _school_view(root: Path) -> dict[str, Any] | None:
    """The sentence she is on now, in file order. The last row in the file is not the current one."""
    from lumina_core.maturity.playground.learning_book import load_names, load_outcomes, read_header

    header = read_header(root)
    order: list[str] = []
    latest: dict[str, dict[str, Any]] = {}
    for row in load_names(root):
        name = str(row.get("name") or "")
        if not name:
            continue
        if name not in latest:
            order.append(name)
        latest[name] = row
    minute_count = int(header.get("minute_count") or 0)
    if not latest and minute_count <= 0:
        return None
    counts = {"lab": 0, "waiting": 0, "forward": 0, "buried": 0, "hand": 0}
    for row in latest.values():
        status = str(row.get("status") or "")
        if status == "waiting_tail":
            counts["waiting"] += 1
        elif status in counts:
            counts[status] += 1
    current: dict[str, Any] | None = None
    for status in ("hand", "lab", "waiting_tail", "forward"):
        for name in order:
            if str(latest[name].get("status") or "") == status:
                current = latest[name]
                break
        if current is not None:
            break
    return {
        "minute_count": minute_count,
        "counts": counts,
        "current": current,
        "outcomes": load_outcomes(root),
    }


def _research_line(school: dict[str, Any] | None) -> str:
    """What she is studying. Empty when the book has no open sentence."""
    if school is None:
        return ""
    row = school.get("current")
    if not isinstance(row, dict):
        buried = int(school["counts"]["buried"])
        if buried <= 0:
            return ""
        return f"Begraven: {buried} zinnen. Het schrift blijft. Geen order naar NinjaTrader."
    sentence = row.get("sentence") if isinstance(row.get("sentence"), dict) else {}
    name = str(row.get("name") or "")
    outcomes = [item for item in school["outcomes"] if str(item.get("name") or "") == name]
    mean = ""
    values = [float(item["net_r"]) for item in outcomes if item.get("net_r") is not None]
    if values:
        mean = f", mean R {sum(values) / len(values):.3f}"
    status = str(row.get("status") or "")
    why = {
        "lab": "Geen order naar NinjaTrader: de staart van deze zin is nog niet gescoord",
        "waiting_tail": "Geen order naar NinjaTrader: deze zin wacht op haar eigen latere staart",
        "forward": "Geen order naar NinjaTrader: het handexamen is nog niet gehaald",
        "hand": "Deze zin mag een SIM-order naar NinjaTrader sturen",
    }.get(status, "Geen order naar NinjaTrader")
    bar = sentence.get("bar_minutes", 1)
    return f"Onderzoek {name}: {bar} minuten, {len(outcomes)} papieren uitslagen{mean}. {why}."


def _paper_line(school: dict[str, Any] | None) -> str:
    if school is None:
        return ""
    counts = school["counts"]
    return (
        f"Papier: {int(school['minute_count'])} archiefminuten. "
        f"Lab {counts['lab']}, wacht {counts['waiting']}, vooruit {counts['forward']}, "
        f"begraven {counts['buried']}, hand {counts['hand']}. "
        "Papieren uitslagen zijn geen orders."
    )


def _venue_line(
    *,
    crawl: dict[str, Any],
    progress: dict[str, Any],
    closes: list[dict[str, Any]],
    now: datetime,
) -> str:
    side = int(crawl.get("position_side") or 0)
    try:
        qty = int(crawl.get("qty") or 0)
    except (TypeError, ValueError):
        qty = 0
    pending = crawl.get("pending_unfilled") is True
    if pending:
        book = "Er staat een order uit bij NinjaTrader. Nog geen fill."
    elif side > 0:
        book = f"NinjaTrader: long {qty}. De fill is van de beurs."
    elif side < 0:
        book = f"NinjaTrader: short {qty}. De fill is van de beurs."
    else:
        book = "NinjaTrader: plat. Geen order uitstaand."
    last = _last_moment(closes, progress)
    if last is None:
        return book
    age = max(0, int((now - last).total_seconds()))
    return f"{book} Laatste print {_age_words(age).replace('Laatste minuut ', '')}, {_chicago(last)}."


def _school_alerts(
    root: Path,
    alerts: list[str],
    school: dict[str, Any] | None,
    *,
    verdict: str,
) -> list[str]:
    from lumina_core.maturity.playground.law import N_D_SCHOOL
    from lumina_core.maturity.playground.school_days import green_day_streak

    if school is None:
        return alerts[:MAX_ALERTS]
    rows = [row for row in alerts if not row.startswith("Ogen:") and not row.startswith("Ouder boek:")]
    green = green_day_streak(root)
    rows.insert(
        0,
        f"Groene SIM-dagen: {green} van {N_D_SCHOOL}. "
        "Een groene dag is een hogere rekening aan het slot dan bij de opening.",
    )
    repair = _repair_line(root)
    if repair:
        rows.insert(0, repair)
    if verdict == "blind":
        rows.append("De plant-vector is leeg. Het papier leest die vector niet.")
    older = [row for row in alerts if row.startswith("Ouder boek:")]
    if older:
        rows.append(older[0].replace("Ouder boek:", "Crawl-boek:", 1).replace(
            "Deze klok telt",
            "Dat hoort niet bij het schrift. Deze klok telt",
            1,
        ))
    return rows[:MAX_ALERTS]


def _repair_line(root: Path) -> str:
    path = root / "reports" / "playground_tick_repair" / "repairs.jsonl"
    if not path.is_file():
        return ""
    last = ""
    try:
        for line in path.read_text(encoding="utf-8").splitlines():
            if line.strip():
                last = line
    except OSError:
        return ""
    if not last:
        return ""
    try:
        row = json.loads(last)
    except json.JSONDecodeError:
        return ""
    if not isinstance(row, dict):
        return ""
    reason = str(row.get("reason") or "")
    added = int(row.get("added") or 0) if str(row.get("added") or "").lstrip("-").isdigit() else 0
    if reason == "filled":
        return f"Reparatie: {added} minuten uit NinjaTrader teruggezet. Niets verzonnen."
    if reason == "source_empty":
        return "Reparatie: NinjaTrader had geen print in dat gat. Er is niets bijgeschreven."
    if reason == "nt_unreachable":
        return "Reparatie: NinjaTrader was niet bereikbaar. Er is niets verzonnen."
    if reason == "mismatch_refused":
        return "Reparatie: een minuut week af van het archief. Die is niet overschreven."
    return ""


def _headline(
    *,
    decisions: int,
    flats: int,
    action: float | None,
    paused: bool,
    pending: bool,
    closes: list[dict[str, Any]],
) -> str:
    if paused:
        return "Playground is gepauzeerd. Tape en cursor blijven."
    if pending:
        return "Er staat een order uit. De beurs heeft hem nog niet gevuld."
    if decisions <= 0:
        if closes:
            return (
                "Minuten komen binnen, maar deze klok heeft nog geen beslissing. "
                "Geen 240-minutenkaars nodig om te beginnen."
            )
        return "Nog geen gesloten minuut binnen. Geen 240-minutenkaars nodig om te beginnen."
    action_bit = "Actie nog niet opgeslagen" if action is None else f"Laatste actie {action:.2f}"
    if flats == decisions:
        return (
            f"Zij kiest plat. {action_bit}. "
            "Onder 0.50 is dat geen order. Dat is haar keuze, geen storing."
        )
    return (
        f"Deze klok: {decisions} minuten bekeken, waarvan {flats} plat. {action_bit}. "
        "Een order telt pas als de beurs hem vult."
    )


def _waiting(
    *,
    sealed: bool,
    paused: bool,
    pending: bool,
    decisions: int,
    flats: int,
    n_p: int,
) -> str:
    if paused:
        return "Hervat op dezelfde tape. Stall telt niet tijdens pauze."
    if not sealed:
        return "Op jou: dagvloer en SEAL. De crawl wacht tot de envelope dicht is."
    if pending:
        return f"n_P blijft {n_p}/150 tot een echte fill. JSON is geen fill."
    if decisions <= 0:
        return "Zij wacht op de eerste gesloten minuut van de SIM-feed. Niet op een hogere-tijdframekaars."
    if flats == decisions:
        return (
            f"Schoolpoort: 5 groene dagen. Closes {n_p} zijn geen poort van 150. "
            "Schaduw meet mee en neemt pas over na 150 bewezen trades. "
            "Een bijvul is geen dag. Geen 240-minutenkaars nodig om te kijken."
        )
    return (
        f"Schoolpoort: 5 groene dagen. Closes {n_p}. "
        "Schaduw meet mee en neemt pas over na 150 bewezen trades."
    )


def _closed_sentence(moment: datetime) -> str | None:
    from lumina_core.market.globex_hours import closed_sentence

    try:
        return closed_sentence(moment)
    except ValueError:
        return None


def _clock_line(
    *,
    closes: list[dict[str, Any]],
    progress: dict[str, Any],
    decisions: int,
    running: bool,
    paused: bool,
    now: datetime,
) -> str:
    closed = _closed_sentence(now)
    if closed is not None:
        return closed
    last = _last_moment(closes, progress)
    chicago = _chicago(last) if last is not None else ""
    age = max(0, int((now - last).total_seconds())) if last is not None else None
    counted = f"{decisions} minuten deze klok" if decisions > 0 else "nog geen beslissing deze klok"
    if paused:
        when = f"Laatste minuut {chicago}." if chicago else "Nog geen minuut op deze klok."
        return f"{when} {counted}. Gepauzeerd."
    if age is None:
        if running:
            return f"Nog geen minuut op deze klok. {counted}."
        return f"Klok staat stil. {counted}."
    age_bit = _age_words(age)
    place = f"{age_bit} · {chicago}" if chicago else age_bit
    if age < 90:
        pulse = "klok leeft" if running else "minuten komen binnen"
        return f"{place} · {counted} · {pulse}."
    if not running:
        return f"{place} · {counted}. De Playground-klok staat stil."
    if age < STALL_SEC:
        return f"{place} · {counted}. Een stilte onder 30 minuten is geen stall."
    return f"{place} · {counted}. Drie zulke vensters zijn een stall, geen pass."


def _crawl_saved_at(root: Path) -> datetime | None:
    from lumina_core.maturity.playground.crawl import CRAWL_REL

    path = root / CRAWL_REL
    if not path.is_file():
        return None
    return datetime.fromtimestamp(path.stat().st_mtime, tz=timezone.utc)


def _market_line(
    *,
    root: Path,
    closes: list[dict[str, Any]],
    progress: dict[str, Any],
    crawl: dict[str, Any],
    now: datetime,
) -> str:
    listing = _listing(progress)
    px = _price(closes, progress, crawl)
    frozen = _frozen_minutes(closes)
    if px is None and not listing:
        return "Nog geen live prijs."
    head = f"{listing} · {px:.2f}" if listing and px is not None else (
        listing or (f"{px:.2f}" if px is not None else "—")
    )
    last = _last_moment(closes, progress)
    if last is None and px is not None and crawl.get("live_px") not in (None, ""):
        last = _crawl_saved_at(root)
        if last is not None:
            age = max(0, int((now - last).total_seconds()))
            head = f"{head} uit het crawl-boek, bewaard {_age_words(age)}, {_chicago(last)}"
            last = None
    if last is None and px is not None and "crawl-boek" not in head:
        head = f"{head}. Het tijdstip van deze print ontbreekt"
    elif last is not None:
        age = max(0, int((now - last).total_seconds()))
        head = f"{head} · {_age_words(age)}, {_chicago(last)}"
    if frozen >= FROZEN_MIN and px is not None:
        return (
            f"{head}. De print staat al {frozen} minuten stil. "
            "Minuten komen binnen, de print beweegt niet."
        )
    return head


def _alerts(
    *,
    root: Path,
    closes: list[dict[str, Any]],
    occupancy: float | None,
    decisions: int,
    totals: dict[str, int],
    verdict: str,
    geometry: str,
    reject: str,
) -> list[str]:
    rows: list[str] = []
    if reject:
        rows.append(f"Laatste order geweigerd: {reject}.")
    bar_book = bar_book_operator_alert(root)
    if bar_book:
        rows.append(bar_book)
    if occupancy is not None and not (
        S3_OCCUPANCY_MIN - 1e-12 <= occupancy <= S3_OCCUPANCY_MAX + 1e-12
    ):
        rows.append(
            f"Occupancy {occupancy * 100:.0f}% plat. Dat is een meting, niet de schoolpoort. "
            "De schoolpoort is 5 groene dagen."
        )
    older = int(totals.get("total_bars") or 0)
    if older > decisions:
        rows.append(
            f"Ouder boek: {older} beslissingen. Deze klok telt {decisions} nieuwe minuten. "
            "Die twee niet optellen."
        )
    if verdict == "blind":
        rows.append("Ogen: blind. Exam-slots staan leeg in de live vector. Geen pass.")
    gap = _gap_line(closes)
    if gap:
        rows.append(gap)
    if geometry == "missing":
        rows.append("Birth-geometrie ontbreekt. Schaduwen openen niet. De policy kijkt wel.")
    return rows[:MAX_ALERTS]


def _tone(
    *,
    running: bool,
    paused: bool,
    sealed: bool,
    closes: list[dict[str, Any]],
    now: datetime,
    alerts: list[str],
    market: str,
) -> str:
    if paused or not sealed:
        return "wait"
    if "stil" in market or any(
        "Occupancy" in row or "geweigerd" in row or "Barboek" in row for row in alerts
    ):
        return "alert"
    last = parse_utc(str(closes[-1].get("ts") or "")) if closes else None
    age = max(0, int((now - last).total_seconds())) if last is not None else None
    if _closed_sentence(now) is not None:
        return "wait"
    if running and age is not None and age >= STALL_SEC:
        return "alert"
    if running and age is not None and age < 90:
        return "live"
    if running:
        return "wait"
    return "idle"

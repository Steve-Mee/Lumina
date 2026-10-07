/** Operator instrument: what she is doing, and what she waits for. Engine SSOT. */

import type { PlaygroundSenseBrief as SensePayload } from "@/lib/playground/playgroundChecklist";
import { cn } from "@/lib/utils";

export type SenseView = {
  headline: string;
  waiting: string;
  clock: string;
  market: string;
  paper: string;
  venue: string;
  alerts: string[];
  tone: "live" | "wait" | "alert" | "idle";
  fallback: boolean;
};

const FALLBACK_VIEW: SenseView = {
  headline: "De klok draait. Live zinnen van de engine zijn nog niet binnengekomen.",
  waiting: "Geen 240-minutenkaars nodig om te kijken. Dit is een fallback, geen meting.",
  clock: "Wacht op de volgende voortgang van de klok.",
  market: "—",
  paper: "",
  venue: "",
  alerts: [],
  tone: "wait",
  fallback: true,
};

export function PlaygroundSenseBrief({
  sense,
  running,
  variant = "inline",
}: {
  sense?: SensePayload | null;
  running: boolean;
  variant?: "inline" | "dock";
}) {
  const view = senseViewForScreen(sense, running);
  if (!view) return null;
  return (
    <section
      aria-label="Wat er nu gebeurt"
      aria-live="polite"
      className={cn(
        "playground-sense",
        variant === "dock" && "playground-sense--dock",
        view.fallback && "playground-sense--fallback",
      )}
      data-tone={view.tone}
    >
      <header className="playground-sense__head">
        <span className="playground-sense__dot" aria-hidden />
        <p className="playground-sense__kicker">Wat er nu gebeurt</p>
        {view.fallback ? <span className="playground-sense__tag">fallback</span> : null}
      </header>
      <p className="playground-sense__headline">{view.headline}</p>
      <dl className="playground-sense__rows">
        <div className="playground-sense__row">
          <dt>Wacht</dt>
          <dd title={view.waiting}>{view.waiting}</dd>
        </div>
        <div className="playground-sense__row">
          <dt>Klok</dt>
          <dd title={view.clock}>{view.clock}</dd>
        </div>
        <div className="playground-sense__row">
          <dt>Markt</dt>
          <dd title={view.market}>{view.market}</dd>
        </div>
        {view.paper ? (
          <div className="playground-sense__row">
            <dt>Papier</dt>
            <dd title={view.paper}>{view.paper}</dd>
          </div>
        ) : null}
        {view.venue ? (
          <div className="playground-sense__row">
            <dt>Beurs</dt>
            <dd title={view.venue}>{view.venue}</dd>
          </div>
        ) : null}
      </dl>
      {view.alerts.length > 0 ? (
        <ul className="playground-sense__alerts">
          {view.alerts.map((alert) => (
            <li key={alert} title={alert}>
              {alert}
            </li>
          ))}
        </ul>
      ) : null}
    </section>
  );
}

export function senseLines(sense: { lines?: string[] } | null | undefined): string[] {
  if (!sense || !Array.isArray(sense.lines)) return [];
  return sense.lines.map((line) => String(line)).filter((line) => line.trim().length > 0);
}

export function senseViewForScreen(
  sense: SensePayload | null | undefined,
  running: boolean,
): SenseView | null {
  if (sense && typeof sense.headline === "string" && sense.headline.trim()) {
    return {
      headline: sense.headline.trim(),
      waiting: String(sense.waiting || "").trim() || "—",
      clock: String(sense.clock || "").trim() || "—",
      market: String(sense.market || "").trim() || "—",
      paper: String(sense.paper || "").trim(),
      venue: String(sense.venue || "").trim(),
      alerts: Array.isArray(sense.alerts)
        ? sense.alerts.map((item) => String(item)).filter((item) => item.trim().length > 0)
        : [],
      tone: sense.tone === "live" || sense.tone === "wait" || sense.tone === "alert" || sense.tone === "idle"
        ? sense.tone
        : running
          ? "live"
          : "idle",
      fallback: false,
    };
  }
  const live = senseLines(sense);
  if (live.length > 0) {
    return {
      headline: live[0],
      waiting: live[1] || "—",
      clock: live[2] || "—",
      market: live[3] || "—",
      paper: "",
      venue: "",
      alerts: live.slice(4, 12),
      tone: running ? "live" : "idle",
      fallback: false,
    };
  }
  return running ? FALLBACK_VIEW : null;
}

export function senseLinesForScreen(
  sense: { lines?: string[] } | null | undefined,
  running: boolean,
): string[] {
  const view = senseViewForScreen(sense, running);
  if (!view) return [];
  return [view.headline, view.waiting, view.clock, view.market, view.paper, view.venue, ...view.alerts].filter(
    (line) => line && line !== "—",
  );
}

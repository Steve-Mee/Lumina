/** Honest Playground life-signs. The seconds move. A frozen number means the clock stopped. */

import { formatHeartbeatAge, heartbeatAgeMs } from "@/lib/awakening/awakeningLife";

export type PlaygroundLifeState = "live" | "waiting" | "silent" | "idle";

export interface PlaygroundLifeInput {
  running: boolean;
  updatedAt?: unknown;
  nP?: unknown;
  greenDays?: unknown;
  exchangeNote?: unknown;
  envelopeSealed?: boolean;
  feedNote?: unknown;
  nowMs: number;
}

const SILENT_AFTER_MS = 45_000;

function asNumber(value: unknown): number | null {
  if (typeof value === "number" && Number.isFinite(value)) return value;
  if (typeof value === "string" && value.trim() !== "") {
    const n = Number(value);
    return Number.isFinite(n) ? n : null;
  }
  return null;
}

export function resolvePlaygroundLifeState(input: PlaygroundLifeInput): PlaygroundLifeState {
  if (!input.running) return "idle";
  const age = heartbeatAgeMs(input.updatedAt, input.nowMs);
  if (age == null || age >= SILENT_AFTER_MS) return "silent";
  if (input.envelopeSealed === false) return "waiting";
  return "live";
}

export function playgroundLifeCaption(state: PlaygroundLifeState): string {
  if (state === "live") return "Klok leeft";
  if (state === "waiting") return "School · geen drawdown-limiet";
  if (state === "silent") return "Geen hartslag — de klok is stil";
  return "Klok uit";
}

export function playgroundLifeLine(input: PlaygroundLifeInput): string {
  const closed = typeof input.exchangeNote === "string" ? input.exchangeNote.trim() : "";
  if (closed.startsWith("Beurs dicht")) return closed;
  const nP = Math.round(asNumber(input.nP) ?? 0);
  const green = Math.round(asNumber(input.greenDays) ?? 0);
  const age = formatHeartbeatAge(heartbeatAgeMs(input.updatedAt, input.nowMs));
  const feed = typeof input.feedNote === "string" ? input.feedNote.trim() : "";
  const clock = `groen ${green}/5 · closes ${nP.toLocaleString("en-US")} · hartslag ${age}`;
  if (!input.running) return `Stil · ${clock}`;
  if (input.envelopeSealed === false) {
    const floor = "Geen drawdown-limiet";
    return feed ? `${floor} · ${clock} · ${feed}` : `${floor} · ${clock}`;
  }
  return feed ? `Zij kijkt · ${clock} · ${feed}` : `Zij kijkt · ${clock}`;
}

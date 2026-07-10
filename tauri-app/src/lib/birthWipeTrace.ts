/** Structured trace for Wis birth-data — inspect via DevTools console or window.__BIRTH_WIPE_TRACE__. */

export type BirthWipeTraceLevel = "debug" | "info" | "warn" | "error";

export interface BirthWipeTraceEntry {
  ts: string;
  level: BirthWipeTraceLevel;
  phase: string;
  detail?: Record<string, unknown>;
  message?: string;
}

const TRACE_PREFIX = "[birth-wipe]";
const MAX_TRACE_ENTRIES = 80;

const traceBuffer: BirthWipeTraceEntry[] = [];

declare global {
  interface Window {
    __BIRTH_WIPE_TRACE__?: BirthWipeTraceEntry[];
  }
}

function pushTrace(entry: BirthWipeTraceEntry): void {
  traceBuffer.push(entry);
  if (traceBuffer.length > MAX_TRACE_ENTRIES) {
    traceBuffer.splice(0, traceBuffer.length - MAX_TRACE_ENTRIES);
  }
  if (typeof window !== "undefined") {
    window.__BIRTH_WIPE_TRACE__ = [...traceBuffer];
  }
}

export function getBirthWipeTrace(): readonly BirthWipeTraceEntry[] {
  return [...traceBuffer];
}

export function clearBirthWipeTrace(): void {
  traceBuffer.length = 0;
  if (typeof window !== "undefined") {
    window.__BIRTH_WIPE_TRACE__ = [];
  }
}

export function traceBirthWipe(
  phase: string,
  detail: Record<string, unknown> = {},
  level: BirthWipeTraceLevel = "info",
): void {
  const entry: BirthWipeTraceEntry = {
    ts: new Date().toISOString(),
    level,
    phase,
    detail: Object.keys(detail).length > 0 ? detail : undefined,
    message: typeof detail.message === "string" ? detail.message : undefined,
  };
  pushTrace(entry);

  const payload = { phase, ...detail };
  const line = `${TRACE_PREFIX} ${phase}`;
  switch (level) {
    case "error":
      console.error(line, payload);
      break;
    case "warn":
      console.warn(line, payload);
      break;
    case "debug":
      console.debug(line, payload);
      break;
    default:
      console.info(line, payload);
  }
}

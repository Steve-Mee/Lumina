/** Honest Playground copy — never keep a loading line after the clock has died. */

export function playgroundClockButtonLabel(input: {
  running: boolean;
  passNow: boolean;
  progressMessage?: string | null;
}): string {
  if (input.passNow) return "PLAYGROUND COMPLETE";
  if (!input.running) return "START PLAYGROUND";
  const message = (input.progressMessage || "").toLowerCase();
  if (message.includes("plat") || message.includes("geen stall") || message.includes("flat")) {
    return "ZIJ KIEST FLAT";
  }
  return "SCHOOL";
}

export function playgroundHeaderStatus(input: {
  running: boolean;
  passNow: boolean;
  focusStatus?: string | null;
  error?: string | null;
  progressMessage?: string | null;
  envelopeSealed?: boolean;
}): string {
  if (input.running && input.envelopeSealed === false) {
    return "Geen drawdown-limiet in de school";
  }
  if (input.running) return input.progressMessage || "Leerschool in SIM";
  if (input.passNow) return "AND passed — return to Phase Hub";
  if (isPlaygroundFailed(input)) {
    return "Clock halted — fail-closed, Birth + Awakening intact";
  }
  return "Incomplete — floors stay fail-closed";
}

export function playgroundMissionMessage(input: {
  running: boolean;
  error?: string | null;
  focusStatus?: string | null;
  progressMessage?: string | null;
  note?: string | null;
  envelopeSealed?: boolean;
}): string {
  if (input.running && input.envelopeSealed === false) {
    return "De klok leeft. Verlies stopt de school niet. Bijvullen is geen groene dag.";
  }
  if (input.running) {
    return input.progressMessage || "Leerschool in SIM";
  }
  if (isPlaygroundFailed(input)) {
    return failLine(input.error, input.progressMessage);
  }
  return (
    input.progressMessage ||
    input.note ||
    "Leerschool in SIM. Poort: 5 groene sessiedagen van echte fills. Geen REAL."
  );
}

export function isPlaygroundFailed(input: {
  running?: boolean;
  error?: string | null;
  focusStatus?: string | null;
}): boolean {
  if (input.running) return false;
  if (typeof input.error === "string" && input.error.trim()) return true;
  return input.focusStatus === "failed";
}

function failLine(error?: string | null, progressMessage?: string | null): string {
  const err = typeof error === "string" ? error.trim() : "";
  if (err) return `Failed: ${err}`;
  const msg = typeof progressMessage === "string" ? progressMessage.trim() : "";
  if (msg.toLowerCase().startsWith("failed:")) return msg;
  if (msg) return `Failed: ${msg}`;
  return "Failed: playground clock halted";
}

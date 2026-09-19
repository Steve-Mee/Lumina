/** Honest Apprenticeship copy — never keep a loading line after the clock has died. */

export function apprenticeshipHeaderStatus(input: {
  running: boolean;
  passNow: boolean;
  focusStatus?: string | null;
  error?: string | null;
  progressMessage?: string | null;
}): string {
  if (input.running) return input.progressMessage || "Living clock";
  if (input.passNow) return "AND passed — return to Phase Hub";
  if (isApprenticeshipFailed(input)) {
    return "Clock halted — fail-closed, Birth + Playground intact";
  }
  return "Incomplete — floors stay fail-closed";
}

export function apprenticeshipMissionMessage(input: {
  running: boolean;
  error?: string | null;
  focusStatus?: string | null;
  progressMessage?: string | null;
  note?: string | null;
}): string {
  if (input.running) {
    return input.progressMessage || "Living clock — walking on NT SIM under REAL rules";
  }
  if (isApprenticeshipFailed(input)) {
    return failLine(input.error, input.progressMessage);
  }
  return (
    input.progressMessage ||
    input.note ||
    "Walk five consecutive SIM session days. Sharpe ≥ 0.20, DD ≤ 12%, constitution 0. A backtest is not a day."
  );
}

export function isApprenticeshipFailed(input: {
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
  return "Failed: apprenticeship clock halted";
}

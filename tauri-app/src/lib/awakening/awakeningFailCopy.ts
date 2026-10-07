/** Honest Awakening copy — never keep a loading line after the clock has died. */

export function awakeningHeaderStatus(input: {
  running: boolean;
  passNow: boolean;
  focusStatus?: string | null;
  error?: string | null;
  progressMessage?: string | null;
}): string {
  if (input.running) return input.progressMessage || "First Watch living clock";
  if (input.passNow) return "AND passed — return to Phase Hub";
  if (input.focusStatus === "stopped") return "Stopped — Birth plant intact";
  if (isAwakeningFailed(input)) return "Clock halted — fail-closed, Birth intact";
  if (!input.focusStatus || input.focusStatus === "pending") {
    return "Not started — start Awakening from Phase Hub";
  }
  return "Incomplete — floors stay fail-closed";
}

export function awakeningMissionMessage(input: {
  running: boolean;
  error?: string | null;
  focusStatus?: string | null;
  progressMessage?: string | null;
  note?: string | null;
}): string {
  if (input.running) {
    return input.progressMessage || "First Watch living clock";
  }
  if (input.focusStatus === "stopped") {
    return input.progressMessage || "Stopped — Birth plant intact. Freeze held.";
  }
  if (isAwakeningFailed(input)) {
    return failLine(input.error, input.progressMessage);
  }
  return (
    input.progressMessage ||
    input.note ||
    "First Watch: frozen Birth plant on holdout B. One eval, no learn(). Tape end is the exam."
  );
}

export function isAwakeningFailed(input: {
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
  return "Failed: awakening runner halted";
}

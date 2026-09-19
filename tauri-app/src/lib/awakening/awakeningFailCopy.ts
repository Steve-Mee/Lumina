/** Honest Awakening copy — never keep a loading line after the clock has died. */

export function awakeningHeaderStatus(input: {
  running: boolean;
  passNow: boolean;
  focusStatus?: string | null;
  error?: string | null;
  progressMessage?: string | null;
}): string {
  if (input.running) return input.progressMessage || "Living clock";
  if (input.passNow) return "AND passed — return to Phase Hub";
  if (isAwakeningFailed(input)) return "Clock halted — fail-closed, Birth intact";
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
    return input.progressMessage || "Living clock";
  }
  if (isAwakeningFailed(input)) {
    return failLine(input.error, input.progressMessage);
  }
  return (
    input.progressMessage ||
    input.note ||
    "Prefer better than frozen π*. Cycle 0 evals the parent. Then 8 train cycles keep-best. Tape end is not a stop."
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

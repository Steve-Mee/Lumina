/** Honest Proving Ground copy — never keep a loading line after the clock has died. */

export function provingGroundHeaderStatus(input: {
  running: boolean;
  passNow: boolean;
  focusStatus?: string | null;
  error?: string | null;
  progressMessage?: string | null;
}): string {
  if (input.running) return input.progressMessage || "Living clock";
  if (input.passNow) return "AND passed — return to Phase Hub";
  if (isProvingGroundFailed(input)) {
    return "Clock halted — fail-closed, earlier ladder intact";
  }
  return "Incomplete — floors stay fail-closed";
}

export function provingGroundMissionMessage(input: {
  running: boolean;
  error?: string | null;
  focusStatus?: string | null;
  progressMessage?: string | null;
  note?: string | null;
}): string {
  if (input.running) {
    return input.progressMessage || "Living clock — cert exam + shadow + PromotionGate";
  }
  if (isProvingGroundFailed(input)) {
    return failLine(input.error, input.progressMessage);
  }
  return (
    input.progressMessage ||
    input.note ||
    "Driving test before capital. Cert OOS 48%/0.35/8%, this-run shadow, PromotionGate 4/4. Birth JSON is not the exam."
  );
}

export function isProvingGroundFailed(input: {
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
  return "Failed: proving-ground clock halted";
}

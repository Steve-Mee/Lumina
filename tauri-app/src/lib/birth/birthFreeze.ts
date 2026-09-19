import type { BirthStatusPayload } from "@/lib/birthClient";

/**
 * Unresolved champion/phoenix freeze — fail-closed.
 * A freeze object that is not explicitly resolved is sacred, even when reason
 * is briefly empty during a disk write or a live leftover is still true.
 */
export function isUnresolvedTerminalFreeze(
  status: BirthStatusPayload | null | undefined,
): boolean {
  const freeze = status?.progress?.terminal_freeze;
  if (!freeze || typeof freeze !== "object") {
    return false;
  }
  if (freeze.resolved === true) {
    return false;
  }
  const reason = String(freeze.reason ?? "").trim();
  const nextAction = String(freeze.next_action ?? "").trim();
  const schema = String(freeze.schema ?? "").trim();
  return reason !== "" || nextAction !== "" || schema !== "";
}

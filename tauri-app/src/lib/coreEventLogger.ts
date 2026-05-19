import { invoke, isTauri } from "@tauri-apps/api/core";

import { REAL_SAFE_MODE_THRESHOLD_MS } from "@/lib/realSafeMode";

export interface CoreEventPayload {
  ts: string;
  event: string;
  source: "command_deck";
  [key: string]: unknown;
}

export async function logCoreEvent(
  event: string,
  details: Record<string, unknown> = {},
): Promise<void> {
  const payload: CoreEventPayload = {
    ts: new Date().toISOString(),
    event,
    source: "command_deck",
    threshold_ms: REAL_SAFE_MODE_THRESHOLD_MS,
    ...details,
  };

  if (!isTauri()) {
    console.warn("[core_event]", payload);
    return;
  }

  try {
    await invoke("append_core_event", {
      payload: JSON.stringify(payload),
    });
  } catch (error) {
    console.error("[core_event] failed to append", error, payload);
  }
}

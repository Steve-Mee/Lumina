import { useCoreStore } from "@/store/coreStore";

import {
  parseTelemetryFrame,
  resolveCoreLiveHttpUrl,
  type TelemetryFrame,
} from "@/lib/coreLiveTelemetry";

export const FALLBACK_THRESHOLD_MS = 10_000;
export const POLL_INTERVAL_MS = 2_000;

let fallbackThresholdTimer: ReturnType<typeof setTimeout> | null = null;
let pollIntervalTimer: ReturnType<typeof setInterval> | null = null;
let pollSeq = 0;

export function getPollSeq(): number {
  return pollSeq;
}

export function resetPollSeq(): void {
  pollSeq = 0;
}

export function clearFallbackThresholdTimer(): void {
  if (fallbackThresholdTimer !== null) {
    clearTimeout(fallbackThresholdTimer);
    fallbackThresholdTimer = null;
  }
}

export function stopPolling(): void {
  if (pollIntervalTimer !== null) {
    clearInterval(pollIntervalTimer);
    pollIntervalTimer = null;
  }
}

export async function fetchTelemetryFrame(): Promise<TelemetryFrame | null> {
  try {
    const response = await fetch(resolveCoreLiveHttpUrl());
    if (!response.ok) {
      useCoreStore
        .getState()
        .setLastError(`Polling failed: HTTP ${response.status}`);
      return null;
    }
    const parsed: unknown = await response.json();
    const frame = parseTelemetryFrame(parsed);
    if (!frame) {
      useCoreStore
        .getState()
        .setLastError("Received malformed polling payload");
      return null;
    }
    pollSeq += 1;
    return { ...frame, seq: pollSeq };
  } catch {
    useCoreStore.getState().setLastError("Polling request failed");
    return null;
  }
}

export async function pollOnce(isWebSocketConnected: () => boolean, intentionalClose: () => boolean): Promise<void> {
  if (intentionalClose() || isWebSocketConnected()) {
    return;
  }
  const frame = await fetchTelemetryFrame();
  if (frame) {
    useCoreStore.getState().applyTelemetryFrame(frame);
  }
}

export function startPollingFallback(
  isWebSocketConnected: () => boolean,
  intentionalClose: () => boolean,
): void {
  const store = useCoreStore.getState();
  if (intentionalClose() || isWebSocketConnected()) {
    return;
  }

  store.setFallbackMode(true);
  stopPolling();
  void pollOnce(isWebSocketConnected, intentionalClose);
  pollIntervalTimer = setInterval(() => {
    void pollOnce(isWebSocketConnected, intentionalClose);
  }, POLL_INTERVAL_MS);
}

export function armFallbackThreshold(
  isWebSocketConnected: () => boolean,
  intentionalClose: () => boolean,
  startFallback: () => void,
): void {
  if (intentionalClose() || isWebSocketConnected()) {
    return;
  }

  clearFallbackThresholdTimer();
  fallbackThresholdTimer = setTimeout(() => {
    fallbackThresholdTimer = null;
    if (intentionalClose() || isWebSocketConnected()) {
      return;
    }
    startFallback();
  }, FALLBACK_THRESHOLD_MS);
}

export function exitFallbackMode(): void {
  clearFallbackThresholdTimer();
  stopPolling();
  useCoreStore.getState().setFallbackMode(false);
}
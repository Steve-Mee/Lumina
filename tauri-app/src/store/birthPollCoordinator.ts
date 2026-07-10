import type { BirthStatusPayload } from "@/lib/birthClient";
import { fetchBirthStatusTyped } from "@/lib/birthClient";

const TRANSIENT_HEAVY_PHASES = new Set([
  "loading_history",
  "loading_history_failed",
  "enriching_news",
  "enriching_regimes",
  "train_holdout_split",
  "holdout_preflight",
  "holdout_preflight_expansion",
  "policy_init",
  "ticks_ready",
]);

export const TRANSIENT_POLL_WARNING =
  "Status even traag — training loopt door. Probeer opnieuw te verbinden.";

let pollAbortController: AbortController | null = null;
let pollInFlight = false;
let consecutivePollFailures = 0;

export function isTransientHeavyBirthPhase(status: BirthStatusPayload | null): boolean {
  if (status == null) {
    return false;
  }
  if (String(status.status ?? "").toLowerCase() !== "running") {
    return false;
  }
  const phase = String(status.progress?.phase ?? "").toLowerCase();
  const stage = String(status.progress?.stage ?? "").toLowerCase();
  return stage === "loading_data" || TRANSIENT_HEAVY_PHASES.has(phase);
}

function normalizePollError(err: unknown): string {
  if (err instanceof DOMException && err.name === "AbortError") {
    return "";
  }
  if (err instanceof Error) {
    return err.message;
  }
  return String(err);
}

function isAbortError(err: unknown): boolean {
  if (err instanceof DOMException && err.name === "AbortError") {
    return true;
  }
  return err instanceof Error && err.message === "Request cancelled";
}

export function isTransientPollWarning(message: string | null | undefined): boolean {
  return message === TRANSIENT_POLL_WARNING;
}

/** Test hook: whether a background status poll is in flight. */
export function isBirthPollInFlight(): boolean {
  return pollInFlight;
}

const POLL_FRESH_WAIT_MS = 3000;
const POLL_FRESH_POLL_INTERVAL_MS = 50;

export const STOP_ENGINE_POLL_MS = 500;
export const STOP_ENGINE_TIMEOUT_MS = 30_000;
export const WIPE_VERIFY_ATTEMPTS = 10;
export const WIPE_VERIFY_DELAY_MS = 500;

export async function waitForPollIdle(maxWaitMs: number = POLL_FRESH_WAIT_MS): Promise<void> {
  const deadline = Date.now() + maxWaitMs;
  while (pollInFlight && Date.now() < deadline) {
    await new Promise((resolve) => setTimeout(resolve, POLL_FRESH_POLL_INTERVAL_MS));
  }
}

export function resetPollCoordinator(): void {
  pollAbortController?.abort();
  pollAbortController = null;
  pollInFlight = false;
  consecutivePollFailures = 0;
}

export async function pollBirthStatusWithErrorHandling(
  applyStatus: (payload: BirthStatusPayload) => void,
  getStatus: () => BirthStatusPayload | null,
  onPollError: (pollError: string | null) => void,
): Promise<BirthStatusPayload | null> {
  if (pollInFlight) {
    return getStatus();
  }

  pollAbortController?.abort();
  pollAbortController = new AbortController();
  const { signal } = pollAbortController;
  pollInFlight = true;

  try {
    const payload = await fetchBirthStatusTyped({ signal, connectTimeout: 30_000 });
    if (signal.aborted) {
      return getStatus();
    }
    consecutivePollFailures = 0;
    applyStatus(payload);
    return payload;
  } catch (err) {
    if (signal.aborted || isAbortError(err)) {
      return getStatus();
    }
    consecutivePollFailures += 1;
    const message = normalizePollError(err);
    const current = getStatus();
    const transient = isTransientHeavyBirthPhase(current);
    const shouldShow = Boolean(message) && (!transient || consecutivePollFailures >= 3);
    if (shouldShow) {
      onPollError(
        transient && consecutivePollFailures >= 3 ? TRANSIENT_POLL_WARNING : message,
      );
    }
    return null;
  } finally {
    pollInFlight = false;
  }
}

export async function pollFreshBirthStatus(
  poll: () => Promise<BirthStatusPayload | null>,
): Promise<BirthStatusPayload | null> {
  await waitForPollIdle();
  if (pollInFlight) {
    pollAbortController?.abort();
    pollInFlight = false;
    await waitForPollIdle(500);
  }
  return poll();
}
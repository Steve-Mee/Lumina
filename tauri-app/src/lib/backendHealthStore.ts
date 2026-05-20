import { probeBackendHealth } from "@/lib/setupClient";

type Listener = (state: BackendHealthSnapshot) => void;

export interface BackendHealthSnapshot {
  alive: boolean;
  known: boolean;
}

let backendAlive = false;
let backendHealthKnown = false;
const listeners = new Set<Listener>();
let subscriberCount = 0;
let intervalId: ReturnType<typeof setInterval> | null = null;

function snapshot(): BackendHealthSnapshot {
  return { alive: backendAlive, known: backendHealthKnown };
}

function emit(): void {
  const current = snapshot();
  for (const listener of listeners) {
    listener(current);
  }
}

async function probe(): Promise<void> {
  try {
    backendAlive = await probeBackendHealth();
  } catch {
    backendAlive = false;
  }
  backendHealthKnown = true;
  emit();
}

function ensurePolling(): void {
  if (intervalId !== null) {
    return;
  }
  void probe();
  intervalId = setInterval(() => void probe(), 5000);
}

function stopPollingIfIdle(): void {
  if (subscriberCount === 0 && intervalId !== null) {
    clearInterval(intervalId);
    intervalId = null;
  }
}

export function refreshBackendHealth(): Promise<void> {
  return probe();
}

export function getBackendAlive(): boolean {
  return backendAlive;
}

export function getBackendHealthKnown(): boolean {
  return backendHealthKnown;
}

export function getBackendHealthSnapshot(): BackendHealthSnapshot {
  return snapshot();
}

export function subscribeBackendHealth(listener: (alive: boolean) => void): () => void;
export function subscribeBackendHealth(
  listener: (state: BackendHealthSnapshot) => void,
  fullSnapshot: true,
): () => void;
export function subscribeBackendHealth(
  listener: ((alive: boolean) => void) | ((state: BackendHealthSnapshot) => void),
  fullSnapshot?: boolean,
): () => void {
  const wrapped: Listener = fullSnapshot
    ? (listener as (state: BackendHealthSnapshot) => void)
    : (state) => (listener as (alive: boolean) => void)(state.alive);

  listeners.add(wrapped);
  subscriberCount += 1;
  wrapped(snapshot());
  ensurePolling();
  return () => {
    listeners.delete(wrapped);
    subscriberCount -= 1;
    stopPollingIfIdle();
  };
}

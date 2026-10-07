import {
  probeBackendReachability,
  type BackendProbeVerdict,
} from "@/lib/setupClient";

type Listener = (state: BackendHealthSnapshot) => void;

export interface BackendHealthSnapshot {
  alive: boolean;
  known: boolean;
}

/** Two refused connections before the deck locks. One busy probe never counts. */
export const HARD_DOWN_POLLS = 2;

export interface BackendHealthMachine {
  alive: boolean;
  known: boolean;
  hardDownStreak: number;
}

export function applyProbeVerdict(
  state: BackendHealthMachine,
  verdict: BackendProbeVerdict,
): BackendHealthMachine {
  if (verdict === "up") {
    return { alive: true, known: true, hardDownStreak: 0 };
  }
  if (verdict === "timeout") {
    return { ...state, hardDownStreak: 0 };
  }
  const hardDownStreak = state.hardDownStreak + 1;
  if (hardDownStreak >= HARD_DOWN_POLLS) {
    return { alive: false, known: true, hardDownStreak };
  }
  return { ...state, hardDownStreak };
}

let machine: BackendHealthMachine = {
  alive: false,
  known: false,
  hardDownStreak: 0,
};
const listeners = new Set<Listener>();
let subscriberCount = 0;
let intervalId: ReturnType<typeof setInterval> | null = null;

function snapshot(): BackendHealthSnapshot {
  return { alive: machine.alive, known: machine.known };
}

function emit(): void {
  const current = snapshot();
  for (const listener of listeners) {
    listener(current);
  }
}

async function probe(): Promise<void> {
  const verdict = await probeBackendReachability();
  machine = applyProbeVerdict(machine, verdict);
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
  return machine.alive;
}

export function getBackendHealthKnown(): boolean {
  return machine.known;
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

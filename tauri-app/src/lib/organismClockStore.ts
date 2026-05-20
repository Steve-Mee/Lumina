import { readOrganismClock } from "@/lib/breatheCurve";
import type { TradingMode } from "@/store/coreStore";

export interface OrganismClockSnapshot {
  elapsedSec: number;
  phase: number;
  envelope: number;
  cycleSec: number;
}

type Listener = (snapshot: OrganismClockSnapshot) => void;

let originMs = performance.now();
let mode: TradingMode = "SIM";
let reducedMotion = false;
let frameId = 0;
let subscriberCount = 0;
let latest: OrganismClockSnapshot = buildSnapshot(0, mode);

const listeners = new Set<Listener>();

function buildSnapshot(elapsedSec: number, tradingMode: TradingMode): OrganismClockSnapshot {
  const { phase, envelope, cycleSec } = readOrganismClock(elapsedSec, tradingMode);
  return { elapsedSec, phase, envelope, cycleSec };
}

function emit(): void {
  for (const listener of listeners) {
    listener(latest);
  }
}

function tick(now: number): void {
  const elapsedSec = reducedMotion ? 0 : (now - originMs) / 1000;
  latest = buildSnapshot(elapsedSec, mode);
  emit();
  frameId = requestAnimationFrame(tick);
}

function ensureLoop(): void {
  if (subscriberCount > 0 && frameId === 0) {
    frameId = requestAnimationFrame(tick);
  }
}

function stopLoopIfIdle(): void {
  if (subscriberCount === 0 && frameId !== 0) {
    cancelAnimationFrame(frameId);
    frameId = 0;
  }
}

export function resetOrganismClockOrigin(): void {
  originMs = performance.now();
  latest = buildSnapshot(0, mode);
  emit();
}

export function setOrganismClockMode(nextMode: TradingMode): void {
  if (mode === nextMode) {
    return;
  }
  mode = nextMode;
  latest = buildSnapshot(latest.elapsedSec, mode);
  emit();
}

export function setOrganismClockReducedMotion(next: boolean): void {
  if (reducedMotion === next) {
    return;
  }
  reducedMotion = next;
  if (reducedMotion) {
    latest = buildSnapshot(0, mode);
    emit();
  } else {
    resetOrganismClockOrigin();
  }
}

export function getOrganismClock(tradingMode?: TradingMode): OrganismClockSnapshot {
  if (tradingMode !== undefined && tradingMode !== mode) {
    return buildSnapshot(latest.elapsedSec, tradingMode);
  }
  return latest;
}

export function subscribeOrganismClock(listener: Listener): () => void {
  listeners.add(listener);
  subscriberCount += 1;
  listener(latest);
  ensureLoop();
  return () => {
    listeners.delete(listener);
    subscriberCount -= 1;
    stopLoopIfIdle();
  };
}

/** Internal: bind store mode/reducedMotion from shell hooks. */
export function configureOrganismClock(nextMode: TradingMode, nextReducedMotion: boolean): void {
  setOrganismClockReducedMotion(nextReducedMotion);
  setOrganismClockMode(nextMode);
}

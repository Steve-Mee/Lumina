/** Honest Apprenticeship life-signs — runner + heartbeat only. */

export type ApprenticeshipLifeState = "live" | "computing" | "idle";

export interface ApprenticeshipLifeInput {
  running: boolean;
  activity?: unknown;
  nA?: unknown;
  nD?: unknown;
  updatedAt?: unknown;
  nowMs: number;
}

const COMPUTING_AFTER_MS = 45_000;

function asNumber(value: unknown): number | null {
  if (typeof value === "number" && Number.isFinite(value)) return value;
  if (typeof value === "string" && value.trim() !== "") {
    const n = Number(value);
    return Number.isFinite(n) ? n : null;
  }
  return null;
}

export function heartbeatAgeMs(updatedAt: unknown, nowMs: number): number | null {
  if (typeof updatedAt !== "string" || !updatedAt.trim()) return null;
  const t = Date.parse(updatedAt);
  if (!Number.isFinite(t)) return null;
  return Math.max(0, nowMs - t);
}

export function formatHeartbeatAge(ageMs: number | null): string {
  if (ageMs == null) return "no heartbeat yet";
  const sec = Math.floor(ageMs / 1000);
  if (sec < 5) return "just now";
  if (sec < 60) return `${sec}s ago`;
  const min = Math.floor(sec / 60);
  if (min < 60) return `${min}m ${sec % 60}s ago`;
  return `${min}m ago`;
}

export function resolveApprenticeshipLifeState(
  input: ApprenticeshipLifeInput,
): ApprenticeshipLifeState {
  if (!input.running) return "idle";
  const age = heartbeatAgeMs(input.updatedAt, input.nowMs);
  if (age != null && age >= COMPUTING_AFTER_MS) return "computing";
  return "live";
}

export function apprenticeshipLifeLine(input: ApprenticeshipLifeInput): string {
  const nA = asNumber(input.nA) ?? 0;
  const nD = asNumber(input.nD) ?? 0;
  const activity = input.running ? "session watch" : "idle";
  const age = formatHeartbeatAge(heartbeatAgeMs(input.updatedAt, input.nowMs));
  return `${activity} · n_A ${Math.round(nA).toLocaleString("en-US")}/150 · green ${Math.round(nD)}/5 · ${age}`;
}

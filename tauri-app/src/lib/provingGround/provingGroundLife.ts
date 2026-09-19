/** Honest Proving Ground life-signs — runner + heartbeat only. */

export type ProvingGroundLifeState = "live" | "computing" | "idle";

export interface ProvingGroundLifeInput {
  running: boolean;
  activity?: unknown;
  nG?: unknown;
  gate?: unknown;
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

export function resolveProvingGroundLifeState(
  input: ProvingGroundLifeInput,
): ProvingGroundLifeState {
  if (!input.running) return "idle";
  const age = heartbeatAgeMs(input.updatedAt, input.nowMs);
  if (age != null && age >= COMPUTING_AFTER_MS) return "computing";
  return "live";
}

export function provingGroundLifeLine(input: ProvingGroundLifeInput): string {
  const nG = asNumber(input.nG) ?? 0;
  const gate = asNumber(input.gate) ?? 0;
  const activity = input.running ? "exam watch" : "idle";
  const age = formatHeartbeatAge(heartbeatAgeMs(input.updatedAt, input.nowMs));
  return `${activity} · n_G ${Math.round(nG).toLocaleString("en-US")}/150 · gate ${Math.round(gate)}/4 · ${age}`;
}

/** Honest Awakening life-signs — no fake progress, only runner + heartbeat. */

export type AwakeningLifeState = "live" | "computing" | "idle";

export interface AwakeningLifeInput {
  running: boolean;
  cycle?: unknown;
  activity?: unknown;
  trainTimesteps?: unknown;
  probeBars?: unknown;
  nB?: unknown;
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

export function resolveAwakeningLifeState(input: AwakeningLifeInput): AwakeningLifeState {
  if (!input.running) return "idle";
  const age = heartbeatAgeMs(input.updatedAt, input.nowMs);
  if (age != null && age >= COMPUTING_AFTER_MS) return "computing";
  return "live";
}

function activityLabel(activity: unknown, running: boolean): string {
  if (activity === "train_A") return "train A";
  if (activity === "probe_A") return "day book";
  if (activity === "eval_B") return "eval B";
  if (running) return "eval B";
  return "idle";
}

export function awakeningLifeLine(input: AwakeningLifeInput): string {
  const steps = asNumber(input.trainTimesteps);
  const probeBars = asNumber(input.probeBars);
  const nB = asNumber(input.nB) ?? 0;
  const activity = activityLabel(input.activity, input.running);
  const age = formatHeartbeatAge(heartbeatAgeMs(input.updatedAt, input.nowMs));
  const stepBit =
    input.activity === "probe_A" && probeBars != null
      ? ` · bar ${Math.round(probeBars).toLocaleString("en-US")}`
      : steps != null && steps > 0
        ? ` · ${Math.round(steps).toLocaleString("en-US")} steps`
        : "";
  return `First Watch · ${activity}${stepBit} · n_B ${Math.round(nB).toLocaleString("en-US")}/500 · ${age}`;
}

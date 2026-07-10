import type { BirthProgressPayload } from "@/lib/birthClient";

export function normalizeToken(value: unknown): string {
  return String(value ?? "")
    .trim()
    .toLowerCase();
}

export function parseProgressTimestamp(progress: BirthProgressPayload | undefined): number | null {
  const raw = progress?.timestamp;
  if (!raw) return null;
  const ms = Date.parse(raw);
  return Number.isFinite(ms) ? ms : null;
}

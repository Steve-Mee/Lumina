/** Phase Hub pure helpers (Tauri UI god split). */
import type { AdvanceMode } from "@/lib/maturationClient";

export const ADVANCE_OPTIONS: { id: AdvanceMode; label: string; hint: string }[] = [
  {
    id: "manual",
    label: "Manual",
    hint: "Start each phase yourself on this PC",
  },
  {
    id: "telegram",
    label: "Telegram",
    hint: "Confirm the next phase via Telegram message",
  },
  {
    id: "auto_evolve",
    label: "Auto evolve",
    hint: "Chain phases automatically (REAL still needs you)",
  },
];

export function formatLearned(learned: Record<string, unknown> | undefined): string[] {
  if (!learned || typeof learned !== "object") return [];
  const lines: string[] = [];
  for (const [key, value] of Object.entries(learned)) {
    if (value == null || value === "") continue;
    if (key === "milestones" && Array.isArray(value)) {
      lines.push(`Milestones: ${value.join(", ")}`);
      continue;
    }
    if (typeof value === "object") {
      lines.push(`${key}: ${JSON.stringify(value)}`);
      continue;
    }
    lines.push(`${key}: ${String(value)}`);
  }
  return lines.slice(0, 12);
}

/** Human-readable countdown for Telegram advance TTL (M7). */
export function formatRemainingSec(sec: number | null | undefined): string {
  if (sec == null || Number.isNaN(sec)) return "";
  const s = Math.max(0, Math.floor(sec));
  if (s <= 0) return "expired";
  const h = Math.floor(s / 3600);
  const m = Math.floor((s % 3600) / 60);
  const r = s % 60;
  if (h > 0) return `${h}h ${m}m`;
  if (m > 0) return `${m}m ${r}s`;
  return `${r}s`;
}

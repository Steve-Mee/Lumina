import type { TradingMode } from "@/store/coreStore";

export interface ModePostResult {
  ok: boolean;
  mode?: string;
  error?: string;
}

export function resolveCoreModeUrl(): string {
  const base =
    import.meta.env.VITE_LUMINA_BACKEND_URL ?? "http://127.0.0.1:8000";
  return base.replace(/\/$/, "") + "/api/core/mode";
}

function toApiMode(mode: TradingMode): "sim" | "real" {
  return mode === "REAL" ? "real" : "sim";
}

export async function postOperatorMode(mode: TradingMode): Promise<ModePostResult> {
  try {
    const response = await fetch(resolveCoreModeUrl(), {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ mode: toApiMode(mode) }),
    });

    if (!response.ok) {
      const detail = await response.text();
      return {
        ok: false,
        error: detail || `HTTP ${response.status}`,
      };
    }

    const body = (await response.json()) as { ok?: boolean; mode?: string };
    return { ok: body.ok !== false, mode: body.mode };
  } catch (err) {
    const message = err instanceof Error ? err.message : "Network error";
    return { ok: false, error: message };
  }
}

import { resolveBackendBaseUrl } from "@/lib/setupClient";

export async function postAttentionReport(payload: {
  reason_code: "real_safe_mode" | "real_trading_blocked" | "backend_unreachable" | "setup_incomplete";
  detail?: string;
  context?: Record<string, unknown>;
}): Promise<{ ok: boolean; sent: boolean }> {
  const base = resolveBackendBaseUrl();
  const response = await fetch(`${base}/api/notifications/attention`, {
    method: "POST",
    headers: { Accept: "application/json", "Content-Type": "application/json" },
    body: JSON.stringify(payload),
  });
  if (!response.ok) {
    throw new Error(`Attention report HTTP ${response.status}`);
  }
  return response.json() as Promise<{ ok: boolean; sent: boolean }>;
}

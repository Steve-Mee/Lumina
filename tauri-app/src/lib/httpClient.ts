import { isTauri } from "@tauri-apps/api/core";

/**
 * HTTP fetch that uses Tauri plugin-http in the desktop shell (bypasses WebView CORS)
 * and falls back to window.fetch in the browser / Vitest.
 */
export async function luminaFetch(
  input: string,
  init?: RequestInit,
): Promise<Response> {
  if (isTauri()) {
    const { fetch: tauriFetch } = await import("@tauri-apps/plugin-http");
    return tauriFetch(input, init as RequestInit);
  }
  return fetch(input, init);
}

/** Extract a human-readable message from FastAPI/plain HTTP error bodies. */
export async function readHttpErrorDetail(response: Response): Promise<string> {
  const raw = await response.text().catch(() => "");
  if (!raw.trim()) {
    return `HTTP ${response.status}`;
  }
  try {
    const parsed = JSON.parse(raw) as { detail?: unknown };
    const { detail } = parsed;
    if (typeof detail === "string" && detail.trim()) {
      return detail;
    }
    if (Array.isArray(detail)) {
      const parts = detail
        .map((item) => {
          if (typeof item === "string") return item;
          if (item && typeof item === "object" && "msg" in item) {
            return String((item as { msg: unknown }).msg);
          }
          return JSON.stringify(item);
        })
        .filter(Boolean);
      if (parts.length > 0) {
        return parts.join("; ");
      }
    }
  } catch {
    // not JSON — use raw body
  }
  return raw.trim();
}

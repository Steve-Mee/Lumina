import { beforeEach, describe, expect, it, vi } from "vitest";

import { isBirthStartSuccessful, resumeBirthSession, retryBirthSession, stopBirthSession } from "@/lib/birthClient";

const luminaFetch = vi.fn();

vi.mock("@/lib/httpClient", () => ({
  luminaFetch: (...args: unknown[]) => luminaFetch(...args),
  readHttpErrorDetail: async (response: Response) => {
    const text = await response.text();
    try {
      const parsed = JSON.parse(text) as { detail?: string };
      return parsed.detail ?? text;
    } catch {
      return text;
    }
  },
}));

vi.mock("@/lib/setupClient", () => ({
  resolveBackendBaseUrl: () => "http://127.0.0.1:8000",
}));

describe("birthClient recovery routes", () => {
  beforeEach(() => {
    luminaFetch.mockReset();
  });

  it("isBirthStartSuccessful accepts start_acknowledged over terminal status", () => {
    expect(isBirthStartSuccessful("certificate_failed", { start_acknowledged: true })).toBe(true);
    expect(isBirthStartSuccessful("certificate_failed")).toBe(false);
  });

  it("resumeBirthSession uses retry without wipe", async () => {
    luminaFetch.mockResolvedValueOnce(
      new Response(JSON.stringify({ status: "started" }), { status: 200 }),
    );

    const payload = await resumeBirthSession(25000);

    expect(payload.status).toBe("started");
    expect(luminaFetch).toHaveBeenCalledWith(
      "http://127.0.0.1:8000/api/birth/retry?target_trades=25000",
      { method: "POST" },
    );
  });

  it("retryBirthSession falls back to start when retry route is missing", async () => {
    luminaFetch
      .mockResolvedValueOnce(
        new Response(JSON.stringify({ detail: "Not Found" }), { status: 404 }),
      )
      .mockResolvedValueOnce(
        new Response(JSON.stringify({ status: "started" }), { status: 200 }),
      );

    const payload = await retryBirthSession(25000, { wipe: false });

    expect(payload.status).toBe("started");
    expect(luminaFetch).toHaveBeenCalledTimes(2);
    expect(String(luminaFetch.mock.calls[1]?.[0])).toContain("/api/birth/start?");
    expect(String(luminaFetch.mock.calls[1]?.[0])).toContain("continue_training=true");
  });

  it("stopBirthSession posts to birth stop via luminaFetch", async () => {
    luminaFetch.mockResolvedValueOnce(
      new Response(JSON.stringify({ status: "stopped", message: "ok" }), { status: 200 }),
    );

    const payload = await stopBirthSession();

    expect(payload.status).toBe("stopped");
    expect(luminaFetch).toHaveBeenCalledWith("http://127.0.0.1:8000/api/birth/stop", {
      method: "POST",
    });
  });
});

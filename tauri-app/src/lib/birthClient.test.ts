import { beforeEach, describe, expect, it, vi } from "vitest";

import {
  fetchBirthStatusTyped,
  isBirthStartSuccessful,
  resumeBirthSession,
  retryBirthSession,
  stopBirthSession,
} from "@/lib/birthClient";

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

  it("resumeBirthSession uses /api/birth/resume", async () => {
    luminaFetch.mockResolvedValueOnce(
      new Response(JSON.stringify({ status: "started" }), { status: 200 }),
    );

    const payload = await resumeBirthSession(25000);

    expect(payload.status).toBe("started");
    expect(luminaFetch).toHaveBeenCalledWith(
      "http://127.0.0.1:8000/api/birth/resume?target_trades=25000",
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

  it("fetchBirthStatusTyped promotes legacy edgescore lift keys to tournament SSOT", async () => {
    luminaFetch.mockResolvedValueOnce(
      new Response(
        JSON.stringify({
          status: "running",
          progress: {
            swarm_edgescore_lift_ok: false,
            swarm_edgescore_at_start: 0.37,
            attention_reason_code: "swarm_no_edgescore_lift",
            attention_summary: "Swarm tournament produced no EdgeScore lift",
            needs_attention: true,
          },
        }),
        { status: 200 },
      ),
    );

    const payload = await fetchBirthStatusTyped();

    expect(payload.progress?.swarm_tournament_lift_ok).toBe(false);
    expect(payload.progress?.swarm_tournament_at_start).toBe(0.37);
    expect(payload.progress?.attention_reason_code).toBe("swarm_no_tournament_lift");
    expect(payload.progress?.attention_summary).toContain("no tournament lift");
    expect(String(payload.progress?.attention_summary ?? "").toLowerCase()).not.toContain(
      "edgescore lift",
    );
  });
});

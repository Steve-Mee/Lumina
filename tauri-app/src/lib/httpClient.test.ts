import { describe, expect, it } from "vitest";

import { readHttpErrorDetail } from "@/lib/httpClient";

describe("readHttpErrorDetail", () => {
  it("parses FastAPI string detail", async () => {
    const response = new Response(JSON.stringify({ detail: "Missing credential" }), {
      status: 400,
    });
    await expect(readHttpErrorDetail(response)).resolves.toBe("Missing credential");
  });

  it("returns raw body when not JSON", async () => {
    const response = new Response("Internal Server Error", { status: 500 });
    await expect(readHttpErrorDetail(response)).resolves.toBe("Internal Server Error");
  });

  it("falls back to HTTP status when body empty", async () => {
    const response = new Response("", { status: 503 });
    await expect(readHttpErrorDetail(response)).resolves.toBe("HTTP 503");
  });
});

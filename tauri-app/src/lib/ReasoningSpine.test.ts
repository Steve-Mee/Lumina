import { readFileSync } from "node:fs";
import { dirname, join } from "node:path";
import { fileURLToPath } from "node:url";
import { describe, expect, it } from "vitest";

const reasoningSpineSource = readFileSync(
  join(dirname(fileURLToPath(import.meta.url)), "../components/decision/ReasoningSpine.tsx"),
  "utf8",
);

describe("ReasoningSpine source contract", () => {
  it("accepts motionReduced prop for low-quality / reduced-motion path", () => {
    expect(reasoningSpineSource).toContain("motionReduced?: boolean");
    expect(reasoningSpineSource).toContain("motionReduced ?? reducedMotionPref");
  });
});

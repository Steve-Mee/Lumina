import { readFileSync } from "node:fs";
import { dirname, join } from "node:path";
import { fileURLToPath } from "node:url";

import { describe, expect, it } from "vitest";

const birthLaunchButtonSource = readFileSync(
  join(dirname(fileURLToPath(import.meta.url)), "BirthLaunchButton.tsx"),
  "utf8",
);

describe("BirthLaunchButton interaction contract", () => {
  it("starts activation sequence on click", () => {
    expect(birthLaunchButtonSource).toMatch(/handleClick[\s\S]*beginSequence\(\)/);
  });

  it("fires activate immediately while cosmetic sequence runs", () => {
    expect(birthLaunchButtonSource).toContain("PRELAUNCH_MS = 600");
    expect(birthLaunchButtonSource).toMatch(/beginSequence[\s\S]*onClick\(\)/);
    expect(birthLaunchButtonSource).toContain("finishCosmeticSequence");
  });

  it("guards against duplicate sequence triggers", () => {
    expect(birthLaunchButtonSource).toContain("sequenceStartedRef");
    expect(birthLaunchButtonSource).toMatch(/beginSequence[\s\S]*sequenceStartedRef\.current/);
    expect(birthLaunchButtonSource).toMatch(/activating[\s\S]*sequenceStartedRef\.current = false/);
  });

  it("handles pointer cancel on Windows/Tauri", () => {
    expect(birthLaunchButtonSource).toContain("onPointerCancel={handlePointerRelease}");
  });

  it("explains click and hold affordance in sublabel", () => {
    expect(birthLaunchButtonSource).toContain("Hold until the ring completes");
  });

  it("keeps particle effects out of document flow", () => {
    expect(birthLaunchButtonSource).toContain("birth-launch-btn__fx");
    expect(birthLaunchButtonSource).toContain('className="birth-launch-particle"');
  });
});

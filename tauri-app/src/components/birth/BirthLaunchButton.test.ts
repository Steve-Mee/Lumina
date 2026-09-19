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

  it("commits a press on pointer up and Windows/Tauri pointer cancel", () => {
    expect(birthLaunchButtonSource).toContain("onPointerUp={commitPointerPress}");
    expect(birthLaunchButtonSource).toContain("onPointerCancel={commitPointerPress}");
    expect(birthLaunchButtonSource).toMatch(/commitPointerPress[\s\S]*beginSequence\(\)/);
  });

  it("cancels hold on pointer leave without starting", () => {
    expect(birthLaunchButtonSource).toContain("onPointerLeave={handlePointerLeave}");
    expect(birthLaunchButtonSource).toMatch(/handlePointerLeave[\s\S]*cancelHold\(\)/);
  });

  it("explains click affordance in sublabel", () => {
    expect(birthLaunchButtonSource).toContain("Click to start");
  });

  it("keeps particle effects out of document flow", () => {
    expect(birthLaunchButtonSource).toContain("birth-launch-btn__fx");
    expect(birthLaunchButtonSource).toContain('className="birth-launch-particle"');
  });
});

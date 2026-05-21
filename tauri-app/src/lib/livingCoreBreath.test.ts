import { readFileSync } from "node:fs";
import { dirname, join } from "node:path";
import { fileURLToPath } from "node:url";
import { describe, expect, it } from "vitest";

const livingCoreSource = readFileSync(
  join(dirname(fileURLToPath(import.meta.url)), "../components/LivingCore.tsx"),
  "utf8",
);
const cockpitCss = readFileSync(
  join(dirname(fileURLToPath(import.meta.url)), "../styles/cockpit.css"),
  "utf8",
);

describe("living core breath contract", () => {
  it("HeartCore uses shared organism envelope instead of raw Math.sin heartbeat", () => {
    const heartCoreBlock =
      livingCoreSource.split("function HeartCore")[1]?.split("function AuraHalo")[0] ?? "";
    expect(livingCoreSource).toContain("vigilantHeartbeatPulse");
    expect(heartCoreBlock).toContain("breathDrive");
    expect(heartCoreBlock).not.toContain("Math.sin");
  });

  it("shell halo follows envelope without competing pulse keyframes", () => {
    expect(cockpitCss).toContain("var(--organism-envelope");
    expect(cockpitCss).toMatch(
      /\.living-core-halo--pulse[\s\S]*no competing keyframe pulse/,
    );
    expect(cockpitCss).not.toMatch(
      /\.living-core-halo--pulse\s*\{[^}]*animation:\s*living-core-halo-pulse/,
    );
  });

  it("REAL mode shell ring contracts on envelope peak", () => {
    expect(cockpitCss).toContain('.living-core-shell[data-mode="REAL"]::after');
    expect(cockpitCss).toContain("calc(0.98 + var(--organism-envelope) * 0.02)");
  });
});

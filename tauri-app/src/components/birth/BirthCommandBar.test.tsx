import { readFileSync } from "node:fs";
import { dirname, join } from "node:path";
import { fileURLToPath } from "node:url";

import { describe, expect, it } from "vitest";

const birthCommandBarSource = readFileSync(
  join(dirname(fileURLToPath(import.meta.url)), "./BirthCommandBar.tsx"),
  "utf8",
);

const birthMissionControlSource = readFileSync(
  join(dirname(fileURLToPath(import.meta.url)), "./BirthMissionControl.tsx"),
  "utf8",
);

const birthControlDockSource = readFileSync(
  join(dirname(fileURLToPath(import.meta.url)), "./BirthControlDock.tsx"),
  "utf8",
);

describe("BirthCommandBar", () => {
  it("keeps advanced toggles on the HUD; stop lives in mission control toolbar", () => {
    expect(birthCommandBarSource).not.toContain("BirthControlDock");
    expect(birthMissionControlSource).toContain("BirthControlDock");
    expect(birthMissionControlSource).toContain("showStopControl");
    expect(birthControlDockSource).toContain("Stop birth");
    expect(birthControlDockSource).toContain("birth-control-dock__stop--panel");
  });

  it("uses a single-row mission HUD with full milestone chips + separate tool buttons", () => {
    expect(birthCommandBarSource).toContain("birth-command-bar__row");
    expect(birthCommandBarSource).toContain("birth-command-bar__milestones");
    expect(birthCommandBarSource).toContain("buildHudMilestones");
    expect(birthCommandBarSource).toContain("upcomingCount={0}");
    expect(birthCommandBarSource).toContain("birth-command-bar__tool-btn");
    expect(birthCommandBarSource).toContain("birth-command-bar__tool-btn--active");
    expect(birthCommandBarSource).toContain('"logs"');
    expect(birthCommandBarSource).toContain('"settings"');
    expect(birthCommandBarSource).toContain('"training"');
    expect(birthCommandBarSource).not.toContain("Telemetry");
    expect(birthCommandBarSource).not.toContain("birth-command-bar__segment");
    expect(birthCommandBarSource).not.toContain("birth-command-bar__top");
  });

  it("uses interactive affordances on tool buttons and panel stop control", () => {
    expect(birthCommandBarSource).toContain('luminaInteractiveClass("ghost")');
    expect(birthControlDockSource).toContain('luminaInteractiveClass("danger")');
    expect(birthControlDockSource).toContain("birth-control-dock__stop");
    expect(birthControlDockSource).toContain("openStopConfirm");
    expect(birthControlDockSource).toContain("useBirthUiStore");
  });
});

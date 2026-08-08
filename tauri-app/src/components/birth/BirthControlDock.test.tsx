import { readFileSync } from "node:fs";
import { dirname, join } from "node:path";
import { fileURLToPath } from "node:url";

import { describe, expect, it } from "vitest";

const source = readFileSync(
  join(dirname(fileURLToPath(import.meta.url)), "./BirthControlDock.tsx"),
  "utf8",
);

describe("BirthControlDock wipe UX", () => {
  it("delegates wipe confirm to global BirthConfirmHost via birthUiStore", () => {
    expect(source).toContain("useBirthUiStore");
    expect(source).toContain("openWipeConfirm");
    expect(source).toContain("openStopConfirm");
    expect(source).not.toContain("BirthPortaledDialog");
    expect(source).not.toContain("setWipeStep");
  });

  it("shows toast feedback when wipe is blocked by busy or activating", () => {
    expect(source).toContain("handleWipeClick");
    expect(source).toContain("toast.info");
    expect(source).toContain("Birth is starting");
    expect(source).toContain("Please wait — another birth action is in progress.");
  });

  it("shows toast feedback when stop is blocked by busy", () => {
    expect(source).toContain("handleStopClick");
    expect(source).toContain("Please wait — another birth action is in progress.");
  });

  it("exposes stop on genesis surface when engineLive", () => {
    expect(source).toContain("engineLive");
    expect(source).toContain("{engineLive ? stopButton : null}");
  });

  it("offers reset and full wipe with confirm flow via birthUiStore", () => {
    expect(source).toContain('handleWipeClick("reset")');
    expect(source).toContain('handleWipeClick("full")');
    expect(source).toContain("Full wipe");
    expect(source).toContain("Wipe birth data");
    expect(source).toContain("Resume checkpoint");
  });

  it("emits structured birth-wipe trace logs", () => {
    expect(source).toContain("traceBirthWipe");
    expect(source).toContain("ui.wipe_button.pointerdown");
    expect(source).toContain("ui.wipe_button.click");
  });
});

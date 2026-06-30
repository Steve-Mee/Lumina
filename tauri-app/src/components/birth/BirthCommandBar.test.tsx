import { readFileSync } from "node:fs";

import { dirname, join } from "node:path";

import { fileURLToPath } from "node:url";



import { describe, expect, it } from "vitest";



const birthCommandBarSource = readFileSync(

  join(dirname(fileURLToPath(import.meta.url)), "./BirthCommandBar.tsx"),

  "utf8",

);



const birthControlDockSource = readFileSync(

  join(dirname(fileURLToPath(import.meta.url)), "./BirthControlDock.tsx"),

  "utf8",

);



describe("BirthCommandBar", () => {

  it("wires running controls to BirthControlDock stop flow", () => {

    expect(birthCommandBarSource).toContain('mode="running"');

    expect(birthCommandBarSource).toContain("BirthControlDock");

    expect(birthCommandBarSource).toContain("onStop={onStop}");

    expect(birthControlDockSource).toContain("Stop birth");

  });



  it("exposes spaced inline advanced toggles instead of telemetry drawer", () => {

    expect(birthCommandBarSource).toContain("birth-command-bar__action-btn");

    expect(birthCommandBarSource).toContain("gap-1.5");

    expect(birthCommandBarSource).toContain('"logs"');

    expect(birthCommandBarSource).toContain('"settings"');

    expect(birthCommandBarSource).toContain('"training"');

    expect(birthCommandBarSource).not.toContain("Telemetry");

  });



  it("uses interactive affordances on command bar actions and stop control", () => {

    expect(birthCommandBarSource).toContain('luminaInteractiveClass("ghost")');

    expect(birthControlDockSource).toContain('luminaInteractiveClass("danger")');

    expect(birthControlDockSource).not.toContain('className="z-[60]"');

    expect(birthControlDockSource).toMatch(/birth-control-dock__stop[\s\S]*?aria-busy=\{busy\}/);

    expect(birthControlDockSource).toContain("setStopOpen(true)");

  });

});


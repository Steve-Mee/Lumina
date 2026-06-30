import { readFileSync } from "node:fs";
import { dirname, join } from "node:path";
import { fileURLToPath } from "node:url";

import { describe, expect, it } from "vitest";

const dialogSource = readFileSync(
  join(dirname(fileURLToPath(import.meta.url)), "../components/ui/dialog.tsx"),
  "utf8",
);

const birthControlDockSource = readFileSync(
  join(dirname(fileURLToPath(import.meta.url)), "../components/birth/BirthControlDock.tsx"),
  "utf8",
);

describe("dialogStacking", () => {
  it("keeps dialog content above the overlay scrim", () => {
    expect(dialogSource).toMatch(/DialogOverlay[\s\S]*z-\[100\]/);
    expect(dialogSource).toMatch(/dialogContentClassName[\s\S]*z-\[101\]/);
    expect(dialogSource).toMatch(/withoutZIndex[\s\S]*replace/);
  });

  it("does not let BirthControlDock downgrade dialog content below the overlay", () => {
    expect(birthControlDockSource).not.toContain('className="z-[60]"');
    expect(birthControlDockSource).toContain("<DialogContent>");
  });
});

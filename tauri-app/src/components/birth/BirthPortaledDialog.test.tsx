import { readFileSync } from "node:fs";
import { dirname, join } from "node:path";
import { fileURLToPath } from "node:url";

import { describe, expect, it } from "vitest";

const dialogSource = readFileSync(
  join(dirname(fileURLToPath(import.meta.url)), "./BirthPortaledDialog.tsx"),
  "utf8",
);

const cssSource = readFileSync(
  join(dirname(fileURLToPath(import.meta.url)), "../../styles/birthPhase.css"),
  "utf8",
);

describe("BirthPortaledDialog", () => {
  it("portals a centered Lumina glass modal with SIM design tokens", () => {
    expect(dialogSource).toContain("getLuminaOverlayRoot");
    expect(dialogSource).toContain("cockpit-shell");
    expect(dialogSource).toContain('data-mode="SIM"');
    expect(dialogSource).toContain("lumina-glass--overlay");
    expect(dialogSource).toContain("lumina-glow-halo");
    expect(dialogSource).toContain("birth-portaled-dialog__panel");
    expect(cssSource).toContain("transform: translate(-50%, -50%)");
    expect(cssSource).toContain(".birth-portaled-dialog__footer");
  });
});

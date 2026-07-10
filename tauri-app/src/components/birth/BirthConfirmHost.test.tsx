import { readFileSync } from "node:fs";
import { dirname, join } from "node:path";
import { fileURLToPath } from "node:url";

import { describe, expect, it } from "vitest";

const appSource = readFileSync(
  join(dirname(fileURLToPath(import.meta.url)), "../../App.tsx"),
  "utf8",
);

const hostSource = readFileSync(
  join(dirname(fileURLToPath(import.meta.url)), "./BirthConfirmHost.tsx"),
  "utf8",
);

describe("BirthConfirmHost", () => {
  it("is mounted globally from App outside onboarding remounts", () => {
    expect(appSource).toContain("BirthConfirmHost");
    expect(hostSource).toContain("useBirthUiStore");
    expect(hostSource).toContain("wipeConfirmKind");
    expect(hostSource).toContain("preserveTickCache");
    expect(hostSource).toContain("ui.wipe_dialog.mounted");
  });
});

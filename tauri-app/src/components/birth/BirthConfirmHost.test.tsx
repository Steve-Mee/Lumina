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

const dialogSource = readFileSync(
  join(dirname(fileURLToPath(import.meta.url)), "./BirthPortaledDialog.tsx"),
  "utf8",
);

const overlaySource = readFileSync(
  join(dirname(fileURLToPath(import.meta.url)), "./BirthPhaseRecoveryOverlays.tsx"),
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

  it("keeps the wipe CTA outside the scroll body so it stays clickable", () => {
    const footerIndex = dialogSource.indexOf('className="birth-portaled-dialog__footer"');
    const bodyIndex = dialogSource.indexOf('className="birth-portaled-dialog__body"');
    expect(bodyIndex).toBeGreaterThan(-1);
    expect(footerIndex).toBeGreaterThan(bodyIndex);
    expect(dialogSource).toContain("birth-portaled-dialog__layout");
  });

  it("does not let the stall overlay steal clicks while a confirm dialog is open", () => {
    expect(overlaySource).toContain("wipeConfirmOpen");
    expect(overlaySource).toContain("pointer-events-none");
  });
});

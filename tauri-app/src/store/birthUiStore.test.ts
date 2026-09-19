import { beforeEach, describe, expect, it } from "vitest";

import { useBirthUiStore } from "@/store/birthUiStore";

describe("birthUiStore wipe confirm", () => {
  beforeEach(() => {
    useBirthUiStore.getState().resetBirthUi();
  });

  it("does not reset step 2 when stall overlay re-fires openWipeConfirm", () => {
    useBirthUiStore.getState().openWipeConfirm("full");
    useBirthUiStore.getState().setWipeConfirmStep(2);
    useBirthUiStore.getState().openWipeConfirm("full");
    expect(useBirthUiStore.getState().wipeConfirmStep).toBe(2);
    expect(useBirthUiStore.getState().wipeConfirmKind).toBe("full");
  });
});

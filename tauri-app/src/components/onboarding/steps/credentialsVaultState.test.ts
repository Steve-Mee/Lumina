import { describe, expect, it } from "vitest";

import {
  buildVaultFocusRows,
  defaultVaultFocus,
  diagnosticDisplayState,
  fieldFillState,
  focusTitle,
  linkChipStateFromLive,
  linkSummary,
  linkSummaryLive,
  sealReadiness,
  securityChipState,
} from "@/components/onboarding/steps/credentialsVaultState";
import type { OnboardingDraft } from "@/store/onboardingStore";

const emptyCreds = {
  LUMINA_JWT_SECRET_KEY: "",
  LUMINA_ADMIN_API_KEY: "",
  LUMINA_FABRIC_TOKEN: "",
  TELEGRAM_BOT_TOKEN: "",
  TELEGRAM_CHAT_ID: "",
  CROSSTRADE_TOKEN: "",
  CROSSTRADE_ACCOUNT: "",
} as OnboardingDraft["credentials"];

describe("credentialsVaultState", () => {
  it("builds field-level focus rows including fabric token and twin base", () => {
    const rows = buildVaultFocusRows({
      creds: emptyCreds,
      present: {},
      emergencyFeed: false,
      twinBirthReady: false,
    });
    expect(rows.map((r) => r.id)).toEqual([
      "jwt",
      "admin",
      "fabric_token",
      "twin_base",
      "telegram_bot",
      "telegram_chat",
    ]);
    expect(rows.find((r) => r.id === "fabric_token")?.state).toBe("partial");
    expect(rows.find((r) => r.id === "twin_base")?.state).toBe("idle");
    expect(rows.find((r) => r.id === "telegram_bot")?.state).toBe("idle");
  });

  it("defaults focus to diagnostic path when link not green", () => {
    expect(
      defaultVaultFocus({
        fabricGreen: false,
        ntInstalled: true,
        linkState: "fail",
      }),
    ).toBe("diagnostic");
    expect(
      defaultVaultFocus({
        fabricGreen: false,
        ntInstalled: false,
        linkState: "idle",
      }),
    ).toBe("nt_install");
  });

  it("marks required empty fields as partial", () => {
    expect(fieldFillState("")).toBe("partial");
    expect(fieldFillState("set")).toBe("ok");
    expect(focusTitle("fabric_token")).toMatch(/Fabric/i);
  });

  it("never treats paper proof alone as live GREEN chip", () => {
    expect(linkChipStateFromLive("RED", false, { overall: "green" } as never)).toBe(
      "fail",
    );
    expect(linkChipStateFromLive("AMBER", true, { overall: "green" } as never)).toBe(
      "partial",
    );
    expect(linkChipStateFromLive("GREEN", true, null)).toBe("ok");
    expect(
      linkSummary(false, { overall: "green", checks: [] } as never, true),
    ).toMatch(/Proof OK/i);
    expect(
      linkSummaryLive({
        liveLevel: "RED",
        meaning: "Bridge not running",
        hostReady: false,
        proofCertified: true,
        fabricReport: {
          overall: "green",
          checks: [
            { id: "a", title: "a", status: "pass", message: "ok" },
            { id: "b", title: "b", status: "pass", message: "ok" },
          ],
        } as never,
      }),
    ).toMatch(/Live RED/);
  });

  it("security chip and seal readiness stay fail-closed", () => {
    expect(securityChipState(emptyCreds, {})).toBe("idle");
    expect(
      sealReadiness({
        fabricGreen: false,
        ntInstalled: false,
        secState: "ok",
        fabricState: "ok",
        canContinue: false,
      }).state,
    ).toBe("fail");
    expect(
      sealReadiness({
        fabricGreen: false,
        ntInstalled: true,
        secState: "ok",
        fabricState: "ok",
        canContinue: false,
      }).body,
    ).toMatch(/proof|host/i);
    expect(
      sealReadiness({
        fabricGreen: true,
        ntInstalled: true,
        secState: "ok",
        fabricState: "ok",
        canContinue: true,
        twinBirthReady: false,
      }).state,
    ).toBe("partial");
    expect(
      sealReadiness({
        fabricGreen: true,
        ntInstalled: true,
        secState: "ok",
        fabricState: "ok",
        canContinue: true,
        twinBirthReady: true,
      }).state,
    ).toBe("ok");
  });

  it("defaults focus to twin_base after fabric green when twin incomplete", () => {
    expect(
      defaultVaultFocus({
        fabricGreen: true,
        ntInstalled: true,
        linkState: "ok",
        twinBirthReady: false,
      }),
    ).toBe("twin_base");
  });

  it("formats diagnostic display state and link summary", () => {
    expect(diagnosticDisplayState(false, null)).toBe("partial");
    expect(diagnosticDisplayState(true, null)).toBe("ok");
    expect(linkSummary(false, null, false)).toMatch(/Not tested/i);
    expect(linkSummary(true, null, true)).toMatch(/GREEN/i);
  });
});

import { describe, expect, it } from "vitest";

import {
  credentialsReadyInDraft,
  credentialsReadyInEnv,
  mergeCredentialsIntoDraft,
} from "@/lib/credentialsPrefill";

const emptyDraft = () => ({
  LUMINA_JWT_SECRET_KEY: "",
  CROSSTRADE_TOKEN: "",
  CROSSTRADE_ACCOUNT: "",
  LUMINA_ADMIN_API_KEY: "",
  LUMINA_FABRIC_TOKEN: "",
  XAI_API_KEY: "",
  TELEGRAM_BOT_TOKEN: "",
  TELEGRAM_CHAT_ID: "",
});

describe("credentialsReadyInEnv", () => {
  it("returns true when all required keys are present", () => {
    expect(
      credentialsReadyInEnv({
        LUMINA_JWT_SECRET_KEY: true,
        LUMINA_ADMIN_API_KEY: true,
        LUMINA_FABRIC_TOKEN: true,
      }),
    ).toBe(true);
  });

  it("returns false when a required key is missing", () => {
    expect(
      credentialsReadyInEnv({
        LUMINA_JWT_SECRET_KEY: true,
        LUMINA_ADMIN_API_KEY: true,
        LUMINA_FABRIC_TOKEN: false,
      }),
    ).toBe(false);
  });
});

describe("credentialsReadyInDraft", () => {
  it("returns true when draft fields are filled", () => {
    expect(
      credentialsReadyInDraft({
        ...emptyDraft(),
        LUMINA_JWT_SECRET_KEY: "jwt",
        LUMINA_ADMIN_API_KEY: "sk_test",
        LUMINA_FABRIC_TOKEN: "fabric",
      }),
    ).toBe(true);
  });
});

describe("mergeCredentialsIntoDraft", () => {
  it("fills empty fields from prefill", () => {
    const merged = mergeCredentialsIntoDraft(emptyDraft(), {
      LUMINA_JWT_SECRET_KEY: "jwt-from-env",
      CROSSTRADE_ACCOUNT: "acct-123",
    });
    expect(merged.LUMINA_JWT_SECRET_KEY).toBe("jwt-from-env");
    expect(merged.CROSSTRADE_ACCOUNT).toBe("acct-123");
    expect(merged.CROSSTRADE_TOKEN).toBe("");
  });

  it("does not overwrite operator edits", () => {
    const draft = {
      ...emptyDraft(),
      CROSSTRADE_ACCOUNT: "operator-value",
    };
    const merged = mergeCredentialsIntoDraft(draft, {
      CROSSTRADE_ACCOUNT: "env-value",
      CROSSTRADE_TOKEN: "token-env",
    });
    expect(merged.CROSSTRADE_ACCOUNT).toBe("operator-value");
    expect(merged.CROSSTRADE_TOKEN).toBe("token-env");
  });

  it("ignores whitespace-only prefill values", () => {
    const merged = mergeCredentialsIntoDraft(emptyDraft(), {
      LUMINA_JWT_SECRET_KEY: "   ",
      CROSSTRADE_TOKEN: "tok",
    });
    expect(merged.LUMINA_JWT_SECRET_KEY).toBe("");
    expect(merged.CROSSTRADE_TOKEN).toBe("tok");
  });
});

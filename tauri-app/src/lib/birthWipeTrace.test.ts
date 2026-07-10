import { afterEach, describe, expect, it, vi } from "vitest";

import { clearBirthWipeTrace, getBirthWipeTrace, traceBirthWipe } from "@/lib/birthWipeTrace";

describe("birthWipeTrace", () => {
  afterEach(() => {
    clearBirthWipeTrace();
    vi.restoreAllMocks();
  });

  it("records trace entries with phase and detail", () => {
    const infoSpy = vi.spyOn(console, "info").mockImplementation(() => {});
    traceBirthWipe("test.phase", { foo: "bar" });
    const entries = getBirthWipeTrace();
    expect(entries).toHaveLength(1);
    expect(entries[0]?.phase).toBe("test.phase");
    expect(entries[0]?.detail).toEqual({ foo: "bar" });
    expect(infoSpy).toHaveBeenCalled();
  });
});

import { readFileSync } from "node:fs";
import { dirname, join } from "node:path";
import { fileURLToPath } from "node:url";

import { describe, expect, it } from "vitest";

const source = readFileSync(
  join(dirname(fileURLToPath(import.meta.url)), "./usePointerDismissGuard.ts"),
  "utf8",
);

describe("usePointerDismissGuard", () => {
  it("arms a short dismiss window for Radix dialog open-from-click races", () => {
    expect(source).toContain("POINTER_DISMISS_GUARD_MS = 400");
    expect(source).toContain("armPointerDismissGuard");
    expect(source).toContain("shouldSuppressPointerDismiss");
    expect(source).toContain("consumePointerDismiss");
    expect(source).toContain("runAfterPointerRelease");
    expect(source).toMatch(/onPointerDownOutside:\s*consumePointerDismiss/);
    expect(source).toMatch(/onInteractOutside:\s*consumePointerDismiss/);
    expect(source).toContain("requestAnimationFrame");
    expect(source).toContain("event.preventDefault()");
  });
});

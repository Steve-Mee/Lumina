import { readFileSync } from "node:fs";
import { dirname, join } from "node:path";
import { fileURLToPath } from "node:url";

import { describe, expect, it } from "vitest";

const chipsSource = readFileSync(
  join(dirname(fileURLToPath(import.meta.url)), "./BirthGenesisStatusChips.tsx"),
  "utf8",
);

describe("BirthGenesisStatusChips", () => {
  it("shows compact chips with full context in title tooltips", () => {
    expect(chipsSource).toContain("birth-genesis-status-chip");
    expect(chipsSource).toContain("title={plateauTitle}");
    expect(chipsSource).toContain("birth-resume-checkpoint-hint");
    expect(chipsSource).not.toContain("rounded-lg border px-3 py-2");
  });
});

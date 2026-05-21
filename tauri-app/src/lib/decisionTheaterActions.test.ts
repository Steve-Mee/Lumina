import { readFileSync } from "node:fs";
import { dirname, join } from "node:path";
import { fileURLToPath } from "node:url";
import { describe, expect, it } from "vitest";

const stageSource = readFileSync(
  join(dirname(fileURLToPath(import.meta.url)), "../components/decision/DecisionTheaterStage.tsx"),
  "utf8",
);

describe("decisionTheaterActions", () => {
  it("approve uses modeApproveButtonClass not hardcoded emerald", () => {
    expect(stageSource).toContain("modeApproveButtonClass");
    expect(stageSource).not.toContain("border-emerald-500");
    expect(stageSource).not.toContain("bg-emerald-600");
  });

  it("caps trade preview rows", () => {
    expect(stageSource).toContain("resolveDecisionTradePreview");
    expect(stageSource).toContain("Open Monitor");
  });
});

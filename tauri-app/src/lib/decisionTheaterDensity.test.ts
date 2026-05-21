import { readFileSync } from "node:fs";
import { dirname, join } from "node:path";
import { fileURLToPath } from "node:url";
import { describe, expect, it } from "vitest";

const stageSource = readFileSync(
  join(dirname(fileURLToPath(import.meta.url)), "../components/decision/DecisionTheaterStage.tsx"),
  "utf8",
);
const theaterSource = readFileSync(
  join(dirname(fileURLToPath(import.meta.url)), "../components/DecisionTheater.tsx"),
  "utf8",
);
const cockpitCss = readFileSync(
  join(dirname(fileURLToPath(import.meta.url)), "../styles/cockpit.css"),
  "utf8",
);

describe("decision theater density contracts", () => {
  it("recent trades default collapsed in details", () => {
    expect(stageSource).toContain('className="decision-theater-stage__recent');
    expect(stageSource).toContain("<details");
    expect(stageSource).toContain("<summary");
  });

  it("active signal uses compact chip row", () => {
    expect(stageSource).toContain("CF {Math.round(signal.confluence * 100)}%");
    expect(stageSource).toContain("line-clamp-1");
  });

  it("verdict change triggers stage wash pulse class", () => {
    expect(stageSource).toContain("decision-theater-stage--verdict-flash");
    expect(cockpitCss).toContain(".decision-theater-shell:has(.decision-theater-stage--verdict-flash)::before");
  });

  it("reasoning spine compacts when proposal is active", () => {
    expect(theaterSource).toContain("compact={brief.verdict !== \"hold\" && brief.proposalHash !== null}");
  });
});

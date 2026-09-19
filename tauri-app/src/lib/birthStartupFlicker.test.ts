import { readFileSync } from "node:fs";
import { dirname, join } from "node:path";
import { fileURLToPath } from "node:url";

import { describe, expect, it } from "vitest";

const root = join(dirname(fileURLToPath(import.meta.url)), "..");

function read(rel: string): string {
  return readFileSync(join(root, rel), "utf8");
}

describe("startup screen flicker invariants", () => {
  it("BirthPhaseScreen paints from a single operator surface", () => {
    const screen = read("components/birth/BirthPhaseScreen.tsx");
    expect(screen).toContain("resolveBirthPaintSurface");
    expect(screen).not.toContain("missionMode || recoveryOverlayActive");
    expect(screen).not.toMatch(/Fail-closed: never orphan empty hero/);
  });

  it("freeze leftovers cannot look like a live engine", () => {
    const predicates = read("lib/birth/birthStatusPredicates.ts");
    expect(predicates).toContain("isUnresolvedTerminalFreeze");
    expect(predicates).toMatch(
      /export function isBirthEngineActive[\s\S]*isUnresolvedTerminalFreeze/,
    );
    expect(predicates).toMatch(
      /export function isBirthStageStalled[\s\S]*isUnresolvedTerminalFreeze/,
    );
  });

  it("applyStatus pins stall before runPinned training leftover", () => {
    const apply = read("store/birthStoreApplyStatus.ts");
    expect(apply).toContain("freezeUnresolved && !genesisPinned");
    expect(apply).toContain('uiPhase = "stage_stalled"');
  });

  it("Systems Go cover does not drop on a backend blip", () => {
    const gate = read("components/onboarding/OnboardingGate.tsx");
    expect(gate).toContain("shouldHoldStartupCover(ntStartupResolved)");
    expect(gate).not.toMatch(/backendReachable \|\| payload == null/);
  });

  it("ColdStart does not restore deck size on StrictMode unmount", () => {
    const cold = read("components/startup/ColdStartReadiness.tsx");
    expect(cold).toContain("retainStartupCoverWindow");
    expect(cold).toContain("releaseStartupCoverWindow");
    expect(cold).toContain("handleRetry");
    expect(cold).not.toMatch(/onRetry=\{\(\) => \{/);
  });

  it("VisibilityCanvas keeps the WebGL tree mounted when off-screen", () => {
    const canvas = read("components/cockpit/VisibilityCanvas.tsx");
    expect(canvas).toContain('frameloop={isVisible ? "always" : "never"}');
    expect(canvas).not.toContain("{isVisible ? (");
    expect(canvas).not.toContain('key={`${visualQuality}-visible`}');
  });

  it("organism envelope is not a 60fps React setState", () => {
    const ctx = read("context/OrganismEnvelopeContext.tsx");
    expect(ctx).not.toContain("setEnvelope");
    expect(ctx).not.toContain("subscribeOrganismClock");
    expect(ctx).toContain("Do not push rAF snapshots into React state");
  });

  it("autonomous recovery cannot tight-loop under freeze", () => {
    const actions = read("hooks/useBirthPhaseActions.ts");
    expect(actions).toContain("isUnresolvedTerminalFreeze(status)");
    expect(actions).toContain("10_000");
    const store = read("store/birthStore.ts");
    expect(store).toMatch(
      /executeRecommendedRecovery:[\s\S]*isUnresolvedTerminalFreeze/,
    );
  });

  it("stall overlay is a one-screen operator fork, not a stacked mission HUD", () => {
    const overlay = read("components/birth/BirthPhaseRecoveryOverlays.tsx");
    expect(overlay).toContain('variant="compact"');
    expect(overlay).toContain("freezeOperatorFork");
    expect(overlay).toContain("Champion freeze — Accept or Wipe");
    expect(overlay).toContain("autonomousMode && !freezeOperatorFork");
    const shell = read("components/birth/BirthFailureOverlayShell.tsx");
    expect(shell).toContain("items-start");
    expect(shell).toContain("birth-failure-overlay__actions");
    expect(shell).not.toContain("items-center justify-center overflow-y-auto");
  });

  it("operator birth surfaces restore deck window size", () => {
    const screen = read("components/birth/BirthPhaseScreen.tsx");
    expect(screen).toContain("restoreDeckWindowSize");
  });
});

import { readFileSync } from "node:fs";
import { dirname, join } from "node:path";
import { fileURLToPath } from "node:url";

import { describe, expect, it } from "vitest";

import { HUB_WIPE_CARDS } from "@/components/maturity/phaseHubFormat";

const root = join(dirname(fileURLToPath(import.meta.url)));

function source(name: string): string {
  return readFileSync(join(root, name), "utf8");
}

describe("Phase Hub named wipes", () => {
  it("exposes three Genesis-style wipe kinds in order", () => {
    expect(HUB_WIPE_CARDS.map((c) => c.kind)).toEqual(["awakening", "birth", "full"]);
    expect(HUB_WIPE_CARDS.map((c) => c.label)).toEqual([
      "Wipe Awakening",
      "Wipe Birth",
      "Full wipe",
    ]);
    expect(HUB_WIPE_CARDS[2]?.tone).toBe("danger");
  });

  it("PhaseHubDeck uses Genesis wipe cards with keep/destroy hints, not window.confirm", () => {
    const deck = source("PhaseHubDeck.tsx");
    const advance = source("PhaseHubAdvanceSection.tsx");
    expect(deck).toContain("HUB_WIPE_CARDS");
    expect(deck).toContain("RecoveryActionCard");
    expect(deck).not.toContain("BirthStagePassChecklistCard");
    expect(deck).toContain("onWipe(card.kind)");
    expect(deck).toContain("card.hint");
    expect(deck).toContain("card.tip");
    expect(advance).toContain("RecoveryActionCard");
    expect(advance).toContain("opt.tip");
    expect(advance).toContain("opt.hint");
    expect(deck).not.toContain("Refresh hub");
    expect(deck).not.toContain("Wipe all");
    expect(deck).not.toContain("RotateCcw");
    expect(deck).not.toContain("window.confirm");
    expect(deck).not.toContain("from \"@/components/ui/button\"");
  });

  it("PhaseHubScreen uses three-step BirthPortaledDialog typed confirm", () => {
    const screen = source("PhaseHubScreen.tsx");
    const confirm = source("PhaseHubWipeConfirm.tsx");
    const copy = source("phaseWipeCopy.ts");
    expect(screen).toContain("PhaseHubWipeConfirm");
    expect(screen).not.toContain("window.confirm");
    expect(confirm).toContain("BirthPortaledDialog");
    expect(confirm).toContain("I understand — continue");
    expect(confirm).toContain("I accept the loss — continue");
    expect(confirm).toContain("wipePhraseMatches");
    expect(confirm).toContain("WIPE_CONFIRM_PHRASES");
    expect(confirm).toContain('type="text"');
    expect(confirm).toContain("birth-portaled-dialog__phrase");
    expect(confirm).toContain("placeholder={requiredPhrase}");
    expect(readFileSync(join(root, "../../styles/birthPhase.css"), "utf8")).toContain(
      ".birth-portaled-dialog__phrase",
    );
    expect(copy).toContain("Smart Setup stays");
    expect(copy).toContain("Birth plant");
    expect(copy).toContain("WIPE AWAKENING");
  });

  it("Final confirmation commits on pointerup so WebView2 taps wipe", () => {
    const confirm = source("PhaseHubWipeConfirm.tsx");
    expect(confirm).toContain("onPointerUp");
    expect(confirm).toContain("fireConfirm");
    expect(confirm).toContain("confirmOnce");
    expect(source("phaseWipeCopy.ts")).toContain("Wipe Awakening");
  });

  it("offers Activate Birth when the next phase is Birth", () => {
    const deck = source("PhaseHubDeck.tsx");
    const screen = source("PhaseHubScreen.tsx");
    expect(deck).toContain('birthNext ? "ACTIVATE BIRTH"');
    expect(deck).not.toContain("Start Birth from the Birth screen");
    expect(screen).toContain("openBirthGenesis(setPhase)");
    expect(screen).not.toContain("Start Birth from the Birth screen");
    expect(screen).toContain('kind === "birth" || kind === "full"');
  });

  it("cinematic and hub wipe do not disable confirm with start/stop busy", () => {
    const awakening = source("AwakeningPhaseScreen.tsx");
    const hub = source("PhaseHubScreen.tsx");
    expect(awakening).toContain("wiping={wiping}");
    expect(awakening).not.toContain("wiping={busy}");
    expect(hub).toContain("wiping={wiping}");
    expect(hub).not.toContain("if (!wipeKind || busy) return");
    expect(hub).toContain("postWipeMaturityPhase(kind, phrase)");
  });
});

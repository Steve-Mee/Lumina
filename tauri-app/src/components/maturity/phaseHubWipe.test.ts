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

  it("PhaseHubDeck uses recovery glass cards, not Refresh or window.confirm", () => {
    const deck = source("PhaseHubDeck.tsx");
    expect(deck).toContain("HUB_WIPE_CARDS");
    expect(deck).toContain("genesis-recovery-action-grid--3");
    expect(deck).toContain("RecoveryActionCard");
    expect(deck).toContain("onWipe(card.kind)");
    expect(deck).not.toContain("Refresh hub");
    expect(deck).not.toContain("Wipe all");
    expect(deck).not.toContain("RotateCcw");
    expect(deck).not.toContain("window.confirm");
    expect(deck).not.toContain("from \"@/components/ui/button\"");
  });

  it("PhaseHubScreen uses two-step BirthPortaledDialog confirm", () => {
    const screen = source("PhaseHubScreen.tsx");
    const confirm = source("PhaseHubWipeConfirm.tsx");
    expect(screen).toContain("PhaseHubWipeConfirm");
    expect(screen).not.toContain("window.confirm");
    expect(confirm).toContain("BirthPortaledDialog");
    expect(confirm).toContain("I understand — continue");
    expect(confirm).toContain("Smart Setup stays");
    expect(confirm).toContain("Birth plant");
  });

  it("Final confirmation commits on pointerup so WebView2 taps wipe", () => {
    const confirm = source("PhaseHubWipeConfirm.tsx");
    expect(confirm).toContain("onPointerUp");
    expect(confirm).toContain("fireConfirm");
    expect(confirm).toContain("confirmOnce");
    expect(confirm).toContain("Wipe Awakening");
  });

  it("cinematic and hub wipe do not disable confirm with start/stop busy", () => {
    const awakening = source("AwakeningPhaseScreen.tsx");
    const hub = source("PhaseHubScreen.tsx");
    expect(awakening).toContain("wiping={wiping}");
    expect(awakening).not.toContain("wiping={busy}");
    expect(hub).toContain("wiping={wiping}");
    expect(hub).not.toContain("if (!wipeKind || busy) return");
    expect(hub).toContain("postWipeMaturityPhase(kind)");
  });
});

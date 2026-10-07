import type { HubWipeKind } from "@/components/maturity/phaseHubFormat";

export const WIPE_CONFIRM_PHRASES: Record<HubWipeKind, string> = {
  playground: "WIPE PLAYGROUND",
  awakening: "WIPE AWAKENING",
  apprenticeship: "WIPE APPRENTICESHIP",
  proving_ground: "WIPE PROVING GROUND",
  birth: "WIPE BIRTH",
  full: "WIPE FULL",
};

export const WIPE_CONFIRM_COPY: Record<
  HubWipeKind,
  {
    title1: string;
    keep: string;
    remove: string[];
    title2: string;
    body2: string;
    title3: string;
    body3: string;
    confirmLabel: string;
  }
> = {
  playground: {
    title1: "Wipe Playground data?",
    keep: "Genesis, Birth, Awakening, and frozen π* stay.",
    remove: [
      "Playground SIM tape and first-fill ledger",
      "Playground progress heartbeat",
      "Later ladder progress (Apprenticeship and after)",
    ],
    title2: "This cannot be undone",
    body2: "Playground crawl data will be destroyed. Awakening is not re-run. You stay on Phase Hub and can Start Playground again.",
    title3: "Type WIPE PLAYGROUND",
    body3: "Last gate. Type the phrase exactly. There is no undo.",
    confirmLabel: "Wipe Playground",
  },
  awakening: {
    title1: "Wipe Awakening data?",
    keep: "Birth plant, frozen π*, tick cache, cycle journal, and Smart Setup stay.",
    remove: [
      "First Watch seal, holdout ledgers, and progress heartbeat",
      "Generated Awakening zips (live / student / incumbent)",
      "Later ladder progress (Playground and after)",
    ],
    title2: "This cannot be undone",
    body2: "First Watch data will be destroyed. Birth is not re-run. You can Start Awakening again from the frozen plant.",
    title3: "Type WIPE AWAKENING",
    body3: "Last gate. Type the phrase exactly. Birth freeze stays. There is no undo.",
    confirmLabel: "Wipe Awakening",
  },
  apprenticeship: {
    title1: "Wipe Apprenticeship data?",
    keep: "Genesis, Birth, Awakening, Playground, and frozen π* stay.",
    remove: [
      "Apprenticeship tape and session-day ledger",
      "Apprenticeship progress heartbeat",
      "Later ladder progress (Proving Ground and REAL)",
    ],
    title2: "This cannot be undone",
    body2: "Apprenticeship walking data will be destroyed. Playground crawl is not re-run. You can Start Apprenticeship again.",
    title3: "Type WIPE APPRENTICESHIP",
    body3: "Last gate. Type the phrase exactly. There is no undo.",
    confirmLabel: "Wipe Apprenticeship",
  },
  proving_ground: {
    title1: "Wipe Proving Ground data?",
    keep: "Genesis through Apprenticeship, Birth freeze, and frozen π* stay.",
    remove: [
      "Proving Ground tape and exam heartbeat",
      "This-run shadow / PromotionGate evidence",
      "Later ladder progress (REAL)",
    ],
    title2: "This cannot be undone",
    body2: "The driving-test tape will be destroyed. Apprenticeship walk is not re-run. You can Start Proving Ground again.",
    title3: "Type WIPE PROVING GROUND",
    body3: "Last gate. Type the phrase exactly. There is no undo.",
    confirmLabel: "Wipe Proving Ground",
  },
  birth: {
    title1: "Wipe Birth and Awakening?",
    keep: "Tick cache, split cache, enrichment, and Smart Setup stay.",
    remove: [
      "Birth curriculum, checkpoints, and PPO plant",
      "Awakening shot and later ladder progress",
    ],
    title2: "This cannot be undone",
    body2: "Birth reset (history kept). You return to a blank Genesis deck and Activate Birth again.",
    title3: "Type WIPE BIRTH",
    body3: "Last gate. Type the phrase exactly. Tick cache stays. There is no undo.",
    confirmLabel: "Wipe Birth",
  },
  full: {
    title1: "Permanently wipe Birth and history?",
    keep: "Smart Setup stays — credentials, NT paths, and config.yaml are not wiped.",
    remove: [
      "Birth plant, checkpoints, and PPO policies",
      "Awakening shot and later ladder progress",
      "Tick cache, split cache, and enrichment cache",
    ],
    title2: "This cannot be undone",
    body2: "Full wipe. You restart from a blank Genesis deck. History must be loaded again. Setup is not wiped.",
    title3: "Type WIPE FULL",
    body3: "Last gate. Type the phrase exactly. Tick cache is destroyed. There is no undo.",
    confirmLabel: "Wipe everything permanently",
  },
};

export function wipePhraseMatches(kind: HubWipeKind, typed: string): boolean {
  return typed.trim() === WIPE_CONFIRM_PHRASES[kind];
}

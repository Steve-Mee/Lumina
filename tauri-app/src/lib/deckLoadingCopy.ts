export const DECK_LOADING_COPY = {
  neuralCore: "Awakening neural core…",
  evolutionArena: "Initializing evolution arena…",
  forceGraph: "Mapping mutation lattice…",
  generic3d: "Loading neural visualization…",
  riskCitadel: "Connecting risk citadel…",
  ppoSync: "Syncing evolution tree…",
  settingsSync: "Loading deck settings…",
} as const;

export type DeckLoadingCopyKey = keyof typeof DECK_LOADING_COPY;

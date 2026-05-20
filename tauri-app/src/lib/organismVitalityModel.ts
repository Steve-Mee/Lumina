import type { ConnectionStatus, TradingMode } from "@/store/coreStore";

import { deckTransportLabel } from "@/lib/deckStatusModel";

export type VitalityTier = "dormant" | "connected" | "session" | "engine" | "degraded";

export interface VitalityInput {
  connectionStatus: ConnectionStatus;
  fallbackMode: boolean;
  sessionActive: boolean;
  activityStale: boolean;
  engineAlive: boolean;
  mode: TradingMode;
  phaseLabel?: string;
}

export interface VitalityState {
  tier: VitalityTier;
  primaryLabel: string;
  engineGlyph: string | null;
  transportLabel: string;
  showEngineCompanion: boolean;
}

function engineGlyphForMode(mode: TradingMode): string {
  return mode === "REAL" ? "Guarded" : "Live";
}

function formatSessionPrimary(phaseLabel: string | undefined): string {
  const phase = phaseLabel && phaseLabel !== "idle" ? phaseLabel : null;
  return phase ? `Live · ${phase}` : "Lumina live";
}

export function resolveVitality(input: VitalityInput): VitalityState {
  const transportLabel = deckTransportLabel(input.connectionStatus, input.fallbackMode);
  const phaseLabel = input.phaseLabel ?? "idle";
  const glyph = engineGlyphForMode(input.mode);

  if (input.fallbackMode || input.connectionStatus === "disconnected") {
    return {
      tier: "dormant",
      primaryLabel: "Standby",
      engineGlyph: input.engineAlive ? glyph : null,
      transportLabel,
      showEngineCompanion: input.engineAlive,
    };
  }

  if (input.connectionStatus === "connecting" || input.connectionStatus === "reconnecting") {
    return {
      tier: "connected",
      primaryLabel: input.connectionStatus === "connecting" ? "Connecting" : "Reconnecting",
      engineGlyph: input.engineAlive ? glyph : null,
      transportLabel,
      showEngineCompanion: input.engineAlive,
    };
  }

  if (input.activityStale) {
    return {
      tier: "degraded",
      primaryLabel: "Degraded · stale",
      engineGlyph: input.engineAlive ? glyph : null,
      transportLabel,
      showEngineCompanion: input.engineAlive,
    };
  }

  const sessionLive = input.sessionActive && input.connectionStatus === "connected";

  if (sessionLive) {
    return {
      tier: input.engineAlive ? "engine" : "session",
      primaryLabel: formatSessionPrimary(phaseLabel),
      engineGlyph: input.engineAlive ? glyph : null,
      transportLabel,
      showEngineCompanion: input.engineAlive,
    };
  }

  if (input.connectionStatus === "connected") {
    return {
      tier: input.engineAlive ? "engine" : "connected",
      primaryLabel: input.engineAlive ? formatSessionPrimary(phaseLabel) : "Connected",
      engineGlyph: input.engineAlive ? glyph : null,
      transportLabel,
      showEngineCompanion: input.engineAlive,
    };
  }

  return {
    tier: "dormant",
    primaryLabel: "Standby",
    engineGlyph: input.engineAlive ? glyph : null,
    transportLabel,
    showEngineCompanion: input.engineAlive,
  };
}

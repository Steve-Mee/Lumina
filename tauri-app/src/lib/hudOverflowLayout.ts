import type { RuntimeStatus } from "@/lib/runtimeClient";
import type { TradingMode } from "@/store/coreStore";

export const HUD_OVERFLOW_MAX_ITEMS = 5;
/** Settings is always overflow item 0 in CommandHud — not counted toward HUD_OVERFLOW_MAX_ITEMS ops cap. */

export type HudOverflowItemId =
  | "trainingMonitor"
  | "botConfig"
  | "saveAndStart"
  | "stopEngine"
  | "safety"
  | "launchNinja";

export interface HudOverflowItem {
  id: HudOverflowItemId;
  label: string;
}

export interface HudOverflowContext {
  mode: TradingMode;
  runtime: RuntimeStatus | null;
  apiKeyConfigured: boolean;
}

export function resolveOverflowItems(ctx: HudOverflowContext): HudOverflowItem[] {
  const engineAlive = Boolean(ctx.runtime?.alive);
  const items: HudOverflowItem[] = [];

  if (engineAlive) {
    items.push({ id: "trainingMonitor", label: "Training monitor" });
  }

  items.push({ id: "botConfig", label: "Bot configuration" });

  if (!engineAlive && ctx.apiKeyConfigured) {
    items.push({ id: "saveAndStart", label: "Save & Start" });
  }

  if (engineAlive) {
    items.push({ id: "stopEngine", label: "Stop Engine" });
  }

  items.push({ id: "safety", label: "Safety" });
  items.push({ id: "launchNinja", label: "Launch NinjaTrader" });

  return items.slice(0, HUD_OVERFLOW_MAX_ITEMS);
}

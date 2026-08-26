/**
 * Option A: hug the Systems Go card with the native window, then restore deck size.
 * One window only — no second webview.
 */
import { isTauri } from "@tauri-apps/api/core";

/** Compact window around Systems Go card (~26.5rem + chrome). */
export const SYSTEMS_GO_WINDOW = {
  width: 480,
  height: 760,
  minWidth: 420,
  minHeight: 560,
} as const;

/** Matches tauri.conf.json main window. */
export const DECK_WINDOW = {
  width: 1600,
  height: 1000,
  minWidth: 1280,
  minHeight: 720,
} as const;

let mode: "systems-go" | "deck" | "unknown" = "unknown";

async function getWindowApi(): Promise<{
  setSize: (s: { width: number; height: number }) => Promise<void>;
  setMinSize: (s: { width: number; height: number } | null) => Promise<void>;
  center: () => Promise<void>;
} | null> {
  if (!isTauri()) return null;
  try {
    const { getCurrentWindow, LogicalSize } = await import("@tauri-apps/api/window");
    const win = getCurrentWindow();
    return {
      setSize: async (s) => {
        await win.setSize(new LogicalSize(s.width, s.height));
      },
      setMinSize: async (s) => {
        if (s == null) {
          await win.setMinSize(undefined);
          return;
        }
        await win.setMinSize(new LogicalSize(s.width, s.height));
      },
      center: async () => {
        await win.center();
      },
    };
  } catch {
    return null;
  }
}

/** Shrink + center main window to the Systems Go card. */
export async function applySystemsGoWindowSize(): Promise<void> {
  if (mode === "systems-go") return;
  const win = await getWindowApi();
  if (!win) return;
  try {
    // Lower min first so compact size is allowed (conf min is 1280×720).
    await win.setMinSize({
      width: SYSTEMS_GO_WINDOW.minWidth,
      height: SYSTEMS_GO_WINDOW.minHeight,
    });
    await win.setSize({
      width: SYSTEMS_GO_WINDOW.width,
      height: SYSTEMS_GO_WINDOW.height,
    });
    await win.center();
    mode = "systems-go";
  } catch {
    /* non-fatal — UI still works in large window */
  }
}

/** Restore full Command Deck window after Systems Go. */
export async function restoreDeckWindowSize(): Promise<void> {
  if (mode === "deck") return;
  const win = await getWindowApi();
  if (!win) return;
  try {
    await win.setSize({
      width: DECK_WINDOW.width,
      height: DECK_WINDOW.height,
    });
    await win.setMinSize({
      width: DECK_WINDOW.minWidth,
      height: DECK_WINDOW.minHeight,
    });
    await win.center();
    mode = "deck";
  } catch {
    /* non-fatal */
  }
}

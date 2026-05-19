import { isTauri } from "@tauri-apps/api/core";
import { register, unregister } from "@tauri-apps/plugin-global-shortcut";
import { useEffect } from "react";

import {
  dispatchApproveLastMutation,
  dispatchEvolve,
  dispatchPause,
} from "@/lib/commandActions";

const SHORTCUTS = [
  "CommandOrControl+E",
  "CommandOrControl+P",
  "CommandOrControl+A",
] as const;

function isEditableFocused(): boolean {
  const active = document.activeElement;
  if (!active || !(active instanceof HTMLElement)) {
    return false;
  }
  const tag = active.tagName;
  return (
    tag === "INPUT" ||
    tag === "TEXTAREA" ||
    active.isContentEditable
  );
}

function dispatchForShortcut(shortcut: string): void {
  switch (shortcut) {
    case "CommandOrControl+E":
      dispatchEvolve();
      break;
    case "CommandOrControl+P":
      dispatchPause();
      break;
    case "CommandOrControl+A":
      dispatchApproveLastMutation();
      break;
  }
}

function handleBrowserKeyDown(event: KeyboardEvent): void {
  if (isEditableFocused()) {
    return;
  }

  const mod = event.metaKey || event.ctrlKey;
  if (!mod) {
    return;
  }

  const key = event.key.toLowerCase();
  if (key === "e") {
    event.preventDefault();
    dispatchEvolve();
    return;
  }
  if (key === "p") {
    event.preventDefault();
    dispatchPause();
    return;
  }
  if (key === "a") {
    event.preventDefault();
    dispatchApproveLastMutation();
  }
}

export function useTauriGlobalShortcuts(): void {
  useEffect(() => {
    if (isTauri()) {
      let cancelled = false;

      void register([...SHORTCUTS], (event) => {
        if (cancelled || event.state !== "Pressed" || isEditableFocused()) {
          return;
        }
        dispatchForShortcut(event.shortcut);
      }).catch((error: unknown) => {
        console.error("Failed to register global shortcuts", error);
      });

      return () => {
        cancelled = true;
        void unregister([...SHORTCUTS]).catch((error: unknown) => {
          console.error("Failed to unregister global shortcuts", error);
        });
      };
    }

    window.addEventListener("keydown", handleBrowserKeyDown);
    return () => window.removeEventListener("keydown", handleBrowserKeyDown);
  }, []);
}

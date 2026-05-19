import { toast } from "sonner";

import { useSettingsDialogStore } from "@/store/settingsDialogStore";

export function handleRuntimeError(err: unknown, fallback = "Operation failed"): void {
  const message = err instanceof Error ? err.message : fallback;
  const needsApiKey =
    message.includes("API key") ||
    message.includes("401") ||
    message.toLowerCase().includes("unauthorized");

  if (needsApiKey) {
    toast.error("Admin API key required for engine and runtime actions", {
      action: {
        label: "Open Settings",
        onClick: () => useSettingsDialogStore.getState().openSettings("apiKey"),
      },
    });
    return;
  }

  toast.error(message);
}

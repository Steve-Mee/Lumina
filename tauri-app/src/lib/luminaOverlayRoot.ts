/** Dedicated overlay mount — survives birth deck remounts; preferred over raw document.body in Tauri. */
export function getLuminaOverlayRoot(): HTMLElement {
  if (typeof document === "undefined") {
    throw new Error("document is not available");
  }
  const dedicated = document.getElementById("lumina-overlay-root");
  if (dedicated instanceof HTMLElement) {
    return dedicated;
  }
  return document.body;
}

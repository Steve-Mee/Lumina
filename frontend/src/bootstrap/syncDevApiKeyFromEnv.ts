import { DEFAULT_LUMINA_API_KEY_LS_KEY } from "../hooks/useLuminaMetrics";

/**
 * Alleen in Vite `import.meta.env.DEV`: als `VITE_LUMINA_API_KEY` gezet is en localStorage
 * nog geen key heeft, schrijf die één keer weg. Handig voor lokaal ontwikkelen zonder DevTools.
 * Let op: elke `VITE_*` variabele komt in de client bundle — nooit productie-secrets zo exposen.
 */
export function syncDevApiKeyFromEnv(): void {
  if (!import.meta.env.DEV) {
    return;
  }
  const raw = import.meta.env.VITE_LUMINA_API_KEY;
  if (typeof raw !== "string" || !raw.trim()) {
    return;
  }
  try {
    if (!localStorage.getItem(DEFAULT_LUMINA_API_KEY_LS_KEY)) {
      localStorage.setItem(DEFAULT_LUMINA_API_KEY_LS_KEY, raw.trim());
    }
  } catch {
    // storage denied / private mode
  }
}

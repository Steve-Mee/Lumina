/// <reference types="vite/client" />

interface ImportMetaEnv {
  /** Toon operatornaam in de top-bar (optional) */
  readonly VITE_DASHBOARD_OPERATOR?: string;
  /**
   * Alleen bedoeld voor lokale dev: éénmalig naar `localStorage` `lumina_api_key` (zie bootstrap).
   * Nooit echte productie-keys als `VITE_*` committen — ze belanden in de bundel.
   */
  readonly VITE_LUMINA_API_KEY?: string;
  /** Override voor Vite dev-proxy target (bv. Docker: `http://host.docker.internal:8000`). */
  readonly VITE_API_PROXY_TARGET?: string;
}

interface ImportMeta {
  readonly env: ImportMetaEnv;
}

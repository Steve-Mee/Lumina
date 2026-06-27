import { Settings } from "lucide-react";
import { useEffect, useState } from "react";
import { motion } from "framer-motion";
import { toast } from "sonner";

import { PanelLoader } from "@/components/cockpit/PanelLoader";
import { DECK_LOADING_COPY } from "@/lib/deckLoadingCopy";
import { luminaSurfaceMutedClass } from "@/lib/glassGlowTaxonomy";
import { BotConfigForm } from "@/components/config/BotConfigForm";
import { Button } from "@/components/ui/button";
import { useAdaptiveIntelligenceContext } from "@/context/AdaptiveIntelligenceContext";
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
  DialogTrigger,
} from "@/components/ui/dialog";
import { resetCommandDeckTour } from "@/components/cockpit/CommandDeckTour";
import {
  persistMonitoringApiKey,
  resolveMonitoringApiKey,
} from "@/lib/monitoringClient";
import { fetchDeckApiKey } from "@/lib/setupClient";
import {
  VISUAL_QUALITY_LABELS,
  VISUAL_QUALITY_PRESETS,
  type VisualQuality,
} from "@/lib/visualQualityPresets";
import { useModeMotion } from "@/hooks/useModeMotion";
import { usePrefersReducedMotion } from "@/hooks/usePrefersReducedMotion";
import {  transitionOrNone } from "@/lib/motionPresets";
import { realDialogBodyClass, realDialogTitleClass } from "@/lib/modePresentation";
import { cn } from "@/lib/utils";
import { selectCurrentMode, useCoreStore } from "@/store/coreStore";
import { useBotConfigStore } from "@/store/botConfigStore";
import {
  usePanelRefreshStore,
  type PanelRefreshSeconds,
} from "@/store/panelRefreshStore";
import {
  useSettingsDialogStore,
  type SettingsTab,
} from "@/store/settingsDialogStore";
import {
  readHudLayoutPrefs,
} from "@/lib/hudSignalLayout";
import { useHudLayoutPrefsStore } from "@/store/hudLayoutPrefsStore";
import {
  selectVisualQuality,
  useVisualSettingsStore,
} from "@/store/visualSettingsStore";

const QUALITY_ORDER: VisualQuality[] = ["low", "balanced", "high"];

const TAB_LABELS: Record<SettingsTab, string> = {
  apiKey: "API Key",
  bot: "Bot Config",
  visual: "Visual",
  refresh: "Refresh",
};

const REFRESH_OPTIONS: PanelRefreshSeconds[] = [5, 10, 15, 30, 60];

function SettingsTabBar({
  tab,
  onSelect,
  mode,
}: {
  tab: SettingsTab;
  onSelect: (next: SettingsTab) => void;
  mode: ReturnType<typeof selectCurrentMode>;
}) {
  const reducedMotion = usePrefersReducedMotion();
  const modeMotion = useModeMotion();

  return (
    <div className="flex flex-wrap gap-1 border-b border-white/10 px-6 pb-3">
      {(Object.keys(TAB_LABELS) as SettingsTab[]).map((key) => {
        const active = tab === key;
        return (
          <button
            key={key}
            type="button"
            onClick={() => onSelect(key)}
            className={cn(
              "relative rounded-md px-3 py-1.5 font-mono text-[10px] tracking-wide uppercase transition-colors",
              active
                ? mode === "REAL"
                  ? "text-slate-200"
                  : "text-cyan-200"
                : "text-muted-foreground hover:bg-white/5 hover:text-foreground",
            )}
          >
            {active ? (
              <motion.span
                layoutId="settings-tab"
                className={cn(
                  "absolute inset-0 rounded-md",
                  mode === "REAL" ? "bg-slate-700/25" : "bg-cyan-500/15",
                )}
                transition={transitionOrNone(reducedMotion, modeMotion)}
              />
            ) : null}
            <span className="relative z-[1]">{TAB_LABELS[key]}</span>
          </button>
        );
      })}
    </div>
  );
}

export function SettingsDialog({ hideTrigger = false }: { hideTrigger?: boolean }) {
  const open = useSettingsDialogStore((s) => s.open);
  const tab = useSettingsDialogStore((s) => s.tab);
  const openSettings = useSettingsDialogStore((s) => s.openSettings);
  const closeSettings = useSettingsDialogStore((s) => s.closeSettings);
  const setTab = useSettingsDialogStore((s) => s.setTab);

  const [apiKeyDraft, setApiKeyDraft] = useState(() => resolveMonitoringApiKey() ?? "");
  const [syncingKey, setSyncingKey] = useState(false);
  const [hudPrefs, setHudPrefs] = useState(readHudLayoutPrefs);
  const setHudPrefsStore = useHudLayoutPrefsStore((s) => s.setPrefs);

  const operatorMode = useCoreStore(selectCurrentMode);
  const draft = useBotConfigStore((s) => s.draft);
  const loading = useBotConfigStore((s) => s.loading);
  const saving = useBotConfigStore((s) => s.saving);
  const error = useBotConfigStore((s) => s.error);
  const loadFromBackend = useBotConfigStore((s) => s.loadFromBackend);
  const updateDraft = useBotConfigStore((s) => s.updateDraft);
  const save = useBotConfigStore((s) => s.save);
  const isDirty = useBotConfigStore((s) => s.isDirty);

  const visualQuality = useVisualSettingsStore(selectVisualQuality);
  const setVisualQuality = useVisualSettingsStore((s) => s.setVisualQuality);
  const panelRefreshSeconds = usePanelRefreshStore((s) => s.seconds);
  const setPanelRefreshSeconds = usePanelRefreshStore((s) => s.setSeconds);
  const { refresh: refreshMonitoring } = useAdaptiveIntelligenceContext();

  useEffect(() => {
    if (open) {
      setApiKeyDraft(resolveMonitoringApiKey() ?? "");
      void loadFromBackend();
    }
  }, [open, loadFromBackend]);

  const handleOpenChange = (next: boolean) => {
    if (!next) {
      closeSettings();
    }
  };

  const saveApiKey = () => {
    const trimmed = apiKeyDraft.trim();
    if (!trimmed) {
      toast.error("Enter your admin API key");
      return;
    }
    persistMonitoringApiKey(trimmed);
    void refreshMonitoring();
    toast.success("API key saved — monitoring panels updated");
  };

  const syncFromBackend = async () => {
    setSyncingKey(true);
    try {
      const response = await fetchDeckApiKey();
      const key = response.api_key?.trim();
      if (response.configured && key) {
        setApiKeyDraft(key);
        persistMonitoringApiKey(key);
        void refreshMonitoring();
        toast.success("Deck connected to backend admin key");
      } else {
        toast.error("No admin API key found in backend .env");
      }
    } catch (err) {
      toast.error(err instanceof Error ? err.message : "Sync failed");
    } finally {
      setSyncingKey(false);
    }
  };

  const saveBotConfig = async () => {
    const ok = await save();
    if (ok) {
      toast.success("Bot configuration saved to config.yaml");
      toast.info("Restart the engine for changes to take full effect");
    } else if (error) {
      toast.error(error);
    }
  };

  return (
    <Dialog open={open} onOpenChange={handleOpenChange}>
      {hideTrigger ? null : (
      <DialogTrigger asChild>
        <Button
          type="button"
          size="sm"
          variant="command-ghost"
          className="h-9 w-9 p-0"
          aria-label="Settings"
          title="Settings"
          data-tour="settings-button"
          onClick={() => openSettings("apiKey")}
        >
          <Settings className="size-4" />
        </Button>
      </DialogTrigger>
      )}
      <DialogContent className="max-h-[90vh] max-w-xl overflow-hidden p-0">
        <DialogHeader
          className={cn(
            "border-b border-white/10 px-6 py-4",
            operatorMode === "REAL" && "bg-slate-900/40",
          )}
        >
          <DialogTitle
            className={operatorMode === "REAL" ? realDialogTitleClass() : "text-cyan-100"}
          >
            Settings
          </DialogTitle>
          <DialogDescription>
            API access, bot configuration, and visual quality
          </DialogDescription>
        </DialogHeader>

        <SettingsTabBar tab={tab} onSelect={setTab} mode={operatorMode} />

        <div className="max-h-[min(58vh,520px)] overflow-y-auto px-6 py-4">
          {tab === "bot" && operatorMode === "REAL" ? (
            <p className={cn("mb-3 rounded-md border border-slate-500/25 bg-slate-900/40 px-3 py-2 font-mono text-[10px]", realDialogBodyClass())}>
              REAL mode — bot configuration changes may affect live capital deployment.
            </p>
          ) : null}
          {tab === "apiKey" ? (
            <div className="space-y-3">
              <p className="text-xs text-muted-foreground">
                Required for engine start/stop, safety actions, monitoring, and evolution
                approvals. Use the same admin key from your backend{" "}
                <span className="font-mono">.env</span>.
              </p>
              <input
                className="onboarding-field w-full font-mono"
                type="password"
                value={apiKeyDraft}
                onChange={(e) => setApiKeyDraft(e.target.value)}
                placeholder="sk_… or LUMINA_ADMIN_API_KEY value"
              />
              <div className="flex flex-wrap gap-2">
                <Button type="button" size="sm" variant="command-primary" onClick={saveApiKey}>
                  Save API key
                </Button>
                <Button
                  type="button"
                  size="sm"
                  variant="command-ghost"
                  disabled={syncingKey}
                  onClick={() => void syncFromBackend()}
                >
                  {syncingKey ? "Syncing…" : "Sync from backend"}
                </Button>
              </div>
            </div>
          ) : null}

          {tab === "bot" ? (
            loading ? (
              <PanelLoader label={DECK_LOADING_COPY.settingsSync} className="min-h-[160px]" />
            ) : (
              <>
                <p className="mb-3 text-xs text-muted-foreground">
                  Same configuration as <strong className="text-foreground">Bot Config</strong> in the
                  command bar — edits here and in the HUD dialog stay in sync.
                </p>
                {error ? <p className="mb-3 text-sm text-red-300/90">{error}</p> : null}
                <BotConfigForm
                  draft={draft}
                  onChange={updateDraft}
                  showModeCallout
                  operatorMode={operatorMode}
                />
              </>
            )
          ) : null}

          {tab === "refresh" ? (
            <div className="space-y-3">
              <p className="text-xs text-muted-foreground">
                Panel auto-refresh interval for Activity, Monitor, and diagnostics (Streamlit
                command-center parity).
              </p>
              <div className="flex flex-wrap gap-2">
                {REFRESH_OPTIONS.map((sec) => (
                  <button
                    key={sec}
                    type="button"
                    onClick={() => setPanelRefreshSeconds(sec)}
                    className={cn(
                      "rounded-md border px-3 py-1.5 font-mono text-xs",
                      panelRefreshSeconds === sec
                        ? operatorMode === "REAL"
                          ? "border-slate-500/40 bg-slate-700/25 text-slate-200"
                          : "border-cyan-400/40 bg-cyan-500/10 text-cyan-200"
                        : "border-white/10 text-muted-foreground",
                    )}
                  >
                    {sec}s
                  </button>
                ))}
              </div>
            </div>
          ) : null}

          {tab === "visual" ? (
            <div className="space-y-4">
            <div className="grid gap-2">
              {QUALITY_ORDER.map((quality) => {
                const preset = VISUAL_QUALITY_PRESETS[quality];
                const meta = VISUAL_QUALITY_LABELS[quality];
                const active = visualQuality === quality;
                return (
                  <button
                    key={quality}
                    type="button"
                    onClick={() => setVisualQuality(quality)}
                    className={cn(
                      "rounded-lg border px-3 py-2.5 text-left transition-colors",
                      active
                        ? operatorMode === "REAL"
                          ? "border-slate-500/40 bg-slate-700/25"
                          : "border-cyan-400/40 bg-cyan-500/10"
                        : luminaSurfaceMutedClass("border border-white/10 hover:border-white/20"),
                    )}
                  >
                    <p className="font-mono text-xs tracking-wide text-foreground">{meta.title}</p>
                    <p className="mt-0.5 text-[10px] text-muted-foreground">{meta.description}</p>
                    <p className="mt-1.5 font-mono text-[9px] text-cyan-200/70">
                      DPR {preset.dpr.join("–")} · particles ×{preset.particleScale}
                    </p>
                  </button>
                );
              })}
            </div>
            {operatorMode === "SIM" ? (
              <div className={luminaSurfaceMutedClass("rounded-lg border border-white/10 p-3")}>
                <p className="font-mono text-xs tracking-wide text-foreground">HUD hero signal</p>
                <p className="mt-1 text-[10px] text-muted-foreground">
                  Primary HUD slot — secondary contextual moves to Performance annex when session idle.
                </p>
                <Button
                  type="button"
                  size="sm"
                  variant="command-ghost"
                  className="mt-2"
                  onClick={() => {
                    const next = {
                      ...hudPrefs,
                      heroPrimary: (hudPrefs.heroPrimary === "fortress" ? "equity" : "fortress") as
                        | "equity"
                        | "fortress",
                    };
                    setHudPrefsStore(next);
                    setHudPrefs(next);
                  }}
                >
                  {hudPrefs.heroPrimary === "fortress" ? "Show equity as hero" : "Show fortress arc as hero"}
                </Button>
                <Button
                  type="button"
                  size="sm"
                  variant="command-ghost"
                  className="mt-2 ml-2"
                  onClick={() => {
                    const next = { ...hudPrefs, showPnlInSim: !hudPrefs.showPnlInSim };
                    setHudPrefsStore(next);
                    setHudPrefs(next);
                  }}
                >
                  {hudPrefs.showPnlInSim ? "Annex: regime hint" : "Annex: P&L hint"}
                </Button>
              </div>
            ) : null}
            <div className={luminaSurfaceMutedClass("rounded-lg border border-white/10 p-3")}>
              <p className="text-xs text-muted-foreground">Guided walkthrough of the command deck layout.</p>
              <Button
                type="button"
                size="sm"
                variant="command-ghost"
                className="mt-2"
                onClick={() => {
                  resetCommandDeckTour();
                  closeSettings();
                }}
              >
                Replay command deck tour
              </Button>
            </div>
            </div>
          ) : null}
        </div>

        {tab === "bot" ? (
          <DialogFooter className="border-t border-white/10 px-6 py-4">
            <Button type="button" variant="command-ghost" onClick={() => handleOpenChange(false)}>
              Close
            </Button>
            <Button
              type="button"
              variant="command-primary"
              onClick={() => void saveBotConfig()}
              disabled={!isDirty() || saving || loading}
            >
              {saving ? "Saving…" : "Save bot config"}
            </Button>
          </DialogFooter>
        ) : (
          <DialogFooter className="border-t border-white/10 px-6 py-4">
            <Button type="button" variant="command-ghost" onClick={() => handleOpenChange(false)}>
              Close
            </Button>
          </DialogFooter>
        )}
      </DialogContent>
    </Dialog>
  );
}

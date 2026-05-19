import { Settings } from "lucide-react";
import { useEffect, useState } from "react";
import { toast } from "sonner";

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
import {
  persistMonitoringApiKey,
  resolveMonitoringApiKey,
} from "@/lib/monitoringClient";
import {
  VISUAL_QUALITY_LABELS,
  VISUAL_QUALITY_PRESETS,
  type VisualQuality,
} from "@/lib/visualQualityPresets";
import { cn } from "@/lib/utils";
import { selectCurrentMode, useCoreStore } from "@/store/coreStore";
import { useBotConfigStore } from "@/store/botConfigStore";
import {
  useSettingsDialogStore,
  type SettingsTab,
} from "@/store/settingsDialogStore";
import {
  selectVisualQuality,
  useVisualSettingsStore,
} from "@/store/visualSettingsStore";

const QUALITY_ORDER: VisualQuality[] = ["low", "balanced", "high"];

const TAB_LABELS: Record<SettingsTab, string> = {
  apiKey: "API Key",
  bot: "Bot Config",
  visual: "Visual",
};

function SettingsTabBar({
  tab,
  onSelect,
}: {
  tab: SettingsTab;
  onSelect: (next: SettingsTab) => void;
}) {
  return (
    <div className="flex flex-wrap gap-1 border-b border-white/10 px-6 pb-3">
      {(Object.keys(TAB_LABELS) as SettingsTab[]).map((key) => (
        <button
          key={key}
          type="button"
          onClick={() => onSelect(key)}
          className={cn(
            "rounded-md px-3 py-1.5 font-mono text-[10px] tracking-wide uppercase transition-colors",
            tab === key
              ? "bg-cyan-500/15 text-cyan-200"
              : "text-muted-foreground hover:bg-white/5 hover:text-foreground",
          )}
        >
          {TAB_LABELS[key]}
        </button>
      ))}
    </div>
  );
}

export function SettingsDialog() {
  const open = useSettingsDialogStore((s) => s.open);
  const tab = useSettingsDialogStore((s) => s.tab);
  const openSettings = useSettingsDialogStore((s) => s.openSettings);
  const closeSettings = useSettingsDialogStore((s) => s.closeSettings);
  const setTab = useSettingsDialogStore((s) => s.setTab);

  const [apiKeyDraft, setApiKeyDraft] = useState(() => resolveMonitoringApiKey() ?? "");

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
      <DialogTrigger asChild>
        <Button
          type="button"
          size="sm"
          variant="ghost"
          className="h-9 w-9 p-0 text-muted-foreground hover:text-cyan-200"
          aria-label="Settings"
          title="Settings"
          onClick={() => openSettings("apiKey")}
        >
          <Settings className="size-4" />
        </Button>
      </DialogTrigger>
      <DialogContent className="max-h-[90vh] max-w-xl overflow-hidden p-0">
        <DialogHeader className="border-b border-white/10 px-6 py-4">
          <DialogTitle className="text-cyan-100">Settings</DialogTitle>
          <DialogDescription>
            API access, bot configuration, and visual quality
          </DialogDescription>
        </DialogHeader>

        <SettingsTabBar tab={tab} onSelect={setTab} />

        <div className="max-h-[min(58vh,520px)] overflow-y-auto px-6 py-4">
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
              <Button type="button" size="sm" onClick={saveApiKey}>
                Save API key
              </Button>
            </div>
          ) : null}

          {tab === "bot" ? (
            loading ? (
              <div className="space-y-3">
                {Array.from({ length: 4 }).map((_, i) => (
                  <div key={i} className="h-10 animate-pulse rounded-lg bg-white/5" />
                ))}
              </div>
            ) : (
              <>
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

          {tab === "visual" ? (
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
                        ? "border-cyan-400/40 bg-cyan-500/10"
                        : "border-white/10 bg-black/20 hover:border-white/20",
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
          ) : null}
        </div>

        {tab === "bot" ? (
          <DialogFooter className="border-t border-white/10 px-6 py-4">
            <Button type="button" variant="outline" onClick={() => handleOpenChange(false)}>
              Close
            </Button>
            <Button
              type="button"
              onClick={() => void saveBotConfig()}
              disabled={!isDirty() || saving || loading}
            >
              {saving ? "Saving…" : "Save bot config"}
            </Button>
          </DialogFooter>
        ) : (
          <DialogFooter className="border-t border-white/10 px-6 py-4">
            <Button type="button" variant="outline" onClick={() => handleOpenChange(false)}>
              Close
            </Button>
          </DialogFooter>
        )}
      </DialogContent>
    </Dialog>
  );
}

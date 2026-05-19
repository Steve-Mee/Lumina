import { SlidersHorizontal } from "lucide-react";
import { useEffect, useState } from "react";
import { toast } from "sonner";

import { BotConfigForm } from "@/components/config/BotConfigForm";
import { Button } from "@/components/ui/button";
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
  DialogTrigger,
} from "@/components/ui/dialog";
import { selectCurrentMode, useCoreStore } from "@/store/coreStore";
import { useBotConfigStore } from "@/store/botConfigStore";

export function BotConfigurationDialog() {
  const [open, setOpen] = useState(false);
  const [confirmClose, setConfirmClose] = useState(false);
  const operatorMode = useCoreStore(selectCurrentMode);
  const draft = useBotConfigStore((s) => s.draft);
  const loading = useBotConfigStore((s) => s.loading);
  const saving = useBotConfigStore((s) => s.saving);
  const error = useBotConfigStore((s) => s.error);
  const loadFromBackend = useBotConfigStore((s) => s.loadFromBackend);
  const updateDraft = useBotConfigStore((s) => s.updateDraft);
  const save = useBotConfigStore((s) => s.save);
  const isDirty = useBotConfigStore((s) => s.isDirty);
  const resetDraft = useBotConfigStore((s) => s.resetDraft);

  useEffect(() => {
    if (open) {
      void loadFromBackend();
    }
  }, [open, loadFromBackend]);

  const handleOpenChange = (next: boolean) => {
    if (!next && isDirty()) {
      setConfirmClose(true);
      return;
    }
    if (!next) {
      resetDraft();
    }
    setOpen(next);
  };

  const handleSave = async () => {
    const ok = await save();
    if (ok) {
      toast.success("Bot configuration saved to config.yaml");
      toast.info("Restart the engine for changes to take full effect");
      setOpen(false);
    } else if (error) {
      toast.error(error);
    }
  };

  return (
    <>
      <Dialog open={open} onOpenChange={handleOpenChange}>
        <DialogTrigger asChild>
          <Button
            type="button"
            size="sm"
            variant="ghost"
            className="h-9 w-9 p-0 text-muted-foreground hover:text-violet-200"
            aria-label="Bot configuration"
            title="Bot configuration"
          >
            <SlidersHorizontal className="size-4" />
          </Button>
        </DialogTrigger>
        <DialogContent className="bot-config-dialog max-h-[90vh] max-w-xl overflow-hidden p-0">
          <DialogHeader className="border-b border-white/10 px-6 py-4">
            <DialogTitle className="text-cyan-100">Bot Configuration</DialogTitle>
            <DialogDescription>
              Persisted to config.yaml — applies on next engine reload
            </DialogDescription>
          </DialogHeader>

          <div className="max-h-[min(60vh,520px)] overflow-y-auto px-6 py-4">
            {loading ? (
              <div className="space-y-4">
                {Array.from({ length: 4 }).map((_, index) => (
                  <div
                    key={index}
                    className="h-12 animate-pulse rounded-lg bg-white/5"
                  />
                ))}
              </div>
            ) : (
              <>
                {error ? (
                  <p className="mb-4 text-sm text-red-300/90">{error}</p>
                ) : null}
                <BotConfigForm
                  draft={draft}
                  onChange={updateDraft}
                  showModeCallout
                  operatorMode={operatorMode}
                />
              </>
            )}
          </div>

          <DialogFooter className="border-t border-white/10 px-6 py-4">
            <Button
              type="button"
              variant="outline"
              onClick={() => handleOpenChange(false)}
              disabled={saving}
            >
              Cancel
            </Button>
            <Button
              type="button"
              onClick={() => void handleSave()}
              disabled={!isDirty() || saving || loading}
            >
              {saving ? "Saving…" : "Save changes"}
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>

      <Dialog open={confirmClose} onOpenChange={setConfirmClose}>
        <DialogContent className="max-w-sm">
          <DialogHeader>
            <DialogTitle>Discard unsaved changes?</DialogTitle>
            <DialogDescription>
              Your bot configuration edits have not been saved.
            </DialogDescription>
          </DialogHeader>
          <DialogFooter>
            <Button variant="outline" onClick={() => setConfirmClose(false)}>
              Keep editing
            </Button>
            <Button
              variant="destructive"
              onClick={() => {
                resetDraft();
                setConfirmClose(false);
                setOpen(false);
              }}
            >
              Discard
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>
    </>
  );
}

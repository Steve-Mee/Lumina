/** Genesis charter: how the next phase starts. Same choice as the Phase Hub. */
import { useCallback, useEffect, useState } from "react";
import { toast } from "sonner";

import { PhaseHubAdvanceSection } from "@/components/maturity/PhaseHubAdvanceSection";
import {
  type AdvanceMode,
  type MaturityHubPayload,
  fetchMaturityHub,
  postAdvanceNextPhase,
  postMaturityPreferences,
} from "@/lib/maturationClient";

export function GenesisAdvanceChoice() {
  const [hub, setHub] = useState<MaturityHubPayload | null>(null);
  const [busy, setBusy] = useState(false);
  const [telegramToken, setTelegramToken] = useState("");

  const reload = useCallback(async () => {
    try {
      setHub(await fetchMaturityHub());
    } catch {
      setHub(null);
    }
  }, []);

  useEffect(() => {
    void reload();
  }, [reload]);

  const onSetMode = async (mode: AdvanceMode) => {
    setBusy(true);
    try {
      await postMaturityPreferences(mode);
      toast.success(
        mode === "auto_evolve"
          ? "Lumina start de volgende fase zelf. REAL blijft op jouw goedkeuring wachten."
          : mode === "telegram"
            ? "Elke volgende fase wacht op YES in Telegram."
            : "Je start elke fase zelf.",
      );
      await reload();
    } catch (err) {
      toast.error(err instanceof Error ? err.message : "Kon de keuze niet bewaren");
    } finally {
      setBusy(false);
    }
  };

  const onAdvance = async () => {
    setBusy(true);
    try {
      await postAdvanceNextPhase({ confirm: true, telegramToken: telegramToken.trim() });
      setTelegramToken("");
      await reload();
    } catch (err) {
      toast.error(err instanceof Error ? err.message : "Token geweigerd");
    } finally {
      setBusy(false);
    }
  };

  return (
    <PhaseHubAdvanceSection
      hub={hub}
      busy={busy}
      telegramToken={telegramToken}
      setTelegramToken={setTelegramToken}
      onSetMode={onSetMode}
      onAdvance={onAdvance}
      setBusy={setBusy}
      reload={reload}
    />
  );
}

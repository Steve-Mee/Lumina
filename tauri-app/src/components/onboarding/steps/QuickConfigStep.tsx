import { motion } from "framer-motion";

import { BotConfigForm } from "@/components/config/BotConfigForm";
import { Button } from "@/components/ui/button";
import type { OnboardingDraft } from "@/store/onboardingStore";
import type { BotConfigDraft } from "@/lib/botConfigDraft";

interface QuickConfigStepProps {
  draft: OnboardingDraft;
  onChange: (patch: Partial<OnboardingDraft>) => void;
  onContinue: () => void;
}

function toBotDraft(draft: OnboardingDraft): BotConfigDraft {
  return {
    mode: draft.mode,
    risk: draft.risk,
    evolution: draft.evolution,
    preferences: {
      instrument: "ES",
      voice_enabled: true,
      screen_share_enabled: true,
    },
  };
}

export function QuickConfigStep({ draft, onChange, onContinue }: QuickConfigStepProps) {
  return (
    <motion.div
      initial={{ opacity: 0, y: 10 }}
      animate={{ opacity: 1, y: 0 }}
      className="mx-auto max-w-xl p-2 md:p-4"
    >
      <h2 className="mb-2 text-lg font-semibold">Quick Configuration</h2>
      <p className="mb-6 text-sm text-muted-foreground">
        Choose your target operations mode and core risk parameters. During Birth Phase, runtime
        is <strong className="text-cyan-300/90">always SIM</strong> (fail-closed).
      </p>

      <BotConfigForm
        draft={toBotDraft(draft)}
        onChange={(patch) =>
          onChange({
            ...patch,
            mode: patch.mode ?? draft.mode,
            risk: patch.risk ? { ...draft.risk, ...patch.risk } : draft.risk,
            evolution: patch.evolution ? { ...draft.evolution, ...patch.evolution } : draft.evolution,
          })
        }
      />

      <Button className="onboarding-cta mt-8 w-full py-5" onClick={onContinue}>
        Continue
      </Button>
    </motion.div>
  );
}

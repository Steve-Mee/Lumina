import { CommandDeckPhaseReports } from "@/components/cockpit/CommandDeckPhaseReports";
import { CommandDeckRiskStrip } from "@/components/cockpit/CommandDeckRiskStrip";
import { CommandDeckStatusStrip } from "@/components/cockpit/CommandDeckStatusStrip";
import { CommandHud } from "@/components/cockpit/CommandHud";
import { EvolutionDeckPanel } from "@/components/cockpit/EvolutionDeckPanel";
import { IntelligenceDeckPanel } from "@/components/cockpit/IntelligenceDeckPanel";
import { PanelErrorBoundary } from "@/components/cockpit/PanelErrorBoundary";
import { PhaseHelixStage } from "@/components/shared/PhaseCinematicFrames";
import { preferAwakeningHub, setPreferAwakeningHub } from "@/lib/awakening/awakeningSurfacePref";
import { preferPlaygroundHub, setPreferPlaygroundHub } from "@/lib/playground/playgroundSurfacePref";
import { selectCurrentMode, useCoreStore } from "@/store/coreStore";
import { useOnboardingStore } from "@/store/onboardingStore";

export function CommandDeckScreen() {
  const operatorMode = useCoreStore(selectCurrentMode);
  const appSurface = useOnboardingStore((s) => s.payload?.app_surface);
  const operatorDeckActive = useOnboardingStore((s) => s.operatorDeckActive);
  const returnToPhaseHub = useOnboardingStore((s) => s.returnToPhaseHub);
  const setPhase = useOnboardingStore((s) => s.setPhase);

  const playgroundReturn = appSurface === "playground" && !preferPlaygroundHub();
  const awakeningReturn = appSurface === "awakening" && !preferAwakeningHub();
  const showReturn = Boolean(operatorDeckActive || appSurface === "playground" || appSurface === "awakening");
  const returnLabel = playgroundReturn ? "Playground" : awakeningReturn ? "Awakening" : "Phase Hub";
  const onReturn = () => {
    if (playgroundReturn) {
      setPreferPlaygroundHub(false);
      useOnboardingStore.setState({ operatorDeckActive: false });
      setPhase("playground");
      return;
    }
    if (awakeningReturn) {
      setPreferAwakeningHub(false);
      useOnboardingStore.setState({ operatorDeckActive: false });
      setPhase("awakening");
      return;
    }
    returnToPhaseHub();
  };

  return (
    <div className="command-deck-ops">
      <div className="command-deck-ops__helix">
        <PhaseHelixStage variant="mission" />
      </div>

      <section
        className="command-deck-ops__panel lumina-glass lumina-glass--overlay"
        aria-label={operatorMode === "REAL" ? "REAL operations" : "SIM operations"}
      >
        <header className="command-deck-ops__chrome risk-envelope-panel__toolbar">
          <div className="command-deck-ops__identity min-w-0">
            <p className="risk-envelope-panel__toolbar-title">
              {operatorMode === "REAL" ? "REAL command" : "SIM command"}
            </p>
            <p className="command-deck-ops__identity-sub">
              Living organism · fail-closed ops
            </p>
          </div>
          <div className="command-deck-ops__hud">
            <CommandHud />
          </div>
          <div className="command-deck-ops__chrome-actions">
            <CommandDeckPhaseReports />
            {showReturn ? (
              <button
                type="button"
                className="genesis-recovery-action-card__btn genesis-recovery-action-card__btn--idle command-deck-ops__return"
                onClick={onReturn}
              >
                {returnLabel}
              </button>
            ) : null}
          </div>
        </header>

        <CommandDeckStatusStrip />
        <CommandDeckRiskStrip />

        <div className="command-deck-ops__boards">
          <div className="command-deck-ops__board">
            <PanelErrorBoundary panelName="Evolution">
              <EvolutionDeckPanel className="h-full min-h-0" frameVariant="muted" />
            </PanelErrorBoundary>
          </div>
          <div className="command-deck-ops__board">
            <PanelErrorBoundary panelName="Intelligence">
              <IntelligenceDeckPanel className="h-full min-h-0" frameVariant="muted" />
            </PanelErrorBoundary>
          </div>
        </div>
      </section>
    </div>
  );
}

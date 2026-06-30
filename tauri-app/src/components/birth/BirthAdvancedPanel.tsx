import { ChevronDown, X } from "lucide-react";



import { BirthLogsPanel } from "@/components/birth/BirthLogsPanel";

import { BirthSettingsPanel } from "@/components/birth/BirthSettingsPanel";

import { PPOEvolutionDashboard } from "@/components/ppo/PPOEvolutionDashboard";

import { TrainingControlBar } from "@/components/operations/TrainingControlBar";

import { Button } from "@/components/ui/button";

import { distressPanelClass } from "@/lib/modePresentation";

import type { BirthSettingsPayload } from "@/lib/birthClient";

import type { PPOEvolutionMetric } from "@/lib/ppoEvolutionTypes";

import { cn } from "@/lib/utils";



export type BirthAdvancedSection = "logs" | "settings" | "training";



interface BirthAdvancedPanelProps {

  running: boolean;

  openSection: BirthAdvancedSection | null;

  onToggleSection: (section: BirthAdvancedSection | null) => void;

  settingsInitial?: Partial<BirthSettingsPayload>;

  trainingLogs?: PPOEvolutionMetric[];

  trainingConnected?: boolean;

  /** When true, section toggles live in the command bar; only open content renders here. */

  controlled?: boolean;

  className?: string;

}



const SECTION_LABELS: Record<BirthAdvancedSection, string> = {

  logs: "Engine logs",

  settings: "Settings",

  training: "Advanced training (PPO)",

};



function SectionContent({

  section,

  running,

  settingsInitial,

  trainingLogs,

  trainingConnected,

}: {

  section: BirthAdvancedSection;

  running: boolean;

  settingsInitial?: Partial<BirthSettingsPayload>;

  trainingLogs: PPOEvolutionMetric[];

  trainingConnected: boolean;

}) {

  if (section === "logs") {

    return <BirthLogsPanel />;

  }

  if (section === "settings") {

    return (

      <>

        {running ? (

          <p className={cn("mb-3 text-xs", distressPanelClass("warn"))}>

            Settings lock while training runs.

          </p>

        ) : null}

        <BirthSettingsPanel initial={settingsInitial} />

      </>

    );

  }

  return (

    <div className="space-y-3">

      <TrainingControlBar compact className="justify-start" />

      <PPOEvolutionDashboard

        logs={trainingLogs}

        connected={trainingConnected}

        title="PPO Evolution Dashboard"

        compact

      />

    </div>

  );

}



function SectionToggle({

  id,

  label,

  open,

  onToggle,

  children,

}: {

  id: BirthAdvancedSection;

  label: string;

  open: boolean;

  onToggle: (id: BirthAdvancedSection) => void;

  children: React.ReactNode;

}) {

  return (

    <div className="birth-advanced-section rounded-lg border border-white/8">

      <button

        type="button"

        className="birth-advanced-section__toggle flex w-full items-center justify-between gap-2 px-3 py-2 text-left"

        aria-expanded={open}

        onClick={() => onToggle(id)}

      >

        <span className="font-mono text-[10px] tracking-wide text-cyan-200/90 uppercase">{label}</span>

        <ChevronDown

          className={cn("size-3.5 shrink-0 text-muted-foreground transition-transform", open && "rotate-180")}

        />

      </button>

      {open ? <div className="border-t border-white/5 px-3 py-3">{children}</div> : null}

    </div>

  );

}



export function BirthAdvancedPanel({

  running,

  openSection,

  onToggleSection,

  settingsInitial,

  trainingLogs = [],

  trainingConnected = false,

  controlled = false,

  className,

}: BirthAdvancedPanelProps) {

  const handleToggle = (section: BirthAdvancedSection) => {

    onToggleSection(openSection === section ? null : section);

  };



  if (controlled) {

    if (!openSection) {

      return null;

    }



    const settingsLabel = running ? "Settings (locked)" : SECTION_LABELS.settings;



    return (

      <div

        className={cn(

          "birth-advanced-panel birth-advanced-panel--controlled rounded-lg border border-white/8",

          className,

        )}

      >

        <div className="flex items-center justify-between gap-2 border-b border-white/5 px-3 py-2">

          <span className="font-mono text-[10px] tracking-wide text-cyan-200/90 uppercase">

            {openSection === "settings" ? settingsLabel : SECTION_LABELS[openSection]}

          </span>

          <Button

            type="button"

            variant="ghost"

            size="sm"

            className="h-7 px-2 font-mono text-[10px] tracking-wide uppercase text-muted-foreground"

            onClick={() => onToggleSection(null)}

          >

            <X className="size-3.5" aria-hidden />

            Close

          </Button>

        </div>

        <div className="birth-advanced-panel__content px-3 py-3">

          <SectionContent

            section={openSection}

            running={running}

            settingsInitial={settingsInitial}

            trainingLogs={trainingLogs}

            trainingConnected={trainingConnected}

          />

        </div>

      </div>

    );

  }



  return (

    <div className={cn("birth-advanced-panel space-y-2", className)}>

      <SectionToggle

        id="logs"

        label="Engine logs"

        open={openSection === "logs"}

        onToggle={handleToggle}

      >

        <BirthLogsPanel />

      </SectionToggle>



      <SectionToggle

        id="settings"

        label={running ? "Settings (locked)" : "Settings"}

        open={openSection === "settings"}

        onToggle={handleToggle}

      >

        {running ? (

          <p className={cn("mb-3 text-xs", distressPanelClass("warn"))}>

            Settings lock while training runs.

          </p>

        ) : null}

        <BirthSettingsPanel initial={settingsInitial} />

      </SectionToggle>



      {running || trainingLogs.length > 0 || trainingConnected ? (

        <SectionToggle

          id="training"

          label="Advanced training (PPO)"

          open={openSection === "training"}

          onToggle={handleToggle}

        >

          <div className="space-y-3">

            <TrainingControlBar compact className="justify-start" />

            <PPOEvolutionDashboard

              logs={trainingLogs}

              connected={trainingConnected}

              title="PPO Evolution Dashboard"

              compact

            />

          </div>

        </SectionToggle>

      ) : null}

    </div>

  );

}



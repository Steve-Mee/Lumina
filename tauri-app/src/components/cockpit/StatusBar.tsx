import {

  selectCurrentMode,

  selectModeSyncStatus,

  useCoreStore,

} from "@/store/coreStore";

import { cn } from "@/lib/utils";

import { modeValueClass } from "@/lib/modePresentation";

import { useEffect, useState } from "react";

import { ModeBadge } from "@/components/cockpit/ModeBadge";



interface StatusBarProps {

  className?: string;

}



function formatClock(date: Date): string {

  return date.toLocaleTimeString(undefined, {

    hour: "2-digit",

    minute: "2-digit",

    second: "2-digit",

    hour12: false,

  });

}



export function StatusBar({ className }: StatusBarProps) {

  const mode = useCoreStore(selectCurrentMode);

  const modeSyncStatus = useCoreStore(selectModeSyncStatus);

  const [clock, setClock] = useState(() => formatClock(new Date()));

  const showModeBadge = modeSyncStatus === "error";



  useEffect(() => {

    const timer = window.setInterval(() => setClock(formatClock(new Date())), 1000);

    return () => window.clearInterval(timer);

  }, []);



  return (

    <footer

      data-mode={mode}

      className={cn(

        "status-bar lumina-glass lumina-glass--panel relative z-10 flex h-10 shrink-0 items-center justify-between gap-4 border-t px-5 font-mono text-[11px] text-muted-foreground",

        mode === "REAL" && "border-t-[color-mix(in_srgb,var(--real-chrome-accent)_22%,transparent)]",

        className,

      )}

    >

      <div className="status-bar__brand flex items-center gap-2 tracking-[0.18em] uppercase">

        <span>LUMINA</span>

      </div>

      <div className="flex items-center gap-3">

        {showModeBadge ? <ModeBadge mode={mode} /> : null}

        <time className={cn("tabular-nums", modeValueClass(mode))} dateTime={clock}>

          {clock}

        </time>

      </div>

    </footer>

  );

}


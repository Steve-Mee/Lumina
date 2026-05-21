import {
  selectCurrentMode,
  useCoreStore,
} from "@/store/coreStore";
import { glassSurfaceClass } from "@/lib/glassGlowTaxonomy";
import { cn } from "@/lib/utils";

interface StatusBarProps {
  className?: string;
}

export function StatusBar({ className }: StatusBarProps) {
  const mode = useCoreStore(selectCurrentMode);

  return (
    <footer
      data-mode={mode}
      className={cn(
        "status-bar status-bar--organism status-bar--glass relative z-10 flex h-10 shrink-0 items-center justify-between gap-4 border-t px-5 font-mono text-[11px] text-muted-foreground",
        glassSurfaceClass("lumina-glass--hud"),
        mode === "REAL" && "border-t-[color-mix(in_srgb,var(--real-chrome-accent)_22%,transparent)]",
        className,
      )}
    >
      <div className="status-bar__brand flex items-center gap-2 tracking-[0.18em] uppercase">
        <span>LUMINA</span>
      </div>
      <p className="status-bar__hint text-[10px] tracking-[0.12em] uppercase opacity-70">
        Neural command deck
      </p>
    </footer>
  );
}

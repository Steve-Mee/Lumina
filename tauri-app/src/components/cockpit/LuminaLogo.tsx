import { cn } from "@/lib/utils";

export function LuminaLogo({ className }: { className?: string }) {
  return (
    <div
      className={cn(
        "relative flex size-40 items-center justify-center md:size-48",
        className,
      )}
      aria-hidden
    >
      <div className="cockpit-logo-ring absolute inset-0 rounded-full border border-cyan-400/20" />
      <div className="cockpit-logo-ring-inner absolute inset-4 rounded-full border border-violet-400/25 border-dashed" />
      <div className="absolute inset-8 rounded-full border border-cyan-400/10" />
      <div className="cockpit-logo-core size-16 rounded-full bg-gradient-to-br from-cyan-400/80 via-violet-500/70 to-indigo-600/80 md:size-20" />
      <div className="absolute size-24 rounded-full bg-cyan-400/5 blur-xl md:size-28" />
    </div>
  );
}

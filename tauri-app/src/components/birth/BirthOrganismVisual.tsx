import { cn } from "@/lib/utils";
import { usePrefersReducedMotion } from "@/hooks/usePrefersReducedMotion";

interface BirthOrganismVisualProps {
  awakening?: boolean;
  className?: string;
}

export function BirthOrganismVisual({ awakening = false, className }: BirthOrganismVisualProps) {
  const reducedMotion = usePrefersReducedMotion();

  return (
    <div
      className={cn(
        "birth-organism relative mx-auto flex size-48 items-center justify-center md:size-56",
        awakening && "birth-organism--awakening",
        reducedMotion && "birth-organism--static",
        className,
      )}
      aria-hidden
    >
      <div className="birth-organism-ring birth-organism-ring--outer" />
      <div className="birth-organism-ring birth-organism-ring--inner" />
      <div className="birth-organism-helix birth-organism-helix--a" />
      <div className="birth-organism-helix birth-organism-helix--b" />
      <div className="birth-organism-core" />
      {awakening ? <div className="birth-organism-burst" /> : null}
    </div>
  );
}

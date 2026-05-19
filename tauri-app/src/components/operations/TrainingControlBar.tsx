import { Pause, Play } from "lucide-react";
import { toast } from "sonner";

import { Button } from "@/components/ui/button";
import { pauseTraining, resumeTraining } from "@/lib/runtimeClient";
import { cn } from "@/lib/utils";

interface TrainingControlBarProps {
  className?: string;
  compact?: boolean;
}

export function TrainingControlBar({ className, compact }: TrainingControlBarProps) {
  return (
    <div className={cn("flex flex-wrap gap-2", className)}>
      <Button
        type="button"
        size={compact ? "xs" : "sm"}
        variant="secondary"
        onClick={() =>
          void pauseTraining()
            .then((r) => toast.success(r.message))
            .catch((e) => toast.error(e instanceof Error ? e.message : "Pause failed"))
        }
      >
        <Pause className="mr-1 size-3" />
        Pause training
      </Button>
      <Button
        type="button"
        size={compact ? "xs" : "sm"}
        variant="secondary"
        onClick={() =>
          void resumeTraining()
            .then((r) => toast.success(r.message))
            .catch((e) => toast.error(e instanceof Error ? e.message : "Resume failed"))
        }
      >
        <Play className="mr-1 size-3" />
        Resume training
      </Button>
    </div>
  );
}

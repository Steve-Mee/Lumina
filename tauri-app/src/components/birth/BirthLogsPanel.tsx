import { useCallback, useEffect, useState } from "react";
import { RefreshCw } from "lucide-react";

import { Button } from "@/components/ui/button";
import { fetchBirthLogsTail } from "@/lib/birthClient";
import { cn } from "@/lib/utils";

interface BirthLogsPanelProps {
  className?: string;
}

export function BirthLogsPanel({ className }: BirthLogsPanelProps) {
  const [stderrPath, setStderrPath] = useState("");
  const [stderr, setStderr] = useState<string[]>([]);
  const [fullPath, setFullPath] = useState("");

  const refresh = useCallback(async () => {
    const payload = await fetchBirthLogsTail(30);
    setStderrPath(payload.stderr_path);
    setStderr(payload.stderr_tail ?? []);
    setFullPath(payload.full_log_path);
  }, []);

  useEffect(() => {
    void refresh();
    const id = window.setInterval(() => void refresh(), 12_000);
    return () => window.clearInterval(id);
  }, [refresh]);

  return (
    <details className={cn("birth-logs-panel", className)}>
      <summary className="birth-logs-panel__summary">
        Birth logs & diagnostics
      </summary>
      <div className="birth-logs-panel__body">
        <p className="birth-logs-panel__paths">
          stderr: {stderrPath || "—"} · full log: {fullPath || "—"}
        </p>
        <Button
          type="button"
          size="xs"
          variant="command-ghost"
          className="birth-logs-panel__refresh"
          onClick={() => void refresh()}
        >
          <RefreshCw className="mr-1 size-3" aria-hidden />
          Refresh logs
        </Button>
        <pre className="birth-logs-panel__pre">
          {stderr.length ? stderr.join("\n") : "No stderr tail"}
        </pre>
      </div>
    </details>
  );
}

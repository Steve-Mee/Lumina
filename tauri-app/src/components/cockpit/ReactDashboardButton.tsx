import { useCallback, useEffect, useState } from "react";
import { ExternalLink } from "lucide-react";
import { toast } from "sonner";

import { Button } from "@/components/ui/button";
import { useAdaptiveIntelligenceContext } from "@/context/AdaptiveIntelligenceContext";
import { fetchReactDashboardStatus } from "@/lib/opsClient";
import { resolveBackendBaseUrl } from "@/lib/setupClient";

export function ReactDashboardButton() {
  const { apiKeyConfigured } = useAdaptiveIntelligenceContext();
  const [url, setUrl] = useState("");
  const [ready, setReady] = useState(false);

  const refresh = useCallback(async () => {
    if (!apiKeyConfigured) return;
    try {
      const status = await fetchReactDashboardStatus();
      setReady(Boolean(status.ready));
      setUrl(String(status.react_url ?? `${resolveBackendBaseUrl()}/ui/`));
    } catch {
      setUrl(`${resolveBackendBaseUrl()}/ui/`);
      setReady(false);
    }
  }, [apiKeyConfigured]);

  useEffect(() => {
    void refresh();
  }, [refresh]);

  const openDashboard = () => {
    const target = url || `${resolveBackendBaseUrl()}/ui/`;
    window.open(target, "_blank", "noopener,noreferrer");
    toast.success(ready ? "Opening React dashboard" : "Opening dashboard URL (build may be missing)");
  };

  return (
    <Button type="button" size="sm" variant="command-ghost" onClick={openDashboard}>
      <ExternalLink className="mr-1 size-3" />
      React dashboard
    </Button>
  );
}

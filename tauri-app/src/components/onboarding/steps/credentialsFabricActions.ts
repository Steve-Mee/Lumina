/** Fabric / NT action helpers for Credentials vault (Tauri UI god split). */
import { toast } from "sonner";

import {
  detectNinjaTrader,
  NINJATRADER_DOWNLOAD_URL,
} from "@/lib/ninjaTraderClient";
import {
  postFabricBootstrap,
  postFabricConnectionTest,
  type FabricConnectionTestReport,
} from "@/lib/setupClient";
import type { OnboardingDraft } from "@/store/onboardingStore";

type Creds = OnboardingDraft["credentials"];

export function openNinjaTraderInstall(): void {
  window.open(NINJATRADER_DOWNLOAD_URL, "_blank", "noopener,noreferrer");
}

export async function refreshNinjaTraderInstalled(
  setNtInstalled: (v: boolean | null) => void,
  setNtChecking: (v: boolean) => void,
): Promise<boolean> {
  setNtChecking(true);
  try {
    const det = await detectNinjaTrader();
    setNtInstalled(det.installed);
    return det.installed;
  } catch {
    setNtInstalled(false);
    return false;
  } finally {
    setNtChecking(false);
  }
}

export async function runFabricBootstrap(opts: {
  creds: Creds;
  onImportFromEnv: () => Promise<boolean>;
  setBootstrapping: (v: boolean) => void;
  setDeployNote: (v: string | null) => void;
  setFabricCertified: (v: boolean) => void;
}): Promise<void> {
  opts.setBootstrapping(true);
  try {
    const result = await postFabricBootstrap();
    if (result.token_ready && !opts.creds.LUMINA_FABRIC_TOKEN.trim()) {
      await opts.onImportFromEnv();
    }
    if (result.deploy?.deployed) {
      opts.setDeployNote(`AddOn deployed · ${result.deploy.copied.length} files`);
    } else if (result.deploy?.error) {
      opts.setDeployNote(result.deploy.error);
    }
    if (result.fabric_link_green) opts.setFabricCertified(true);
    if (result.halt) toast.error("Fabric halt active — re-run diagnostic");
  } catch (err) {
    toast.error(err instanceof Error ? err.message : "Fabric bootstrap failed");
  } finally {
    opts.setBootstrapping(false);
  }
}

export async function runFabricDiagnostic(opts: {
  ntInstalled: boolean | null;
  setVaultTabFabric: () => void;
  setTestingFabric: (v: boolean) => void;
  setFabricReport: (r: FabricConnectionTestReport | null) => void;
  setFabricCertified: (v: boolean) => void;
}): Promise<void> {
  if (opts.ntInstalled === false) {
    toast.error("Install NinjaTrader 8 first");
    opts.setVaultTabFabric();
    return;
  }
  opts.setTestingFabric(true);
  opts.setFabricReport(null);
  try {
    const report = await postFabricConnectionTest({
      include_safe_mode: true,
      instrument: "MES",
    });
    opts.setFabricReport(report);
    opts.setFabricCertified(Boolean(report.certified) || report.overall === "green");
    if (report.overall === "green") toast.success("Fabric link: GREEN — Genesis unlocked");
    else if (report.overall === "amber")
      toast.message("Fabric link: AMBER — not enough for Genesis");
    else toast.error("Fabric link: RED — fix issues before Genesis");
  } catch (err) {
    const message = err instanceof Error ? err.message : "Fabric test failed";
    toast.error(message);
    opts.setFabricCertified(false);
    opts.setFabricReport({
      overall: "red",
      started_at: new Date().toISOString(),
      duration_ms: 0,
      target: "127.0.0.1:50051",
      gateway_mode: "sim",
      checks: [{ id: "client_error", title: "Diagnostics request", status: "fail", message }],
      summary: message,
      remediation: ["Backend :8000?", "Host on :50051?", "Token matches?"],
    });
  } finally {
    opts.setTestingFabric(false);
  }
}

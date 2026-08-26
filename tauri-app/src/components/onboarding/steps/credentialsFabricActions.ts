/** Fabric / NT action helpers for Credentials vault (Tauri UI god split). */
import { toast } from "sonner";

import {
  detectNinjaTrader,
  NINJATRADER_DOWNLOAD_URL,
} from "@/lib/ninjaTraderClient";
import {
  fetchFabricLinkStatus,
  postFabricBootstrap,
  postFabricConnectionTest,
  postFabricHeal,
  type FabricConnectionTestReport,
  type FabricHealResult,
} from "@/lib/setupClient";
import { startupSafeToastMessage } from "@/lib/startupToastGate";
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
}): Promise<{
  fabric_link_green: boolean;
  halt: boolean;
  host_ready?: boolean;
  gate_birth_ok?: boolean;
  proof?: { certified?: boolean; badge_ok?: boolean };
} | null> {
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
    // Proof / gate — never set certified from live green alone or paper misread.
    const proofOk = Boolean(
      result.proof?.certified ||
        result.proof?.badge_ok ||
        result.gate_birth_ok ||
        (result.host_ready && result.certificate),
    );
    if (proofOk) opts.setFabricCertified(true);
    if (result.halt) toast.error("Fabric halt active — use Repair connection (will restart NinjaTrader)");
    return {
      fabric_link_green: Boolean(result.fabric_link_green),
      halt: Boolean(result.halt),
      host_ready: Boolean(result.host_ready),
      gate_birth_ok: Boolean(result.gate_birth_ok),
      proof: result.proof,
    };
  } catch (err) {
    toast.error(err instanceof Error ? err.message : "Fabric bootstrap failed");
    return null;
  } finally {
    opts.setBootstrapping(false);
  }
}

/**
 * Soft auto-setup on Credentials mount.
 * - NEVER force-closes NinjaTrader
 * - Prefer diagnostic only when possible (overwriting DLLs while NT runs can crash it)
 */
export async function runFabricSoftSetup(opts: {
  ntInstalled: boolean | null;
  setVaultTabFabric: () => void;
  setRepairing: (v: boolean) => void;
  setHealResult: (r: FabricHealResult | null) => void;
  setFabricReport: (r: FabricConnectionTestReport | null) => void;
  setFabricCertified: (v: boolean) => void;
  setDeployNote: (v: string | null) => void;
}): Promise<FabricHealResult | null> {
  if (opts.ntInstalled === false) {
    opts.setVaultTabFabric();
    return null;
  }
  // Light auto path: port/auth/hist only — skip multi-second SAFE_MODE probe (faster reconnect UX).
  // Full SAFE_MODE coverage stays on explicit "Test connection".
  opts.setRepairing(true);
  opts.setHealResult(null);
  try {
    startupSafeToastMessage("Connecting to NinjaTrader Fabric…");
    const report = await postFabricConnectionTest({
      include_safe_mode: false,
      instrument: "",
    });
    opts.setFabricReport(report);
    opts.setFabricCertified(Boolean(report.certified) || report.overall === "green");
    opts.setDeployNote(
      report.overall === "green"
        ? "Dual-plane proof OK (quick check) — live Brain may show AMBER until supervisor connects"
        : `Quick check ${report.overall.toUpperCase()} — run full Test connection if needed`,
    );
    if (report.overall === "green") {
      // Kick live SSOT (supervisor ensure) after proof — do not claim live GREEN alone.
      try {
        const link = await fetchFabricLinkStatus();
        const level = String(link.level || "").toUpperCase();
        if (level === "GREEN") {
          toast.success("Fabric live GREEN · proof OK");
        } else {
          toast.success(
            `Proof GREEN · live ${level || "AMBER"} — Brain session reconnecting`,
          );
        }
      } catch {
        toast.success("Fabric proof GREEN — verifying live host…");
      }
    } else if (report.overall === "amber") {
      toast.message("Fabric link AMBER — open NinjaTrader if needed, then full Test connection");
    } else {
      const authFail = report.checks?.some(
        (c) => c.id === "auth_ok" && c.status === "fail",
      );
      // Fail-closed: only treat SSOT heal as true when the host explicitly flags it.
      const healed =
        (report as { token_ssot?: { healed_process_env?: boolean } }).token_ssot
          ?.healed_process_env === true ||
        Boolean(
          report.checks?.some(
            (c) =>
              c.id === "token_present" &&
              String(c.message || "").toLowerCase().includes("healed"),
          ),
        );
      if (authFail && healed) {
        toast.error(
          "Token SSOT healed to fabric.json — click Test connection again (host was already green)",
        );
      } else if (authFail) {
        toast.error(
          "Fabric auth failed — token mismatch with NinjaTrader host. Use Repair connection",
        );
      } else {
        toast.error("Fabric not GREEN yet — wait for NT Connected, then Test connection");
      }
    }
    return null;
  } catch (err) {
    const message = err instanceof Error ? err.message : "Soft setup failed";
    toast.error(message);
    return null;
  } finally {
    opts.setRepairing(false);
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
      // Empty → server uses config trading.instrument (MES SEP26), not bare MES.
      instrument: "",
    });
    opts.setFabricReport(report);
    opts.setFabricCertified(Boolean(report.certified) || report.overall === "green");
    if (report.overall === "green") {
      try {
        const link = await fetchFabricLinkStatus();
        const level = String(link.level || "").toUpperCase();
        const gate = Boolean(link.gate_birth_ok || link.host_ready);
        if (level === "GREEN" && gate) {
          toast.success("Live GREEN · dual-plane proof — Genesis unlocked");
        } else if (gate) {
          toast.success(
            `Proof GREEN · live ${level || "AMBER"} — host ready for Genesis`,
          );
        } else {
          toast.message(
            "Proof GREEN but host not ready — wait for NinjaTrader bridge / Repair",
          );
        }
      } catch {
        toast.success("Fabric proof GREEN — recheck live status in LUMINA Link");
      }
    } else if (report.overall === "amber")
      toast.message("Fabric link: AMBER — not enough for Genesis");
    else toast.error("Fabric link: RED — use Repair connection");
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
      remediation: ["Click Repair connection", "Backend :8000?", "NinjaTrader installed?"],
    });
  } finally {
    opts.setTestingFabric(false);
  }
}

/** Explicit user Repair: closes NinjaTrader so locked DLLs can be replaced. */
export async function runFabricRepair(opts: {
  ntInstalled: boolean | null;
  setVaultTabFabric: () => void;
  setRepairing: (v: boolean) => void;
  setHealResult: (r: FabricHealResult | null) => void;
  setFabricReport: (r: FabricConnectionTestReport | null) => void;
  setFabricCertified: (v: boolean) => void;
  setDeployNote: (v: string | null) => void;
}): Promise<FabricHealResult | null> {
  if (opts.ntInstalled === false) {
    toast.error("Install NinjaTrader 8 first");
    opts.setVaultTabFabric();
    openNinjaTraderInstall();
    return null;
  }
  opts.setRepairing(true);
  opts.setHealResult(null);
  try {
    toast.message(
      "Repairing NinjaTrader connection… NinjaTrader will close and restart — re-login in NT after.",
    );
    const result = await postFabricHeal({
      close_ninjatrader: true, // user-initiated only
      launch_ninjatrader: true,
      run_diagnostic: true,
      allow_simhost: false,
      force_redeploy: true,
      wait_host_sec: 100,
    });
    opts.setHealResult(result);
    if (result.report) {
      opts.setFabricReport(result.report as FabricConnectionTestReport);
    }
    opts.setFabricCertified(Boolean(result.certified) || result.overall === "green");
    const passed = result.steps.filter((s) => s.status === "pass").length;
    opts.setDeployNote(
      result.ok
        ? `Connection repaired · ${passed} steps OK`
        : `Repair incomplete · ${result.overall.toUpperCase()}`,
    );
    if (result.ok) {
      toast.success("NinjaTrader connection repaired — GREEN");
    } else {
      const need = result.needs_user[0];
      toast.error(need?.title ?? "Repair did not fully succeed — see steps below");
    }
    return result;
  } catch (err) {
    const message = err instanceof Error ? err.message : "Repair failed";
    toast.error(message);
    opts.setFabricCertified(false);
    return null;
  } finally {
    opts.setRepairing(false);
  }
}

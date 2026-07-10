import { describe, expect, it } from "vitest";

import {
  formatMetricTarget,
  formatMetricValue,
  parseFailureReasonToken,
  resolveCertificateDiagnostics,
  resolveCertificateFailureSubtitle,
} from "@/lib/birthCertificateDiagnostics";
import type { BirthStatusPayload } from "@/lib/birthClient";
import { resolveBirthScreenPhaseHeader } from "@/lib/luminaPhasePresentation";

describe("birthCertificateDiagnostics", () => {
  it("parses failure reason tokens", () => {
    const row = parseFailureReasonToken("oos_winrate:0.31/0.48");
    expect(row).not.toBeNull();
    expect(row?.metricId).toBe("oos_winrate");
    expect(row?.actual).toBeCloseTo(0.31);
    expect(row?.target).toBeCloseTo(0.48);
    expect(row?.passed).toBe(false);
  });

  it("formats drawdown as percent points", () => {
    expect(formatMetricValue("percent", 25.46, "oos_max_drawdown_pct")).toBe("25.5%");
    expect(formatMetricValue("percent", 0.31, "oos_winrate")).toBe("31.0%");
  });

  it("resolves diagnostics from failure_reasons when oos_metrics empty", () => {
    const status: BirthStatusPayload = {
      status: "certificate_failed",
      certificate_ok: false,
      failure_reasons: [
        "oos_winrate:0.31/0.48",
        "oos_sharpe:-5.62/0.35",
        "oos_max_drawdown_pct:25.46/8.00",
      ],
    };
    const diag = resolveCertificateDiagnostics(status);
    expect(diag.metrics.length).toBeGreaterThanOrEqual(3);
    expect(diag.metrics.find((m) => m.metricId === "oos_winrate")?.actual).toBeCloseTo(0.31);
  });

  it("builds runway-aware subtitle", () => {
    const status: BirthStatusPayload = {
      status: "certificate_failed",
      fast_path_eligible: true,
    };
    expect(resolveCertificateFailureSubtitle(status)).toContain("runway");
  });
});

describe("resolveBirthScreenPhaseHeader certificate overlay", () => {
  it("uses short status when certificate overlay is active", () => {
    const header = resolveBirthScreenPhaseHeader({
      genesisMode: false,
      missionMode: false,
      awakening: false,
      activating: false,
      interrupted: false,
      certificateFailed: true,
      certificateOverlayActive: true,
      stageStalledActive: false,
      milestones: [],
      phaseSubtitle: "Certificate thresholds not met — review OOS metrics below and retry birth.",
    });
    expect(header.status).toBe("Diagnostics below");
    expect(header.title).toBe("Certificate");
  });
});

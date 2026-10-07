import { describe, expect, it } from "vitest";

import {
  describePhaseStartOutcome,
  formatAwakeningProbe,
  formatLearned,
  HUB_WIPE_CARDS,
  hubCharterTiles,
  hubVerdict,
  phaseLabel,
  phaseStartIncomplete,
  proofLabel,
  startPhaseCtaLabel,
} from "@/components/maturity/phaseHubFormat";
import { resolveHubCharterTiles } from "@/components/maturity/phaseHubTiles";
import type { MaturityHubPayload } from "@/lib/maturationClient";

const learnedDump = {
  trades: 1145,
  stage_winrate: 0.3333,
  edgescore: 0.6944,
  curriculum_stage: "stage5_probe_handoff",
  message: "Birth Foundation complete — evolvable plant. Certificate OOS is Proving Ground.",
  birth_exit: {
    schema: "birth_exit_v1",
    exited: true,
    policy: { adr: ["0036"] },
  },
};

describe("phaseHubFormat", () => {
  it("never JSON.stringifies nested birth_exit into operator lines", () => {
    const lines = formatLearned(learnedDump);
    expect(lines.join(" ")).not.toContain("{");
    expect(lines.join(" ")).not.toContain("birth_exit_v1");
    expect(lines.some((l) => l.includes("1,145"))).toBe(true);
    expect(lines.some((l) => l.includes("33.3%"))).toBe(true);
    expect(lines.some((l) => /Probe/i.test(l))).toBe(true);
  });

  it("labels proofs for operators, not raw ids", () => {
    expect(proofLabel("evolution_proof_passed")).toBe("Evolution proof");
    expect(proofLabel("adr0026_wr_missing")).toMatch(/holdout WR missing/i);
    expect(proofLabel("median_loss_r_missing")).toMatch(/Process-R/i);
    expect(proofLabel("twin_samples>=50")).toMatch(/Twin watch of this run/);
    expect(phaseLabel("awakening")).toBe("Awakening");
    expect(startPhaseCtaLabel("awakening")).toBe("Start Awakening");
    expect(startPhaseCtaLabel("awakening", { retry: true })).toBe("Retry Awakening");
  });

  it("describes an incomplete Awakening start without hiding missing proofs", () => {
    const hub = {
      runner_active: false,
      focus_status: "failed",
      last_result: { ok: false, missing: ["baseline_not_the_plant"] },
      exit_eval: { ok: false, missing: ["baseline_not_the_plant"] },
    } as unknown as MaturityHubPayload;
    expect(phaseStartIncomplete(hub)).toBe(true);
    expect(describePhaseStartOutcome(hub, "awakening").ok).toBe(false);
    expect(describePhaseStartOutcome(hub, "awakening").message).toMatch(/Plant baseline/i);
  });

  it("formats Birth OOS vs Awakening shot lift without JSON", () => {
    const line = formatAwakeningProbe({
      baseline_oos_wr: 0.333333,
      probe_oos_wr: 0.34,
    });
    expect(line).toContain("33.3%");
    expect(line).toContain("34.0%");
    expect(line).not.toContain("{");
  });

  it("charter tiles stay six scalars with no JSON values", () => {
    const hub = {
      last_completed: "birth",
      next_phase: "birth",
      focus_phase: "birth",
      birth_exit_exited: true,
      learned: learnedDump,
      phase_specs: {
        awakening: { human_goal: "First Watch: frozen plant baseline on holdout, STABLE, no constitution event." },
      },
    } as unknown as MaturityHubPayload;
    const tiles = hubCharterTiles(hub);
    expect(tiles).toHaveLength(6);
    expect(tiles.map((t) => t.value).join(" ")).not.toContain("{");
    expect(tiles[0]?.value).toBe("Birth");
    expect(tiles[1]?.value).toBe("1,145");
  });

  it("Awakening focus shows First Watch plant/constitution KPIs, not Birth WR", () => {
    const hub = {
      last_completed: "birth",
      next_phase: "awakening",
      focus_phase: "awakening",
      birth_exit_exited: true,
      learned: learnedDump,
      focus_learned: {
        n_b: 133,
        occupancy: 0.28,
        stable_class: "INCONCLUSIVE",
        child_weight_sha: "aa",
        init_weight_sha: "aa",
        constitution_violations: 0,
        constitution_blocks: 0,
        note: "First Watch: frozen plant baseline on holdout B, no learn (ADR-0049)",
      },
    } as unknown as MaturityHubPayload;
    const tiles = resolveHubCharterTiles(hub);
    expect(tiles.map((t) => t.label)).toEqual([
      "Goal",
      "n_B",
      "Occupancy",
      "STABLE",
      "Plant",
      "Constitution",
    ]);
    expect(tiles[0]?.value).toBe("First Watch");
    expect(tiles[1]?.value).toContain("133");
    expect(tiles[1]?.value).toContain("500");
    expect(tiles.find((t) => t.label === "Plant")?.value).toBe("plant");
    expect(tiles.find((t) => t.label === "Constitution")?.value).toBe("clear");
    expect(tiles.map((t) => t.value).join(" ")).not.toContain("1,145");
    expect(hubVerdict(hub)).toMatch(/First Watch/i);
    expect(hubVerdict(hub)).not.toMatch(/eyes open/i);
  });

  it("ignores a stored eyes-open note so the old 8-cycle exam cannot outvote First Watch", () => {
    const hub = {
      focus_phase: "awakening",
      next_phase: "awakening",
      focus_learned: {
        note: "Awakening: eyes open — prefer better than frozen π*. STABLE + n_B≥500 AND.",
      },
      phase_specs: {
        awakening: { human_goal: "Open eyes: prefer better policies, regime awareness, recovery." },
      },
    } as unknown as MaturityHubPayload;
    expect(hubVerdict(hub)).toMatch(/First Watch/i);
    expect(hubVerdict(hub)).not.toMatch(/eyes open/i);
    expect(hubVerdict(hub)).not.toMatch(/prefer better/i);
  });

  it("Awakening n_B missing is em dash, measured zero is 0 / 500", () => {
    const missing = resolveHubCharterTiles({
      focus_phase: "awakening",
      focus_learned: {},
    } as unknown as MaturityHubPayload);
    expect(missing.find((t) => t.label === "n_B")?.value).toBe("— / 500");
    const zero = resolveHubCharterTiles({
      focus_phase: "awakening",
      focus_learned: { n_b: 0 },
    } as unknown as MaturityHubPayload);
    expect(zero.find((t) => t.label === "n_B")?.value).toBe("0 / 500");
  });

  it("Playground focus shows first fill / n_P / WR vs BE, not Birth WR", () => {
    const hub = {
      last_completed: "awakening",
      next_phase: "playground",
      focus_phase: "playground",
      birth_exit_exited: true,
      learned: learnedDump,
      focus_learned: {
        n_p: 12,
        first_fill: false,
        skill_wr: 0.31,
        breakeven_wr: 0.42,
        mean_r: -0.2,
        envelope_sealed: false,
        note: "Playground: first contact — crawl in NT SIM",
      },
    } as unknown as MaturityHubPayload;
    const tiles = resolveHubCharterTiles(hub);
    expect(tiles.map((t) => t.label)).toEqual([
      "Doel",
      "Groene dagen",
      "Closes",
      "WR vs BE",
      "Mean R",
      "Envelope",
    ]);
    expect(tiles[1]?.value).toBe("0 / 5");
    expect(tiles[2]?.value).toContain("12");
    expect(tiles[2]?.value).not.toContain("150");
    expect(tiles.map((t) => t.value).join(" ")).not.toContain("1,145");
    expect(proofLabel("n_P=12 < 150")).toContain("12");
    expect(proofLabel("first_honest_fill")).toMatch(/honest SIM fill/i);
  });

  it("hub wipe cards keep Birth vs history vs setup scopes in operator copy", () => {
    const awakening = HUB_WIPE_CARDS.find((c) => c.kind === "awakening");
    const birth = HUB_WIPE_CARDS.find((c) => c.kind === "birth");
    const full = HUB_WIPE_CARDS.find((c) => c.kind === "full");
    expect(awakening?.hint).toMatch(/Keep Birth/i);
    expect(birth?.hint).toMatch(/Keep history/i);
    expect(full?.hint).toMatch(/Setup kept/i);
    expect(full?.tip).toMatch(/Smart Setup stays/i);
  });
});

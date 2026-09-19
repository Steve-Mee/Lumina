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
    expect(proofLabel("twin_samples>=50")).toMatch(/Twin watch of this run/);
    expect(phaseLabel("awakening")).toBe("Awakening");
    expect(startPhaseCtaLabel("awakening")).toBe("Start Awakening");
    expect(startPhaseCtaLabel("awakening", { retry: true })).toBe("Retry Awakening");
  });

  it("describes an incomplete Awakening start without hiding missing proofs", () => {
    const hub = {
      runner_active: false,
      focus_status: "failed",
      last_result: { ok: false, missing: ["evolution_proof_passed"] },
      exit_eval: { ok: false, missing: ["evolution_proof_passed"] },
    } as unknown as MaturityHubPayload;
    expect(phaseStartIncomplete(hub)).toBe(true);
    expect(describePhaseStartOutcome(hub, "awakening").ok).toBe(false);
    expect(describePhaseStartOutcome(hub, "awakening").message).toContain("Evolution proof");
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
        awakening: { human_goal: "Open eyes: prefer better policies, regime awareness, recovery." },
      },
    } as unknown as MaturityHubPayload;
    const tiles = hubCharterTiles(hub);
    expect(tiles).toHaveLength(6);
    expect(tiles.map((t) => t.value).join(" ")).not.toContain("{");
    expect(tiles[0]?.value).toBe("Birth");
    expect(tiles[1]?.value).toBe("1,145");
  });

  it("Awakening focus shows n_B / STABLE / Twin watch, not Birth WR", () => {
    const hub = {
      last_completed: "birth",
      next_phase: "awakening",
      focus_phase: "awakening",
      birth_exit_exited: true,
      learned: learnedDump,
      focus_learned: {
        n_b: 133,
        lift: 0.103,
        occupancy: 0.28,
        wr: 0.436,
        birth_oos_wr: 0.333,
        stable_class: "INCONCLUSIVE",
        twin_watch_n: 0,
        note: "Awakening: eyes open — prefer better than frozen π*. STABLE + n_B≥500 AND.",
      },
    } as unknown as MaturityHubPayload;
    const tiles = resolveHubCharterTiles(hub);
    expect(tiles.map((t) => t.label)).toEqual([
      "Doel",
      "n_B",
      "Lift vs Birth",
      "Occupancy",
      "STABLE",
      "Twin watch",
    ]);
    expect(tiles[1]?.value).toContain("133");
    expect(tiles[1]?.value).toContain("500");
    expect(tiles.map((t) => t.value).join(" ")).not.toContain("1,145");
    expect(hubVerdict(hub)).toMatch(/eyes open/i);
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
      "First fill",
      "n_P",
      "WR vs BE",
      "Mean R",
      "Envelope",
    ]);
    expect(tiles[2]?.value).toContain("12");
    expect(tiles[2]?.value).toContain("150");
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

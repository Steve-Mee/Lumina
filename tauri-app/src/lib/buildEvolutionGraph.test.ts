import { describe, expect, it } from "vitest";

import {
  SYNTHETIC_ROOT_HASH,
  isIdleEvolutionGraph,
  seedDemoGraph,
} from "@/lib/buildEvolutionGraph";
import type { EvolutionGraph, EvolutionNode } from "@/lib/evolutionTreeTypes";

function node(partial: Partial<EvolutionNode> & Pick<EvolutionNode, "id" | "hash">): EvolutionNode {
  return {
    fitness: 0.5,
    generation: 0,
    status: "champion",
    promptId: "live",
    version: "1",
    reasoning: "live",
    parentIds: [],
    createdAt: null,
    ...partial,
  };
}

describe("isIdleEvolutionGraph", () => {
  it("treats an empty graph as idle", () => {
    const graph: EvolutionGraph = { nodes: [], edges: [], activeHash: null, championHash: null };
    expect(isIdleEvolutionGraph(graph)).toBe(true);
  });

  it("treats the synthetic store root as idle", () => {
    const graph: EvolutionGraph = {
      nodes: [
        node({
          id: SYNTHETIC_ROOT_HASH,
          hash: SYNTHETIC_ROOT_HASH,
          promptId: "lumina_champion",
        }),
      ],
      edges: [],
      activeHash: SYNTHETIC_ROOT_HASH,
      championHash: SYNTHETIC_ROOT_HASH,
    };
    expect(isIdleEvolutionGraph(graph)).toBe(true);
  });

  it("treats the seed demo graph as idle", () => {
    expect(isIdleEvolutionGraph(seedDemoGraph())).toBe(true);
  });

  it("keeps a harvested lineage live", () => {
    const hash = "1afcf3a6c0ffee12c0ffee12c0ffee12c0ffee12c0ffee12c0ffee12c0ffee12";
    const graph: EvolutionGraph = {
      nodes: [node({ id: hash, hash, promptId: "birth_exit_pi_star" })],
      edges: [],
      activeHash: hash,
      championHash: hash,
    };
    expect(isIdleEvolutionGraph(graph)).toBe(false);
  });
});

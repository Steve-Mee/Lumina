import type { EvolutionState } from "@/store/coreStore";

import type {
  ApiDnaEdge,
  ApiDnaNode,
  ApiEvolutionTreeResponse,
  ApiPendingMutation,
  DnaNodeStatus,
  EvolutionEdge,
  EvolutionGraph,
  EvolutionNode,
  MutationType,
} from "@/lib/evolutionTreeTypes";

function normalizeStatus(raw: string | undefined): DnaNodeStatus {
  const value = (raw ?? "proposed").toLowerCase();
  if (
    value === "champion" ||
    value === "active" ||
    value === "archived" ||
    value === "proposed" ||
    value === "rejected"
  ) {
    return value;
  }
  return "proposed";
}

function normalizeMutationType(raw: string | undefined): MutationType {
  if (raw === "crossover" || raw === "bootstrap") {
    return raw;
  }
  return "mutate";
}

function deriveReasoning(status: DnaNodeStatus, mutationDepth?: string): string {
  switch (status) {
    case "champion":
      return "Current lineage leader — highest verified fitness in active generation.";
    case "active":
      return "Active strategy DNA deployed in the organism runtime.";
    case "archived":
      return "Archived lineage branch retained for audit and rollback.";
    case "rejected":
      return "Rejected after shadow evaluation or constitutional gate failure.";
    case "proposed":
    default:
      if (mutationDepth === "radical") {
        return "Radical mutation proposal — shadow evaluation pending.";
      }
      if (mutationDepth === "conservative") {
        return "Conservative mutation proposal — awaiting shadow pass.";
      }
      return "Shadow evaluation pending — challengers under review.";
  }
}

function mapApiNode(node: ApiDnaNode): EvolutionNode {
  const status = normalizeStatus(node.status);
  return {
    id: node.hash,
    hash: node.hash,
    fitness: typeof node.fitness_score === "number" ? node.fitness_score : 0.5,
    generation: typeof node.generation === "number" ? node.generation : 0,
    status,
    promptId: node.prompt_id ?? "unknown",
    version: node.version ?? "0.0.0",
    reasoning: deriveReasoning(status, node.mutation_depth),
    parentIds: Array.isArray(node.parent_ids) ? node.parent_ids : [],
    mutationDepth: node.mutation_depth,
    createdAt: node.created_at ?? null,
    contentDigest: node.content_digest ?? null,
  };
}

function mapPendingMutation(mutation: ApiPendingMutation): EvolutionNode {
  return {
    id: mutation.dna_hash,
    hash: mutation.dna_hash,
    fitness:
      typeof mutation.fitness_score === "number" ? mutation.fitness_score : 0.55,
    generation: 0,
    status: "proposed",
    promptId: "pending_mutation",
    version: "draft",
    reasoning: deriveReasoning("proposed"),
    parentIds: [],
    createdAt: null,
  };
}

export function fromApiResponse(raw: ApiEvolutionTreeResponse): EvolutionGraph {
  const nodes = (raw.nodes ?? []).map(mapApiNode);
  const nodeIds = new Set(nodes.map((node) => node.id));

  for (const pending of raw.pending_mutations ?? []) {
    if (!nodeIds.has(pending.dna_hash)) {
      nodes.push(mapPendingMutation(pending));
      nodeIds.add(pending.dna_hash);
    }
  }

  const edges: EvolutionEdge[] = (raw.edges ?? []).map((edge: ApiDnaEdge) => ({
    from: edge.from_hash,
    to: edge.to_hash,
    mutationType: normalizeMutationType(edge.mutation_type),
  }));

  const championHash = raw.champion?.hash ?? raw.active_hash ?? null;

  return {
    nodes,
    edges,
    activeHash: raw.active_hash ?? championHash,
    championHash,
  };
}

export function fromStore(
  evolutionState: EvolutionState,
  championHash?: string | null,
): EvolutionGraph {
  const rootHash =
    championHash ??
    evolutionState.activeDnaHash ??
    "0000000000000000000000000000000000000000000000000000000000000001";

  const championFitness = evolutionState.championFitness ?? 0.72;
  const nodes: EvolutionNode[] = [
    {
      id: rootHash,
      hash: rootHash,
      fitness: championFitness,
      generation: 1,
      status: "champion",
      promptId: "lumina_champion",
      version: "live",
      reasoning: deriveReasoning("champion"),
      parentIds: [],
      createdAt: null,
    },
  ];
  const edges: EvolutionEdge[] = [];

  for (const mutation of evolutionState.activeMutations) {
    if (mutation.hash === rootHash) {
      continue;
    }
    nodes.push({
      id: mutation.hash,
      hash: mutation.hash,
      fitness: Math.min(0.95, 0.55 + mutation.challengerCount * 0.05),
      generation: 2,
      status: "proposed",
      promptId: "mutation_proposal",
      version: "draft",
      reasoning: deriveReasoning("proposed"),
      parentIds: [rootHash],
      createdAt: mutation.timestamp,
    });
    edges.push({
      from: rootHash,
      to: mutation.hash,
      mutationType: "mutate",
    });
  }

  return {
    nodes,
    edges,
    activeHash: rootHash,
    championHash: rootHash,
  };
}

export function mergeGraphs(
  api: EvolutionGraph | null,
  store: EvolutionGraph,
): EvolutionGraph {
  if (!api || api.nodes.length === 0) {
    return store.nodes.length > 0 ? store : seedDemoGraph();
  }

  const nodeMap = new Map(api.nodes.map((node) => [node.id, node]));
  const edgeKeys = new Set(api.edges.map((edge) => `${edge.from}->${edge.to}`));
  const edges = [...api.edges];

  for (const node of store.nodes) {
    if (node.status !== "proposed") {
      continue;
    }
    if (!nodeMap.has(node.id)) {
      nodeMap.set(node.id, node);
    }
  }

  for (const edge of store.edges) {
    const key = `${edge.from}->${edge.to}`;
    if (!edgeKeys.has(key) && nodeMap.has(edge.to)) {
      edges.push(edge);
      edgeKeys.add(key);
    }
  }

  return {
    nodes: [...nodeMap.values()],
    edges,
    activeHash: api.activeHash ?? store.activeHash,
    championHash: api.championHash ?? store.championHash,
  };
}

export function seedDemoGraph(): EvolutionGraph {
  const genesis = "0000000000000000000000000000000000000000000000000000000000000001";
  const alpha = "aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa";
  const beta = "bbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbb";
  const champion = "cccccccccccccccccccccccccccccccccccccccccccccccccccccccccccccccc";
  const proposalA = "dddddddddddddddddddddddddddddddddddddddddddddddddddddddddddddddd";
  const proposalB = "eeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeee";

  const nodes: EvolutionNode[] = [
    {
      id: genesis,
      hash: genesis,
      fitness: 0.51,
      generation: 0,
      status: "archived",
      promptId: "lumina_genesis",
      version: "1.0.0",
      reasoning: deriveReasoning("archived"),
      parentIds: [],
      mutationDepth: "conservative",
      createdAt: "2026-05-19T10:00:00.000Z",
    },
    {
      id: alpha,
      hash: alpha,
      fitness: 0.62,
      generation: 3,
      status: "archived",
      promptId: "lumina_trader_v2",
      version: "2.1.0",
      reasoning: deriveReasoning("archived", "conservative"),
      parentIds: [genesis],
      mutationDepth: "conservative",
      createdAt: "2026-05-19T11:00:00.000Z",
    },
    {
      id: beta,
      hash: beta,
      fitness: 0.68,
      generation: 5,
      status: "active",
      promptId: "lumina_trader_v2",
      version: "2.4.0",
      reasoning: deriveReasoning("active", "conservative"),
      parentIds: [alpha],
      mutationDepth: "conservative",
      createdAt: "2026-05-19T12:00:00.000Z",
    },
    {
      id: champion,
      hash: champion,
      fitness: 0.74,
      generation: 8,
      status: "champion",
      promptId: "lumina_trader_v3",
      version: "3.2.1",
      reasoning: deriveReasoning("champion", "radical"),
      parentIds: [beta],
      mutationDepth: "radical",
      createdAt: "2026-05-19T14:30:00.000Z",
    },
    {
      id: proposalA,
      hash: proposalA,
      fitness: 0.61,
      generation: 9,
      status: "proposed",
      promptId: "mutation_alpha",
      version: "draft",
      reasoning: deriveReasoning("proposed", "conservative"),
      parentIds: [champion],
      mutationDepth: "conservative",
      createdAt: "2026-05-19T15:00:00.000Z",
    },
    {
      id: proposalB,
      hash: proposalB,
      fitness: 0.58,
      generation: 9,
      status: "proposed",
      promptId: "mutation_beta",
      version: "draft",
      reasoning: deriveReasoning("proposed", "radical"),
      parentIds: [champion],
      mutationDepth: "radical",
      createdAt: "2026-05-19T15:05:00.000Z",
    },
  ];

  const edges: EvolutionEdge[] = [
    { from: genesis, to: alpha, mutationType: "bootstrap" },
    { from: alpha, to: beta, mutationType: "mutate" },
    { from: beta, to: champion, mutationType: "crossover" },
    { from: champion, to: proposalA, mutationType: "mutate" },
    { from: champion, to: proposalB, mutationType: "mutate" },
  ];

  return {
    nodes,
    edges,
    activeHash: champion,
    championHash: champion,
  };
}

export function buildEvolutionGraph(
  api: EvolutionGraph | null,
  evolutionState: EvolutionState,
): EvolutionGraph {
  const storeGraph = fromStore(evolutionState);
  const merged = mergeGraphs(api, storeGraph);
  return merged.nodes.length > 0 ? merged : seedDemoGraph();
}

export type MutationType = "crossover" | "mutate" | "bootstrap";

export type DnaNodeStatus =
  | "champion"
  | "active"
  | "archived"
  | "proposed"
  | "rejected";

export interface EvolutionNode {
  id: string;
  hash: string;
  fitness: number;
  generation: number;
  status: DnaNodeStatus;
  promptId: string;
  version: string;
  reasoning: string;
  parentIds: string[];
  mutationDepth?: string;
  createdAt?: string | null;
  contentDigest?: string | null;
}

export interface EvolutionEdge {
  from: string;
  to: string;
  mutationType: MutationType;
}

export interface EvolutionGraph {
  nodes: EvolutionNode[];
  edges: EvolutionEdge[];
  activeHash: string | null;
  championHash: string | null;
}

export interface ApiEvolutionTreeResponse {
  active_hash?: string;
  champion?: ApiDnaNode;
  nodes?: ApiDnaNode[];
  edges?: ApiDnaEdge[];
  pending_mutations?: ApiPendingMutation[];
}

export interface ApiDnaNode {
  hash: string;
  prompt_id?: string;
  version?: string;
  fitness_score?: number;
  generation?: number;
  parent_ids?: string[];
  mutation_rate?: number;
  lineage_hash?: string;
  created_at?: string;
  status?: string;
  mutation_depth?: string;
  content_digest?: string;
}

export interface ApiDnaEdge {
  from_hash: string;
  to_hash: string;
  mutation_type?: string;
}

export interface ApiPendingMutation {
  proposal_id?: string;
  dna_hash: string;
  status?: string;
  fitness_score?: number;
}

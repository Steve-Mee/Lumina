import { useCallback, useEffect, useRef, useState } from "react";

import { buildEvolutionGraph, seedDemoGraph } from "@/lib/buildEvolutionGraph";
import { fetchEvolutionTree } from "@/lib/evolutionTreeClient";
import type { EvolutionGraph } from "@/lib/evolutionTreeTypes";
import { selectEvolutionState, useCoreStore } from "@/store/coreStore";

const POLL_INTERVAL_MS = 5_000;

export function useEvolutionTree() {
  const evolutionState = useCoreStore(selectEvolutionState);
  const [graph, setGraph] = useState<EvolutionGraph>(() => seedDemoGraph());
  const [newNodeIds, setNewNodeIds] = useState<string[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const previousNodeIdsRef = useRef<Set<string>>(new Set());
  const isFirstLoadRef = useRef(true);

  const applyGraph = useCallback((nextGraph: EvolutionGraph) => {
    const nextIds = new Set(nextGraph.nodes.map((node) => node.id));
    const freshIds: string[] = [];

    if (!isFirstLoadRef.current) {
      for (const id of nextIds) {
        if (!previousNodeIdsRef.current.has(id)) {
          freshIds.push(id);
        }
      }
    }

    previousNodeIdsRef.current = nextIds;
    isFirstLoadRef.current = false;
    setGraph(nextGraph);
    if (freshIds.length > 0) {
      setNewNodeIds(freshIds);
    }
  }, []);

  const refresh = useCallback(async () => {
    try {
      const apiGraph = await fetchEvolutionTree();
      const merged = buildEvolutionGraph(apiGraph, evolutionState);
      applyGraph(merged);
      setError(null);
    } catch {
      setError("Failed to load evolution tree");
    } finally {
      setLoading(false);
    }
  }, [applyGraph, evolutionState]);

  useEffect(() => {
    void refresh();
    const timer = setInterval(() => {
      void refresh();
    }, POLL_INTERVAL_MS);
    return () => clearInterval(timer);
  }, [refresh]);

  useEffect(() => {
    const merged = buildEvolutionGraph(null, evolutionState);
    applyGraph(merged.nodes.length > 0 ? merged : seedDemoGraph());
  }, [evolutionState, applyGraph]);

  const clearNewNodes = useCallback(() => {
    setNewNodeIds([]);
  }, []);

  return {
    graph,
    newNodeIds,
    loading,
    error,
    clearNewNodes,
    refresh,
  };
}

declare module "d3-force-3d" {
  export interface SimulationNode {
    index?: number;
    x?: number;
    y?: number;
    z?: number;
    vx?: number;
    vy?: number;
    vz?: number;
    fx?: number | null;
    fy?: number | null;
    fz?: number | null;
  }

  export interface SimulationLink<T extends SimulationNode> {
    source: T | string | number;
    target: T | string | number;
  }

  export interface ForceSimulation<T extends SimulationNode> {
    force(name: string, force?: unknown): this;
    tick(): this;
    stop(): this;
    alpha(): number;
    alpha(value: number): this;
    alphaDecay(value: number): this;
  }

  export function forceSimulation<T extends SimulationNode>(
    nodes?: T[],
    numDimensions?: number,
  ): ForceSimulation<T>;

  export function forceLink<T extends SimulationNode>(
    links?: SimulationLink<T>[],
  ): {
    id(
      accessor: (node: T, index: number, nodes: T[]) => string | number,
    ): unknown;
    distance(distance: number): unknown;
    strength(strength: number): unknown;
  };

  export function forceManyBody(): {
    strength(strength: number): unknown;
  };

  export function forceCenter(
    x?: number,
    y?: number,
    z?: number,
  ): unknown;

  export function forceCollide<T extends SimulationNode>(): {
    radius(accessor: (node: T, index: number, nodes: T[]) => number): unknown;
  };
}

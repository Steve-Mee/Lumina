/** Re-export facade — import from @/lib/birthPhaseModel for backward compatibility. */

export * from "@/lib/birth/birthMilestones";
export * from "@/lib/birth/birthStatusPredicates";
export * from "@/lib/birth/birthProgressExtract";
export * from "@/lib/birth/birthSessionHud";
export * from "@/lib/birth/birthStageScorecard";
export * from "@/lib/birth/birthActiveProgress";
export { normalizeToken, parseProgressTimestamp } from "@/lib/birth/birthModelUtils";

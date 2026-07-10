"""One-shot split birthPhaseModel.ts into lib/birth/* modules."""

from __future__ import annotations

from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "tauri-app" / "src" / "lib" / "birthPhaseModel.ts"
OUT_DIR = ROOT / "tauri-app" / "src" / "lib" / "birth"

UTILS_HEADER = '''import type { BirthProgressPayload } from "@/lib/birthClient";

export function normalizeToken(value: unknown): string {
  return String(value ?? "")
    .trim()
    .toLowerCase();
}

export function parseProgressTimestamp(progress: BirthProgressPayload | undefined): number | null {
  const raw = progress?.timestamp;
  if (!raw) return null;
  const ms = Date.parse(raw);
  return Number.isFinite(ms) ? ms : null;
}
'''

ACTIVE_HEADER = '''import type { BirthProgressPayload } from "@/lib/birthClient";

import { normalizeToken } from "@/lib/birth/birthModelUtils";

export const BIRTH_ACTIVE_PROGRESS_STAGES = new Set([
  "detected",
  "loading_data",
  "training_running",
  "pipeline_boot",
  "historical_loaded",
  "synthetic_top_up",
  "parallel_simulation",
  "ppo_training",
  "curriculum_research",
  "curriculum_learning",
  "data_expansion",
]);

export const BIRTH_ACTIVE_PROGRESS_PHASES = new Set([
  "detected",
  "loading_history",
  "enriching_news",
  "enriching_regimes",
  "train_holdout_split",
  "holdout_preflight",
  "holdout_preflight_expansion",
  "policy_init",
  "ticks_ready",
  "curriculum_stage",
  "curriculum_learning",
  "curriculum_research",
  "data_expansion",
  "parallel_simulation",
  "ppo_training",
  "ppo_polish",
  "oos_evaluation",
]);

export const BIRTH_TERMINAL_PROGRESS_STAGES = new Set([
  "completed",
  "failed",
  "interrupted",
  "stage_stalled",
  "practice_completed",
]);
'''

FACADE_HEADER = '''/** Re-export facade — import from @/lib/birthPhaseModel for backward compatibility. */

export * from "@/lib/birth/birthMilestones";
export * from "@/lib/birth/birthStatusPredicates";
export * from "@/lib/birth/birthProgressExtract";
export * from "@/lib/birth/birthSessionHud";
export * from "@/lib/birth/birthStageScorecard";
export * from "@/lib/birth/birthActiveProgress";
export { normalizeToken, parseProgressTimestamp } from "@/lib/birth/birthModelUtils";
'''


def slice_lines(lines: list[str], start: int, end: int) -> list[str]:
    return lines[start - 1 : end]


def main() -> None:
    lines = SRC.read_text(encoding="utf-8").splitlines()
    OUT_DIR.mkdir(parents=True, exist_ok=True)

    (OUT_DIR / "birthModelUtils.ts").write_text(UTILS_HEADER, encoding="utf-8")

    active_body = slice_lines(lines, 730, 741)
    active_body[0] = "export function isBirthProgressPayloadActive("
    active_file = ACTIVE_HEADER + "\n" + "\n".join(active_body) + "\n"
    (OUT_DIR / "birthActiveProgress.ts").write_text(active_file, encoding="utf-8")

    progress_lines = slice_lines(lines, 452, 482) + ["", ""] + slice_lines(lines, 484, 504) + ["", ""] + slice_lines(lines, 1265, 1276)
    progress_file = (
        'import type { BirthProgressPayload, BirthStatusPayload } from "@/lib/birthClient";\n\n'
        + "\n".join(progress_lines)
        + "\n"
    )
    (OUT_DIR / "birthProgressExtract.ts").write_text(progress_file, encoding="utf-8")

    milestone_lines = slice_lines(lines, 1, 285)
    milestone_file = (
        'import type { BirthProgressPayload, BirthStatusPayload } from "@/lib/birthClient";\n\n'
        + 'import { isBirthCertificateFailed } from "@/lib/birth/birthStatusPredicates";\n'
        + 'import { normalizeToken } from "@/lib/birth/birthModelUtils";\n\n'
        + "\n".join(milestone_lines[1:])  # skip duplicate import
        + "\n"
    )
    (OUT_DIR / "birthMilestones.ts").write_text(milestone_file, encoding="utf-8")

    predicate_lines = slice_lines(lines, 287, 450)
    predicate_file = (
        'import type { BirthProgressPayload, BirthStatusPayload } from "@/lib/birthClient";\n\n'
        + 'import {\n'
        + "  BIRTH_ACTIVE_PROGRESS_PHASES,\n"
        + "  BIRTH_ACTIVE_PROGRESS_STAGES,\n"
        + '} from "@/lib/birth/birthActiveProgress";\n'
        + 'import { normalizeToken } from "@/lib/birth/birthModelUtils";\n\n'
        + "\n".join(predicate_lines[13:])  # skip const sets already in active module
        + "\n"
    )
    (OUT_DIR / "birthStatusPredicates.ts").write_text(predicate_file, encoding="utf-8")

    session_lines = (
        slice_lines(lines, 651, 676)
        + slice_lines(lines, 677, 728)
        + ["", "function resolveSessionSubPhaseLabel(progress: BirthProgressPayload): string {"]
        + slice_lines(lines, 714, 728)[1:]  # body already included above - fix manually
    )
    # Build session hud manually from known line ranges
    session_content = '''import type { BirthProgressPayload } from "@/lib/birthClient";

import { isBirthProgressPayloadActive } from "@/lib/birth/birthActiveProgress";
import { normalizeToken, parseProgressTimestamp } from "@/lib/birth/birthModelUtils";
import { extractStageScorecard } from "@/lib/birth/birthStageScorecard";

'''
    session_content += "\n".join(slice_lines(lines, 651, 712)) + "\n\n"
    session_content += "\n".join(slice_lines(lines, 713, 728)) + "\n\n"
    session_content += "\n".join(slice_lines(lines, 743, 766)) + "\n"
    (OUT_DIR / "birthSessionHud.ts").write_text(session_content, encoding="utf-8")

    scorecard_content = '''import type { BirthProgressPayload } from "@/lib/birthClient";

import { normalizeToken, parseProgressTimestamp } from "@/lib/birth/birthModelUtils";
import { extractSimProgress } from "@/lib/birth/birthProgressExtract";

'''
    scorecard_content += "\n".join(slice_lines(lines, 506, 641)) + "\n\n"
    scorecard_content += "\n".join(slice_lines(lines, 768, 948)) + "\n\n"
    scorecard_content += "\n".join(slice_lines(lines, 950, 1263)) + "\n"
    (OUT_DIR / "birthStageScorecard.ts").write_text(scorecard_content, encoding="utf-8")

    SRC.write_text(FACADE_HEADER, encoding="utf-8")
    print("Extracted birth phase model into", OUT_DIR)


if __name__ == "__main__":
    main()
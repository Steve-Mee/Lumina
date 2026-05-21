import { readdirSync, readFileSync, statSync } from "node:fs";
import { dirname, join } from "node:path";
import { fileURLToPath } from "node:url";
import { describe, expect, it } from "vitest";

const componentsRoot = join(dirname(fileURLToPath(import.meta.url)), "../components");

function collectTsxFiles(dir: string): string[] {
  const entries = readdirSync(dir);
  const files: string[] = [];
  for (const entry of entries) {
    const full = join(dir, entry);
    const stat = statSync(full);
    if (stat.isDirectory()) {
      files.push(...collectTsxFiles(full));
    } else if (entry.endsWith(".tsx")) {
      files.push(full);
    }
  }
  return files;
}

describe("distress grammar sweep", () => {
  it("components do not use flat amber utility alert boxes", () => {
    const offenders: string[] = [];
    for (const file of collectTsxFiles(componentsRoot)) {
      const source = readFileSync(file, "utf8");
      if (source.includes("border-amber-500/") || source.includes("bg-amber-950/")) {
        offenders.push(file.replace(componentsRoot + "\\", "").replace(componentsRoot + "/", ""));
      }
    }
    expect(offenders).toEqual([]);
  });
});

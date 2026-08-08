import { describe, expect, it } from "vitest";

import {
  resolveBooleanConditionTone,
  resolveConditionTone,
} from "@/lib/conditionTone";

describe("conditionTone", () => {
  it("higher-is-better: met / approaching / critical", () => {
    expect(
      resolveConditionTone({ value: 0.4, target: 0.35, direction: "higher" }),
    ).toBe("ok");
    expect(
      resolveConditionTone({
        value: 0.32,
        target: 0.35,
        direction: "higher",
        improving: true,
      }),
    ).toBe("warn");
    expect(
      resolveConditionTone({
        value: 0.1,
        target: 0.35,
        direction: "higher",
        improving: false,
        criticalGap: 0.08,
      }),
    ).toBe("danger");
  });

  it("lower-is-better: hold cap style", () => {
    expect(
      resolveConditionTone({ value: 0.5, max: 0.7, direction: "lower" }),
    ).toBe("ok");
    expect(
      resolveConditionTone({ value: 0.78, max: 0.7, direction: "lower" }),
    ).toBe("warn");
    expect(
      resolveConditionTone({
        value: 0.95,
        max: 0.7,
        direction: "lower",
        criticalGap: 0.15,
      }),
    ).toBe("danger");
  });

  it("band: stage-2 flat 30–70%", () => {
    expect(
      resolveConditionTone({
        value: 0.55,
        min: 0.3,
        max: 0.7,
        direction: "band",
      }),
    ).toBe("ok");
    expect(
      resolveConditionTone({
        value: 0.78,
        min: 0.3,
        max: 0.7,
        direction: "band",
        criticalGap: 0.15,
      }),
    ).toBe("warn");
    expect(
      resolveConditionTone({
        value: 0.95,
        min: 0.3,
        max: 0.7,
        direction: "band",
        criticalGap: 0.15,
      }),
    ).toBe("danger");
  });

  it("boolean gates", () => {
    expect(resolveBooleanConditionTone(true)).toBe("ok");
    expect(resolveBooleanConditionTone(false, { improving: true })).toBe("warn");
    expect(resolveBooleanConditionTone(false)).toBe("danger");
    expect(resolveBooleanConditionTone(null)).toBe("default");
  });
});

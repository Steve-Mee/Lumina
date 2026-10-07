import { describe, expect, it } from "vitest";

import { DEMO_HELP, REAL_HELP, validateAccountPair } from "@/lib/ntAccountNames";

describe("ntAccountNames", () => {
  it("tells the operator exactly which Control Center row to copy", () => {
    expect(DEMO_HELP).toMatch(/Control Center/);
    expect(DEMO_HELP).toMatch(/DEMO5042070/);
    expect(DEMO_HELP).toMatch(/AccountName/);
    expect(REAL_HELP).toMatch(/RealAccountName/);
    expect(REAL_HELP).toMatch(/Control Center/);
    expect(REAL_HELP).toMatch(/demo-rekening/);
  });

  it("accepts a paper demo and a distinct live name", () => {
    const pair = validateAccountPair(" DEMO5042070 ", "APEX12345");
    expect(pair.ok).toBe(true);
    if (pair.ok) {
      expect(pair.demo).toBe("DEMO5042070");
      expect(pair.real).toBe("APEX12345");
    }
  });

  it("refuses an empty real name, a paper real name, and the same name twice", () => {
    expect(validateAccountPair("DEMO5042070", "").ok).toBe(false);
    expect(validateAccountPair("DEMO5042070", "Sim101").ok).toBe(false);
    expect(validateAccountPair("DEMO5042070", "demo5042070").ok).toBe(false);
    expect(validateAccountPair("LiveAcct", "APEX12345").ok).toBe(false);
    expect(validateAccountPair("DEMO 504", "APEX12345").ok).toBe(false);
  });
});

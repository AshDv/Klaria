import { describe, expect, it } from "vitest";

import { instant, parisDate, parisDateTime, parisDayKey, parisTime } from "./dateTime";

describe("dateTime", () => {
  it("conserve une instance Date", () => {
    const value = new Date("2026-01-15T10:00:00Z");
    expect(instant(value)).toBe(value);
  });

  it("interprète une date sans zone comme UTC", () => {
    expect(instant("2026-01-15T10:00:00").toISOString()).toBe("2026-01-15T10:00:00.000Z");
  });

  it("respecte une zone explicitement fournie", () => {
    expect(instant("2026-01-15T11:00:00+01:00").toISOString()).toBe("2026-01-15T10:00:00.000Z");
  });

  it("formate en heure de Paris hiver comme été", () => {
    expect(parisTime("2026-01-15T10:00:00Z")).toMatch(/11:00/);
    expect(parisTime("2026-07-15T10:00:00Z")).toMatch(/12:00/);
  });

  it("calcule la clé du jour parisien autour de minuit", () => {
    expect(parisDayKey("2026-01-15T23:30:00Z")).toBe("2026-01-16");
  });

  it("expose des formats de date lisibles", () => {
    expect(parisDate("2026-01-15T10:00:00Z", { year: "numeric" })).toContain("2026");
    expect(parisDateTime("2026-01-15T10:00:00Z")).toContain("2026");
  });
});

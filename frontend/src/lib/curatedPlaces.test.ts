import { describe, it, expect } from "vitest";
import { CURATED_RECREATION_AREA_IDS } from "./curatedPlaces";

describe("CURATED_RECREATION_AREA_IDS", () => {
  it("has a manageable, non-empty shortlist (10-20 entries)", () => {
    expect(CURATED_RECREATION_AREA_IDS.length).toBeGreaterThanOrEqual(10);
    expect(CURATED_RECREATION_AREA_IDS.length).toBeLessThanOrEqual(20);
  });

  it("has no duplicate ids", () => {
    expect(new Set(CURATED_RECREATION_AREA_IDS).size).toBe(CURATED_RECREATION_AREA_IDS.length);
  });

  it("only contains positive integer ids", () => {
    for (const id of CURATED_RECREATION_AREA_IDS) {
      expect(Number.isInteger(id)).toBe(true);
      expect(id).toBeGreaterThan(0);
    }
  });
});

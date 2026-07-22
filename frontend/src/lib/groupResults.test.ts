import { describe, it, expect } from "vitest";
import { groupResults, hasGroupableResults } from "./groupResults";
import type { ScanResult } from "../types";

function mk(overrides: Partial<ScanResult>): ScanResult {
  return {
    id: 1, scan_run_id: 1, scan_id: 1, campsite_id: "1",
    facility_id: null, facility_name: "F", recreation_area_id: null, recreation_area: null,
    site_name: "S", campsite_type: "TENT",
    booking_date: "2026-07-01", booking_end_date: "2026-07-03",
    booking_url: "https://x", first_seen_at: "2026-06-30T10:00:00Z",
    last_seen_at: "2026-06-30T10:00:00Z", is_available: true, cart_added: false, notified: false,
    ...overrides,
  };
}

describe("groupResults", () => {
  it("nests results under their recreation area and campground", () => {
    const rows = [
      mk({ id: 1, facility_id: "232447", facility_name: "Upper Pines", recreation_area_id: "2991", recreation_area: "Yosemite" }),
      mk({ id: 2, facility_id: "232447", facility_name: "Upper Pines", recreation_area_id: "2991", recreation_area: "Yosemite" }),
      mk({ id: 3, facility_id: "232999", facility_name: "Lower Pines", recreation_area_id: "2991", recreation_area: "Yosemite" }),
    ];
    const { areas, other } = groupResults(rows);
    expect(other).toHaveLength(0);
    expect(areas).toHaveLength(1);
    expect(areas[0].recreationAreaName).toBe("Yosemite");
    expect(areas[0].campgrounds).toHaveLength(2);
    const upperPines = areas[0].campgrounds.find((c) => c.facilityId === "232447")!;
    expect(upperPines.results.map((r) => r.id)).toEqual([1, 2]);
  });

  it("puts rows with no facility_id or recreation_area_id into the Other bucket", () => {
    const rows = [
      mk({ id: 1, facility_id: null, recreation_area_id: null }),
      mk({ id: 2, facility_id: "232447", facility_name: "Upper Pines", recreation_area_id: "2991", recreation_area: "Yosemite" }),
    ];
    const { areas, other } = groupResults(rows);
    expect(other.map((r) => r.id)).toEqual([1]);
    expect(areas).toHaveLength(1);
  });

  it("orders areas and campgrounds by most recent last_seen_at first", () => {
    const rows = [
      mk({ id: 1, facility_id: "A", facility_name: "A camp", recreation_area_id: "1", recreation_area: "Older Area", last_seen_at: "2026-06-01T00:00:00Z" }),
      mk({ id: 2, facility_id: "B", facility_name: "B camp", recreation_area_id: "2", recreation_area: "Newer Area", last_seen_at: "2026-06-05T00:00:00Z" }),
    ];
    const { areas } = groupResults(rows);
    expect(areas.map((a) => a.recreationAreaName)).toEqual(["Newer Area", "Older Area"]);
  });

  it("returns an empty areas list and everything in Other when nothing is groupable", () => {
    const rows = [mk({ id: 1 }), mk({ id: 2 })];
    const { areas, other } = groupResults(rows);
    expect(areas).toHaveLength(0);
    expect(other).toHaveLength(2);
  });
});

describe("hasGroupableResults", () => {
  it("is true when at least one row has a facility_id and recreation_area_id", () => {
    expect(hasGroupableResults([mk({ facility_id: "1", recreation_area_id: "1" })])).toBe(true);
  });

  it("is false when no row has both identifiers", () => {
    expect(hasGroupableResults([mk({ facility_id: null, recreation_area_id: null })])).toBe(false);
  });
});

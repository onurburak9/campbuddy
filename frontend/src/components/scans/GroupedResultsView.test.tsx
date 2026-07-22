import { describe, it, expect } from "vitest";
import { render, screen } from "@testing-library/react";
import { GroupedResultsView } from "./GroupedResultsView";
import type { ScanResult } from "../../types";

function mk(overrides: Partial<ScanResult>): ScanResult {
  return {
    id: 1, scan_run_id: 1, scan_id: 1, campsite_id: "1",
    facility_id: null, facility_name: "F", recreation_area_id: null, recreation_area: null,
    site_name: "Site 1", campsite_type: "TENT",
    booking_date: "2026-07-01", booking_end_date: "2026-07-03",
    booking_url: "https://x", first_seen_at: "2026-06-30T10:00:00Z",
    last_seen_at: "2026-06-30T10:00:00Z", is_available: true, cart_added: false, notified: false,
    ...overrides,
  };
}

describe("GroupedResultsView", () => {
  it("renders an area containing a campground containing its campsite rows", () => {
    const rows = [
      mk({ id: 1, site_name: "Site 1", facility_id: "232447", facility_name: "Upper Pines", recreation_area_id: "2991", recreation_area: "Yosemite" }),
    ];
    render(<GroupedResultsView results={rows} />);
    expect(screen.getByText("Yosemite")).toBeInTheDocument();
    expect(screen.getAllByText("Upper Pines").length).toBeGreaterThan(0);
    expect(screen.getByText("Site 1")).toBeInTheDocument();
  });

  it("appends an Other section for ungroupable rows after all areas", () => {
    const rows = [
      mk({ id: 1, site_name: "Grouped Site", facility_id: "232447", facility_name: "Upper Pines", recreation_area_id: "2991", recreation_area: "Yosemite" }),
      mk({ id: 2, site_name: "Legacy Site", facility_id: null, recreation_area_id: null }),
    ];
    render(<GroupedResultsView results={rows} />);
    expect(screen.getByText("Other")).toBeInTheDocument();
    expect(screen.getByText("Legacy Site")).toBeInTheDocument();
  });

  it("omits the Other section entirely when every row is groupable", () => {
    const rows = [
      mk({ id: 1, facility_id: "232447", facility_name: "Upper Pines", recreation_area_id: "2991", recreation_area: "Yosemite" }),
    ];
    render(<GroupedResultsView results={rows} />);
    expect(screen.queryByText("Other")).not.toBeInTheDocument();
  });

  it("auto-expands the sole area and sole campground", () => {
    const rows = [
      mk({ id: 1, site_name: "Only Site", facility_id: "232447", facility_name: "Upper Pines", recreation_area_id: "2991", recreation_area: "Yosemite" }),
    ];
    render(<GroupedResultsView results={rows} />);
    expect(screen.getByText("Only Site")).toBeVisible();
  });

  it("starts collapsed when there are multiple areas", () => {
    const rows = [
      mk({ id: 1, site_name: "Site A", facility_id: "A", facility_name: "Camp A", recreation_area_id: "1", recreation_area: "Area One" }),
      mk({ id: 2, site_name: "Site B", facility_id: "B", facility_name: "Camp B", recreation_area_id: "2", recreation_area: "Area Two" }),
    ];
    render(<GroupedResultsView results={rows} />);
    expect(screen.getByText("Site A")).not.toBeVisible();
    expect(screen.getByText("Site B")).not.toBeVisible();
  });

  it("shows aggregated available/gone counts on the area header", () => {
    const rows = [
      mk({ id: 1, facility_id: "A", facility_name: "Camp A", recreation_area_id: "1", recreation_area: "Area One", is_available: true }),
      mk({ id: 2, facility_id: "A", facility_name: "Camp A", recreation_area_id: "1", recreation_area: "Area One", is_available: false }),
    ];
    render(<GroupedResultsView results={rows} />);
    expect(screen.getAllByText("1 available").length).toBeGreaterThan(0);
    expect(screen.getAllByText("1 gone").length).toBeGreaterThan(0);
  });
});

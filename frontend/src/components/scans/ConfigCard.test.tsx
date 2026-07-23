import type { ReactNode } from "react";
import { describe, it, expect, vi } from "vitest";
import { render, screen, waitFor } from "@testing-library/react";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { ConfigCard } from "./ConfigCard";
import { search } from "../../api/search";
import type { Scan } from "../../types";

vi.mock("../../api/search", () => ({
  search: {
    resolveRecreationAreas: vi.fn().mockResolvedValue([]),
    resolveCampgrounds: vi.fn().mockResolvedValue([]),
    resolveCampsites: vi.fn().mockResolvedValue([]),
  },
}));

function wrap(ui: ReactNode) {
  const qc = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  return render(<QueryClientProvider client={qc}>{ui}</QueryClientProvider>);
}

const scan: Scan = {
  id: 5, user_id: 1, provider: "RecreationDotGov", name: "Trip", status: "active",
  polling_interval: 600, rec_area_ids: null, campground_ids: [10357105, 10357111],
  campsite_ids: null, search_windows: [{ start_date: "2026-07-03", end_date: "2026-07-05" }],
  nights: 2, days_of_week: [4, 5], weekends_only: false, notify_via_email: true,
  notify_via_telegram: false, notify_on_new_only: true, created_at: "2026-06-01T00:00:00Z",
};

const scanWithAllIds: Scan = {
  ...scan,
  rec_area_ids: [2931],
  campground_ids: [10357105],
  campsite_ids: [42],
};

describe("ConfigCard", () => {
  it("renders the scan configuration", () => {
    wrap(<ConfigCard scan={scan} />);
    expect(screen.getByText("Configuration")).toBeInTheDocument();
    expect(screen.getByText("RecreationDotGov")).toBeInTheDocument();
    expect(screen.getByRole("link", { name: "#10357105" })).toHaveAttribute(
      "href",
      "https://www.recreation.gov/camping/campgrounds/10357105",
    );
    expect(screen.getByRole("link", { name: "#10357111" })).toHaveAttribute(
      "href",
      "https://www.recreation.gov/camping/campgrounds/10357111",
    );
    expect(screen.getByText(/10 min/)).toBeInTheDocument();     // polling
    expect(screen.getByText(/Email/)).toBeInTheDocument();      // notifications
    expect(screen.getByText("Fri")).toBeInTheDocument();        // day-of-week chip
  });

  it("renders em-dash for null/empty ID lists", () => {
    wrap(<ConfigCard scan={scan} />);
    // rec_area_ids and campsite_ids are null in the default fixture — expect "—" placeholders
    const dashes = screen.getAllByText("—");
    expect(dashes.length).toBeGreaterThanOrEqual(2);
  });

  it("renders clickable links for rec_area_ids, campground_ids, and campsite_ids, falling back to #<id> when unresolved", () => {
    wrap(<ConfigCard scan={scanWithAllIds} />);
    expect(screen.getByRole("link", { name: "#2931" })).toHaveAttribute(
      "href",
      "https://www.recreation.gov/gateways/2931",
    );
    expect(screen.getByRole("link", { name: "#10357105" })).toHaveAttribute(
      "href",
      "https://www.recreation.gov/camping/campgrounds/10357105",
    );
    expect(screen.getByRole("link", { name: "#42" })).toHaveAttribute(
      "href",
      "https://www.recreation.gov/camping/campsites/42",
    );
  });

  it("renders resolved names as link text once the resolve API returns them, keeping the ID as a tooltip", async () => {
    vi.mocked(search.resolveRecreationAreas).mockResolvedValueOnce([
      { id: 2931, name: "Yosemite National Park", state: "CA", type: "Park" },
    ]);
    vi.mocked(search.resolveCampgrounds).mockResolvedValueOnce([
      { id: 10357105, name: "Upper Pines", recreation_area: "Yosemite National Park", recreation_area_id: 2931 },
    ]);
    vi.mocked(search.resolveCampsites).mockResolvedValueOnce([
      { id: 42, name: "Site 042", loop: "A", campground_id: 10357105 },
    ]);

    wrap(<ConfigCard scan={scanWithAllIds} />);

    const areaLink = await waitFor(() => screen.getByRole("link", { name: "Yosemite National Park" }));
    expect(areaLink).toHaveAttribute("href", "https://www.recreation.gov/gateways/2931");
    expect(areaLink).toHaveAttribute("title", "ID 2931");

    const campgroundLink = await waitFor(() => screen.getByRole("link", { name: "Upper Pines" }));
    expect(campgroundLink).toHaveAttribute("href", "https://www.recreation.gov/camping/campgrounds/10357105");
    expect(campgroundLink).toHaveAttribute("title", "ID 10357105");

    const campsiteLink = await waitFor(() => screen.getByRole("link", { name: "Site 042" }));
    expect(campsiteLink).toHaveAttribute("href", "https://www.recreation.gov/camping/campsites/42");
    expect(campsiteLink).toHaveAttribute("title", "ID 42");

    // Raw IDs should no longer appear as link text once names are resolved.
    expect(screen.queryByRole("link", { name: "#2931" })).not.toBeInTheDocument();
  });

  it("renders a target-count summary line", () => {
    wrap(<ConfigCard scan={scan} />);
    expect(screen.getByText("Monitoring 2 campgrounds")).toBeInTheDocument();
  });

  it("joins multiple target categories in the summary", () => {
    wrap(<ConfigCard scan={scanWithAllIds} />);
    expect(
      screen.getByText("Monitoring 1 campground across 1 recreation area across 1 campsite"),
    ).toBeInTheDocument();
  });
});

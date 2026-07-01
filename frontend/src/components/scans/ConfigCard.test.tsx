import { describe, it, expect } from "vitest";
import { render, screen } from "@testing-library/react";
import { ConfigCard } from "./ConfigCard";
import type { Scan } from "../../types";

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
    render(<ConfigCard scan={scan} />);
    expect(screen.getByText("Configuration")).toBeInTheDocument();
    expect(screen.getByText("RecreationDotGov")).toBeInTheDocument();
    expect(screen.getByRole("link", { name: "10357105" })).toHaveAttribute(
      "href",
      "https://www.recreation.gov/camping/campgrounds/10357105",
    );
    expect(screen.getByRole("link", { name: "10357111" })).toHaveAttribute(
      "href",
      "https://www.recreation.gov/camping/campgrounds/10357111",
    );
    expect(screen.getByText(/10 min/)).toBeInTheDocument();     // polling
    expect(screen.getByText(/Email/)).toBeInTheDocument();      // notifications
    expect(screen.getByText("Fri")).toBeInTheDocument();        // day-of-week chip
  });

  it("renders em-dash for null/empty ID lists", () => {
    render(<ConfigCard scan={scan} />);
    // rec_area_ids and campsite_ids are null in the default fixture — expect "—" placeholders
    const dashes = screen.getAllByText("—");
    expect(dashes.length).toBeGreaterThanOrEqual(2);
  });

  it("renders clickable links for rec_area_ids, campground_ids, and campsite_ids", () => {
    render(<ConfigCard scan={scanWithAllIds} />);
    expect(screen.getByRole("link", { name: "2931" })).toHaveAttribute(
      "href",
      "https://www.recreation.gov/gateways/2931",
    );
    expect(screen.getByRole("link", { name: "10357105" })).toHaveAttribute(
      "href",
      "https://www.recreation.gov/camping/campgrounds/10357105",
    );
    expect(screen.getByRole("link", { name: "42" })).toHaveAttribute(
      "href",
      "https://www.recreation.gov/camping/campsites/42",
    );
  });
});

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

describe("ConfigCard", () => {
  it("renders the scan configuration", () => {
    render(<ConfigCard scan={scan} />);
    expect(screen.getByText("Configuration")).toBeInTheDocument();
    expect(screen.getByText("RecreationDotGov")).toBeInTheDocument();
    expect(screen.getByText(/10357105, 10357111/)).toBeInTheDocument();
    expect(screen.getByText(/10 min/)).toBeInTheDocument();     // polling
    expect(screen.getByText(/Email/)).toBeInTheDocument();      // notifications
    expect(screen.getByText("Fri")).toBeInTheDocument();        // day-of-week chip
  });
});

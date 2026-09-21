import { describe, it, expect, vi } from "vitest";
import { render, screen } from "@testing-library/react";
import { ScanListItem } from "./ScanListItem";
import type { Scan } from "../../types";

const scan: Scan = {
  id: 7, user_id: 1, provider: "RecreationDotGov", name: "October trip", status: "active",
  polling_interval: 1800, rec_area_ids: [2991], campground_ids: null, campsite_ids: null,
  search_windows: [{ start_date: "2026-10-01", end_date: "2026-11-01", expired: false }],
  nights: 2, days_of_week: null, weekends_only: true, notify_via_email: true,
  notify_via_telegram: false, notify_on_new_only: true, created_at: "2026-09-20T00:00:00Z",
};

describe("ScanListItem", () => {
  it("summarises the stay rather than showing the raw range bound", () => {
    render(<ScanListItem scan={scan} selected={false} onClick={vi.fn()} />);

    const item = screen.getByRole("button");
    expect(item).toHaveTextContent("2 nights");
    expect(item).toHaveTextContent("weekends");
    expect(item).toHaveTextContent("Oct 31");
    // Nov 1 is the exclusive bound, never a night the user could book.
    expect(item).not.toHaveTextContent("Nov");
  });

  it("shows a check-out date when the window is exactly the stay", () => {
    const weekend: Scan = {
      ...scan,
      search_windows: [{ start_date: "2026-09-25", end_date: "2026-09-27", expired: false }],
      weekends_only: false,
    };
    render(<ScanListItem scan={weekend} selected={false} onClick={vi.fn()} />);

    expect(screen.getByRole("button")).toHaveTextContent("Sep 27");
  });

  it("renders nothing for the dates when no window is set", () => {
    const noWindows: Scan = { ...scan, search_windows: [] };
    render(<ScanListItem scan={noWindows} selected={false} onClick={vi.fn()} />);

    expect(screen.getByRole("button")).toHaveTextContent("October trip");
    expect(screen.getByRole("button")).not.toHaveTextContent("night");
  });
});

import { describe, it, expect, vi } from "vitest";
import { http, HttpResponse } from "msw";
import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { server } from "../../test/server";
import { ScanDetailHeader } from "./ScanDetailHeader";
import type { Scan } from "../../types/index";

const scan = {
  id: 7, user_id: 1, provider: "RecreationDotGov", name: "Yosemite", status: "active",
  polling_interval: 300, rec_area_ids: [2991], campground_ids: null, campsite_ids: null,
  search_windows: [{ start_date: "2026-07-01", end_date: "2026-07-03" }], nights: 2,
  days_of_week: null, weekends_only: false, notify_via_email: true,
  notify_via_telegram: false, notify_on_new_only: true, created_at: "2026-06-01T00:00:00Z",
} as const satisfies Scan;

const scanWithCampgrounds = {
  id: 7, user_id: 1, provider: "RecreationDotGov", name: "Yosemite", status: "active",
  polling_interval: 600, rec_area_ids: null, campground_ids: [232447], campsite_ids: null,
  search_windows: [{ start_date: "2026-07-01", end_date: "2026-07-03" }], nights: 2,
  days_of_week: null, weekends_only: false, notify_via_email: true,
  notify_via_telegram: false, notify_on_new_only: false, created_at: "2026-06-01T00:00:00Z",
} as const satisfies Scan;

function wrap(ui: React.ReactNode) {
  const qc = new QueryClient({ defaultOptions: { mutations: { retry: false } } });
  return render(<QueryClientProvider client={qc}>{ui}</QueryClientProvider>);
}

describe("ScanDetailHeader", () => {
  it("pauses an active scan", async () => {
    let paused = false;
    server.use(http.post("/api/v1/scans/7/pause", () => {
      paused = true;
      return HttpResponse.json({ ...scan, status: "paused" });
    }));
    wrap(<ScanDetailHeader scan={scan} onDeleted={vi.fn()} onEdit={vi.fn()} />);
    await userEvent.click(screen.getByRole("button", { name: /pause/i }));
    await waitFor(() => expect(paused).toBe(true));
  });

  it("shows scan id, campground ids, polling interval and notifications", () => {
    wrap(<ScanDetailHeader scan={scanWithCampgrounds} onDeleted={vi.fn()} onEdit={vi.fn()} />);
    expect(screen.getByText(/#7/)).toBeInTheDocument();
    expect(screen.getByText(/campgrounds 232447/)).toBeInTheDocument();
    expect(screen.getByText(/10 min/)).toBeInTheDocument();
    expect(screen.getByText(/Email/)).toBeInTheDocument();
  });

  it("deletes after confirm and calls onDeleted", async () => {
    vi.spyOn(window, "confirm").mockReturnValue(true);
    server.use(http.delete("/api/v1/scans/7", () => new HttpResponse(null, { status: 204 })));
    const onDeleted = vi.fn();
    wrap(<ScanDetailHeader scan={scan} onDeleted={onDeleted} onEdit={vi.fn()} />);
    await userEvent.click(screen.getByRole("button", { name: /delete/i }));
    await waitFor(() => expect(onDeleted).toHaveBeenCalled());
  });
});

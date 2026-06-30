import { describe, it, expect, vi } from "vitest";
import { http, HttpResponse } from "msw";
import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { server } from "../../test/server";
import { ScanListPanel } from "./ScanListPanel";

function wrap(ui: React.ReactNode) {
  const qc = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  return render(<QueryClientProvider client={qc}>{ui}</QueryClientProvider>);
}

const scan = {
  id: 7, user_id: 1, provider: "RecreationDotGov", name: "Yosemite", status: "active",
  polling_interval: 300, rec_area_ids: [2991], campground_ids: null, campsite_ids: null,
  search_windows: [{ start_date: "2026-07-01", end_date: "2026-07-03" }], nights: 2,
  days_of_week: null, weekends_only: false, notify_via_email: true,
  notify_via_telegram: false, notify_on_new_only: true, created_at: "2026-06-01T00:00:00Z",
};

describe("ScanListPanel", () => {
  it("renders scans and fires onSelect", async () => {
    server.use(http.get("/api/v1/scans", () => HttpResponse.json([scan])));
    const onSelect = vi.fn();
    wrap(<ScanListPanel selectedScanId={null} onSelect={onSelect} onNewScan={vi.fn()} />);
    await waitFor(() => expect(screen.getByText("Yosemite")).toBeInTheDocument());
    await userEvent.click(screen.getByText("Yosemite"));
    expect(onSelect).toHaveBeenCalledWith(7);
  });

  it("shows empty state when no scans", async () => {
    server.use(http.get("/api/v1/scans", () => HttpResponse.json([])));
    const onNewScan = vi.fn();
    wrap(<ScanListPanel selectedScanId={null} onSelect={vi.fn()} onNewScan={onNewScan} />);
    await waitFor(() => expect(screen.getByText(/no scans yet/i)).toBeInTheDocument());
  });

  it("calls onNewScan from header + button", async () => {
    server.use(http.get("/api/v1/scans", () => HttpResponse.json([scan])));
    const onNewScan = vi.fn();
    wrap(<ScanListPanel selectedScanId={null} onSelect={vi.fn()} onNewScan={onNewScan} />);
    await waitFor(() => screen.getByText("Yosemite"));
    await userEvent.click(screen.getByRole("button", { name: /new scan/i }));
    expect(onNewScan).toHaveBeenCalled();
  });
});

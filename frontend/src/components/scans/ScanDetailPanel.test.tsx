import { describe, it, expect, vi } from "vitest";
import { http, HttpResponse } from "msw";
import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { server } from "../../test/server";

vi.mock("../../contexts/AuthContext", () => ({
  useAuth: () => ({ user: { id: 1, email: "a@b.c", scan_limit: 5, scans_used: 0, has_telegram: true } }),
}));

import { ScanDetailPanel } from "./ScanDetailPanel";
import type { Scan } from "../../types/index";

const scan4: Scan = {
  id: 4, user_id: 1, provider: "RecreationDotGov", name: "Sequioa", status: "active",
  polling_interval: 600, rec_area_ids: [2931], campground_ids: null, campsite_ids: null,
  search_windows: [{ start_date: "2026-07-01", end_date: "2026-07-03" }], nights: 2,
  days_of_week: null, weekends_only: false, notify_via_email: true,
  notify_via_telegram: false, notify_on_new_only: true, created_at: "2026-06-01T00:00:00Z",
};

const scan5: Scan = {
  id: 5, user_id: 1, provider: "RecreationDotGov", name: "Jul Trip", status: "active",
  polling_interval: 600, rec_area_ids: null, campground_ids: [111], campsite_ids: null,
  search_windows: [{ start_date: "2026-07-10", end_date: "2026-07-12" }], nights: 2,
  days_of_week: null, weekends_only: false, notify_via_email: true,
  notify_via_telegram: false, notify_on_new_only: true, created_at: "2026-06-01T00:00:00Z",
};

const emptyStats = { sites_found: 0, in_cart: 0, total_runs: 0, success_rate: 0 };

function wrap(ui: React.ReactNode) {
  const qc = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  return render(<QueryClientProvider client={qc}>{ui}</QueryClientProvider>);
}

describe("ScanDetailPanel", () => {
  it("remounts tab content when switching scans — Settings tab shows new scan name", async () => {
    server.use(
      http.get("/api/v1/scans/4", () => HttpResponse.json(scan4)),
      http.get("/api/v1/scans/5", () => HttpResponse.json(scan5)),
      http.get("/api/v1/scans/4/stats", () => HttpResponse.json(emptyStats)),
      http.get("/api/v1/scans/5/stats", () => HttpResponse.json(emptyStats)),
      http.get("/api/v1/scans/4/runs", () => HttpResponse.json([])),
      http.get("/api/v1/scans/5/runs", () => HttpResponse.json([])),
      http.get("/api/v1/scans/4/results", () => HttpResponse.json([])),
      http.get("/api/v1/scans/5/results", () => HttpResponse.json([])),
    );

    const { rerender } = wrap(
      <ScanDetailPanel scanId={4} onDeleted={vi.fn()} />,
    );

    // Wait for scan 4 header to appear
    await waitFor(() => expect(screen.getByText("Sequioa")).toBeInTheDocument());

    // Click the Settings tab
    await userEvent.click(screen.getByRole("tab", { name: /settings/i }));

    // The Settings form should show "Sequioa" in the name input
    await waitFor(() =>
      expect(screen.getByDisplayValue("Sequioa")).toBeInTheDocument()
    );

    // Switch to scan 5 (keep the same QueryClient so cached data is available)
    const qc = new QueryClient({ defaultOptions: { queries: { retry: false } } });
    rerender(
      <QueryClientProvider client={qc}>
        <ScanDetailPanel scanId={5} onDeleted={vi.fn()} />
      </QueryClientProvider>,
    );

    // Wait for scan 5 header
    await waitFor(() => expect(screen.getByText("Jul Trip")).toBeInTheDocument());

    // The Settings tab should now show "Jul Trip" — NOT "Sequioa"
    await waitFor(() =>
      expect(screen.getByDisplayValue("Jul Trip")).toBeInTheDocument()
    );
    expect(screen.queryByDisplayValue("Sequioa")).toBeNull();
  });
});

import { describe, it, expect } from "vitest";
import { http, HttpResponse } from "msw";
import { render, screen, waitFor } from "@testing-library/react";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { server } from "../../test/server";
import { OverviewTab } from "./OverviewTab";
import type { Scan } from "../../types";

const scan = { id: 7, search_windows: [{ start_date: "2026-07-01", end_date: "2026-07-03" }] } as unknown as Scan;

function wrap(ui: React.ReactNode) {
  const qc = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  return render(<QueryClientProvider client={qc}>{ui}</QueryClientProvider>);
}

describe("OverviewTab", () => {
  it("shows last checked and last new site found", async () => {
    server.use(
      http.get("/api/v1/scans/7/stats", () => HttpResponse.json({ sites_found: 1, in_cart: 0, total_runs: 5, success_rate: 80 })),
      http.get("/api/v1/scans/7/runs", () => HttpResponse.json([{ id: 9, scan_id: 7, started_at: "2026-06-30T11:00:00Z", finished_at: "2026-06-30T11:00:03Z", outcome: "success", sites_found: 1, error_message: null }])),
      http.get("/api/v1/scans/7/results", () => HttpResponse.json([{ id: 3, scan_run_id: 9, scan_id: 7, campsite_id: "A1", facility_name: "F", site_name: "S", campsite_type: "TENT", booking_date: "2026-07-01", booking_end_date: "2026-07-03", booking_url: "x", first_seen_at: "2026-06-30T11:00:00Z", last_seen_at: "2026-06-30T11:00:00Z", is_available: true, cart_added: false, notified: true }])),
    );
    wrap(<OverviewTab scan={scan} />);
    await waitFor(() => expect(screen.getByText(/Last checked/i)).toBeInTheDocument());
    expect(screen.getByText(/Last new site found/i)).toBeInTheDocument();
  });
});

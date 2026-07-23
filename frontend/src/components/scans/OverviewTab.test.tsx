import { describe, it, expect } from "vitest";
import { http, HttpResponse } from "msw";
import { render, screen, waitFor } from "@testing-library/react";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { server } from "../../test/server";
import { OverviewTab } from "./OverviewTab";
import type { Scan } from "../../types";

const scan = { id: 7, search_windows: [{ start_date: "2026-07-01", end_date: "2026-07-03" }] } as unknown as Scan;

// Computed relative to the real clock (rather than hardcoded) so the "in 5 min"
// assertion below stays true no matter when the test suite actually runs.
const NEXT_RUN_AT = new Date(Date.now() + 5 * 60 * 1000).toISOString();

function wrap(ui: React.ReactNode) {
  const qc = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  return render(<QueryClientProvider client={qc}>{ui}</QueryClientProvider>);
}

describe("OverviewTab", () => {
  it("shows last checked and last new site found", async () => {
    server.use(
      http.get("/api/v1/scans/7/stats", () => HttpResponse.json({
        sites_found: 1, in_cart: 0, total_runs: 5, success_rate: 80, hit_rate: 60,
        next_run_at: NEXT_RUN_AT, last_run_duration_seconds: 12,
      })),
      http.get("/api/v1/scans/7/runs", () => HttpResponse.json([{ id: 9, scan_id: 7, started_at: "2026-06-30T11:00:00Z", finished_at: "2026-06-30T11:00:03Z", outcome: "success", sites_found: 1, error_message: null }])),
      http.get("/api/v1/scans/7/results", () => HttpResponse.json([{ id: 3, scan_run_id: 9, scan_id: 7, campsite_id: "A1", facility_name: "F", site_name: "S", campsite_type: "TENT", booking_date: "2026-07-01", booking_end_date: "2026-07-03", booking_url: "x", first_seen_at: "2026-06-30T11:00:00Z", last_seen_at: "2026-06-30T11:00:00Z", is_available: true, cart_added: false, notified: true }])),
    );
    wrap(<OverviewTab scan={scan} />);
    await waitFor(() => expect(screen.getByText(/Last checked/i)).toBeInTheDocument());
    expect(screen.getByText(/Last new site found/i)).toBeInTheDocument();
    expect(screen.getByText("Hit Rate")).toBeInTheDocument();
    // "Hit Rate" tile renders immediately with a 0% fallback and only picks up
    // the real value once the stats query settles — wait for it like the
    // next-run/last-run-duration assertions below do.
    await waitFor(() => expect(screen.getByText("60%")).toBeInTheDocument());
  });

  it("shows next run time and last run duration from stats", async () => {
    server.use(
      http.get("/api/v1/scans/7/stats", () => HttpResponse.json({
        sites_found: 1, in_cart: 0, total_runs: 5, success_rate: 80, hit_rate: 60,
        next_run_at: NEXT_RUN_AT, last_run_duration_seconds: 12,
      })),
      http.get("/api/v1/scans/7/runs", () => HttpResponse.json([])),
      http.get("/api/v1/scans/7/results", () => HttpResponse.json([])),
    );
    wrap(<OverviewTab scan={scan} />);
    expect(screen.getByText(/Next run/i)).toBeInTheDocument();
    expect(screen.getByText(/Last run took/i)).toBeInTheDocument();
    // Wait for the stats fetch to resolve before asserting the derived values,
    // since the "Next run"/"Last run took" labels render immediately with a
    // "—" fallback and only pick up real values once the query settles.
    await waitFor(() => expect(screen.getByText(/in 5 min/)).toBeInTheDocument());
    expect(screen.getByText("12s")).toBeInTheDocument();
  });

  it("shows dashes for next run and last run duration when absent", async () => {
    server.use(
      http.get("/api/v1/scans/7/stats", () => HttpResponse.json({
        sites_found: 0, in_cart: 0, total_runs: 0, success_rate: 0, hit_rate: 0,
        next_run_at: null, last_run_duration_seconds: null,
      })),
      http.get("/api/v1/scans/7/runs", () => HttpResponse.json([])),
      http.get("/api/v1/scans/7/results", () => HttpResponse.json([])),
    );
    wrap(<OverviewTab scan={scan} />);
    await waitFor(() => expect(screen.getByText(/Next run/i)).toBeInTheDocument());
    const nextRunRow = screen.getByText(/Next run/i).closest("span");
    expect(nextRunRow).toHaveTextContent("—");
  });
});

import { describe, it, expect } from "vitest";
import { http, HttpResponse } from "msw";
import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { server } from "../../test/server";
import { RunHistoryTab } from "./RunHistoryTab";

const run = {
  id: 1, scan_id: 7, started_at: "2026-06-24T11:00:00Z", finished_at: "2026-06-24T11:00:08Z",
  outcome: "error", sites_found: 0, error_message: "provider timeout",
};

function wrap(ui: React.ReactNode) {
  const qc = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  return render(<QueryClientProvider client={qc}>{ui}</QueryClientProvider>);
}

describe("RunHistoryTab", () => {
  it("renders a run row with outcome and expandable error", async () => {
    server.use(http.get("/api/v1/scans/7/runs", () => HttpResponse.json([run])));
    wrap(<RunHistoryTab scanId={7} />);
    await waitFor(() => expect(screen.getByText(/error/i)).toBeInTheDocument());
    expect(screen.getByText(/provider timeout/i)).toBeInTheDocument();
  });

  it("expands a run to show its discovered sites", async () => {
    server.use(
      http.get("/api/v1/scans/7/runs", () => HttpResponse.json([
        { id: 9, scan_id: 7, started_at: "2026-06-30T11:00:00Z", finished_at: "2026-06-30T11:00:03Z", outcome: "success", sites_found: 1, error_message: null },
      ])),
      http.get("/api/v1/scans/7/runs/9/results", () => HttpResponse.json([
        { id: 3, scan_run_id: 9, scan_id: 7, campsite_id: "A1", facility_name: "Upper Pines", site_name: "Site 42", campsite_type: "TENT", booking_date: "2026-07-01", booking_end_date: "2026-07-03", booking_url: "https://x", first_seen_at: "2026-06-30T11:00:00Z", cart_added: false, notified: true },
      ])),
    );
    wrap(<RunHistoryTab scanId={7} />);
    await waitFor(() => expect(screen.getByText(/Success/)).toBeInTheDocument());
    await userEvent.click(screen.getByText(/Success/));
    await waitFor(() => expect(screen.getByText(/Site 42/)).toBeInTheDocument());
    expect(screen.getByText(/first discovered in this run/i)).toBeInTheDocument();
  });
});

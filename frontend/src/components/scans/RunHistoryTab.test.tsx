import { describe, it, expect } from "vitest";
import { http, HttpResponse } from "msw";
import { render, screen, waitFor } from "@testing-library/react";
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
});

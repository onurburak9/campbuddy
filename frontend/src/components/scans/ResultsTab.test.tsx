import { describe, it, expect } from "vitest";
import { http, HttpResponse } from "msw";
import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { server } from "../../test/server";
import { ResultsTab } from "./ResultsTab";

const mk = (id: number, facility: string, type: string, site: string) => ({
  id, scan_run_id: 9, scan_id: 7, campsite_id: `C${id}`, facility_name: facility,
  site_name: site, campsite_type: type, booking_date: "2026-07-01",
  booking_end_date: "2026-07-03", booking_url: "https://x", first_seen_at: "2026-06-30T11:00:00Z",
  last_seen_at: "2026-06-30T11:00:00Z", is_available: true,
  cart_added: false, notified: true,
});
const rows = [
  mk(1, "Moraine", "TENT", "Site 42"),
  mk(2, "Sunset", "RV", "Site 7"),
  mk(3, "Moraine", "RV", "Loop A"),
];

function wrap(ui: React.ReactNode) {
  const qc = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  return render(<QueryClientProvider client={qc}>{ui}</QueryClientProvider>);
}

describe("ResultsTab (client-side filtering)", () => {
  it("renders all results, then filters by search and by facility", async () => {
    server.use(http.get("/api/v1/scans/7/results", () => HttpResponse.json(rows)));
    wrap(<ResultsTab scanId={7} />);
    await waitFor(() => expect(screen.getByText("Site 42")).toBeInTheDocument());
    expect(screen.getByText("Site 7")).toBeInTheDocument();

    await userEvent.type(screen.getByPlaceholderText(/search/i), "loop");
    await waitFor(() => expect(screen.getByText("Loop A")).toBeInTheDocument());
    expect(screen.queryByText("Site 42")).not.toBeInTheDocument();

    await userEvent.clear(screen.getByPlaceholderText(/search/i));
    // Facility dropdown → Sunset (locate via its unique "All campgrounds" option)
    const facilitySelect = screen.getByRole("option", { name: "All campgrounds" }).closest("select")!;
    await userEvent.selectOptions(facilitySelect, "Sunset");
    await waitFor(() => expect(screen.getByText("Site 7")).toBeInTheDocument());
    expect(screen.queryByText("Loop A")).not.toBeInTheDocument();
    expect(screen.queryByText("Site 42")).not.toBeInTheDocument();
  });

  it("shows the no-results-yet message when the API returns an empty array", async () => {
    server.use(http.get("/api/v1/scans/7/results", () => HttpResponse.json([])));
    wrap(<ResultsTab scanId={7} />);
    await screen.findByText(/no results yet/i);
  });

  it("shows the no-match message when filters exclude everything", async () => {
    server.use(http.get("/api/v1/scans/7/results", () => HttpResponse.json(rows)));
    wrap(<ResultsTab scanId={7} />);
    await waitFor(() => expect(screen.getByText("Site 42")).toBeInTheDocument());
    await userEvent.type(screen.getByPlaceholderText(/search/i), "zzzznomatch");
    await waitFor(() => expect(screen.getByText(/no results match your filters/i)).toBeInTheDocument());
  });
});

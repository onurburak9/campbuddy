import { describe, it, expect } from "vitest";
import { http, HttpResponse } from "msw";
import { render, screen, waitFor } from "@testing-library/react";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { server } from "../../test/server";
import { ResultsTab } from "./ResultsTab";

const result = {
  id: 1, scan_id: 7, campsite_id: "A1", facility_name: "Upper Pines", site_name: "Site 42",
  campsite_type: "TENT", booking_date: "2026-07-01", booking_end_date: "2026-07-03",
  booking_url: "https://recreation.gov/x", first_seen_at: "2026-06-24T11:00:00Z",
  cart_added: true, notified: true,
};

function wrap(ui: React.ReactNode) {
  const qc = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  return render(<QueryClientProvider client={qc}>{ui}</QueryClientProvider>);
}

describe("ResultsTab", () => {
  it("renders result cards with a booking link and cart badge", async () => {
    server.use(http.get("/api/v1/scans/7/results", () => HttpResponse.json([result])));
    wrap(<ResultsTab scanId={7} />);
    await waitFor(() => expect(screen.getByText("Site 42")).toBeInTheDocument());
    expect(screen.getByText(/in cart/i)).toBeInTheDocument();
    expect(screen.getByRole("link", { name: /book/i })).toHaveAttribute("href", "https://recreation.gov/x");
  });

  it("shows empty state when no results", async () => {
    server.use(http.get("/api/v1/scans/7/results", () => HttpResponse.json([])));
    wrap(<ResultsTab scanId={7} />);
    await waitFor(() => expect(screen.getByText(/no results yet/i)).toBeInTheDocument());
  });
});

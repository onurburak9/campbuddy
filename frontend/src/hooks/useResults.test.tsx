import { describe, it, expect } from "vitest";
import { http, HttpResponse } from "msw";
import { renderHook, waitFor } from "@testing-library/react";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { server } from "../test/server";
import { useAllScanResults } from "./useResults";

function wrapper({ children }: { children: React.ReactNode }) {
  const qc = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  return <QueryClientProvider client={qc}>{children}</QueryClientProvider>;
}

function makeResult(id: number) {
  return { id, scan_run_id: 1, scan_id: 7, campsite_id: String(id), facility_name: "F",
    site_name: `S${id}`, campsite_type: "TENT", booking_date: "2026-07-01",
    booking_end_date: "2026-07-03", booking_url: "x", first_seen_at: "2026-06-30T11:00:00Z",
    last_seen_at: "2026-06-30T11:00:00Z", is_available: true,
    cart_added: false, notified: false };
}

describe("useAllScanResults", () => {
  it("pages through until a short page and concatenates", async () => {
    server.use(http.get("/api/v1/scans/7/results", ({ request }) => {
      const page = Number(new URL(request.url).searchParams.get("page"));
      if (page === 1) return HttpResponse.json(Array.from({ length: 100 }, (_, i) => makeResult(i + 1)));
      return HttpResponse.json([makeResult(101), makeResult(102)]); // short page → stop
    }));
    const { result } = renderHook(() => useAllScanResults(7), { wrapper });
    await waitFor(() => expect(result.current.isSuccess).toBe(true));
    expect(result.current.data).toHaveLength(102);
  });
});

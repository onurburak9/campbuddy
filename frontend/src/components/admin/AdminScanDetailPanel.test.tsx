import type { ReactNode } from "react";
import { describe, it, expect, vi } from "vitest";
import { render, screen, waitFor } from "@testing-library/react";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { http, HttpResponse } from "msw";
import { server } from "../../test/server";
import { AdminScanDetailPanel } from "./AdminScanDetailPanel";

vi.mock("../../api/search", () => ({
  search: {
    resolveRecreationAreas: vi.fn().mockResolvedValue([]),
    resolveCampgrounds: vi.fn().mockResolvedValue([]),
    resolveCampsites: vi.fn().mockResolvedValue([]),
  },
}));

function wrap(ui: ReactNode) {
  const qc = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  return render(<QueryClientProvider client={qc}>{ui}</QueryClientProvider>);
}

const DETAIL = {
  id: 9, user_id: 3, user_email: "owner@example.com", provider: "RecreationDotGov",
  name: "Yosemite trip", status: "active", polling_interval: 300,
  rec_area_ids: [2991], campground_ids: null, campsite_ids: null,
  search_windows: [{ start_date: "2026-12-03", end_date: "2026-12-05", expired: false }],
  nights: 2, days_of_week: null, weekends_only: false, notify_via_email: true,
  notify_via_telegram: false, notify_on_new_only: true, created_at: "2026-06-01T00:00:00Z",
};

describe("AdminScanDetailPanel", () => {
  it("shows the scan configuration once loaded", async () => {
    server.use(
      http.get("/api/v1/admin/scans/9", () => HttpResponse.json(DETAIL)),
      http.get("/api/v1/admin/scans/9/runs", () => HttpResponse.json([])),
    );
    wrap(<AdminScanDetailPanel scanId={9} />);
    expect(await screen.findByText("Configuration")).toBeInTheDocument();
    expect(screen.getByText("RecreationDotGov")).toBeInTheDocument();
  });

  it("shows recent runs with outcome, sites found, and duration", async () => {
    server.use(
      http.get("/api/v1/admin/scans/9", () => HttpResponse.json(DETAIL)),
      http.get("/api/v1/admin/scans/9/runs", () => HttpResponse.json([
        {
          id: 101, scan_id: 9, started_at: "2026-09-13T10:00:00Z",
          finished_at: "2026-09-13T10:00:05Z", outcome: "success", sites_found: 2, error_message: null,
        },
      ])),
    );
    wrap(<AdminScanDetailPanel scanId={9} />);
    expect(await screen.findByText("Success")).toBeInTheDocument();
    expect(screen.getByText("2 sites")).toBeInTheDocument();
  });

  it("notes that older runs may exist when the recent-runs page is full", async () => {
    const runs = Array.from({ length: 10 }, (_, i) => ({
      id: i, scan_id: 9, started_at: "2026-09-13T10:00:00Z",
      finished_at: "2026-09-13T10:00:05Z", outcome: "success", sites_found: 0, error_message: null,
    }));
    server.use(
      http.get("/api/v1/admin/scans/9", () => HttpResponse.json(DETAIL)),
      http.get("/api/v1/admin/scans/9/runs", () => HttpResponse.json(runs)),
    );
    wrap(<AdminScanDetailPanel scanId={9} />);
    expect(await screen.findByText(/showing the 10 most recent runs/i)).toBeInTheDocument();
  });

  it("shows a message when there are no runs yet", async () => {
    server.use(
      http.get("/api/v1/admin/scans/9", () => HttpResponse.json(DETAIL)),
      http.get("/api/v1/admin/scans/9/runs", () => HttpResponse.json([])),
    );
    wrap(<AdminScanDetailPanel scanId={9} />);
    await waitFor(() => expect(screen.getByText("No runs yet.")).toBeInTheDocument());
  });

  it("shows an error state when the detail fetch fails", async () => {
    server.use(http.get("/api/v1/admin/scans/9", () => new HttpResponse(null, { status: 500 })));
    wrap(<AdminScanDetailPanel scanId={9} />);
    expect(await screen.findByText("Failed to load scan detail.")).toBeInTheDocument();
  });
});

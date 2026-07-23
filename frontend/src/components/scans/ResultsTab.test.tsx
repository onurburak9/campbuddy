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

describe("ResultsTab (availability filter)", () => {
  const availabilityRows = [
    { ...rows[0], is_available: true },
    { ...rows[1], is_available: false },
    { ...rows[2], is_available: true },
  ];

  it("shows all results by default", async () => {
    server.use(http.get("/api/v1/scans/7/results", () => HttpResponse.json(availabilityRows)));
    wrap(<ResultsTab scanId={7} />);
    await waitFor(() => expect(screen.getByText("Site 42")).toBeInTheDocument());
    expect(screen.getByText("Site 7")).toBeInTheDocument();
    expect(screen.getByText("Loop A")).toBeInTheDocument();
  });

  it("filters to only available results when 'Available' is selected", async () => {
    server.use(http.get("/api/v1/scans/7/results", () => HttpResponse.json(availabilityRows)));
    wrap(<ResultsTab scanId={7} />);
    await waitFor(() => expect(screen.getByText("Site 42")).toBeInTheDocument());

    const availabilitySelect = screen.getByRole("option", { name: "All statuses" }).closest("select")!;
    await userEvent.selectOptions(availabilitySelect, "available");
    await waitFor(() => expect(screen.queryByText("Site 7")).not.toBeInTheDocument());
    expect(screen.getByText("Site 42")).toBeInTheDocument();
    expect(screen.getByText("Loop A")).toBeInTheDocument();
  });

  it("filters to only gone results when 'Gone' is selected", async () => {
    server.use(http.get("/api/v1/scans/7/results", () => HttpResponse.json(availabilityRows)));
    wrap(<ResultsTab scanId={7} />);
    await waitFor(() => expect(screen.getByText("Site 42")).toBeInTheDocument());

    const availabilitySelect = screen.getByRole("option", { name: "All statuses" }).closest("select")!;
    await userEvent.selectOptions(availabilitySelect, "gone");
    await waitFor(() => expect(screen.getByText("Site 7")).toBeInTheDocument());
    expect(screen.queryByText("Site 42")).not.toBeInTheDocument();
    expect(screen.queryByText("Loop A")).not.toBeInTheDocument();
  });
});

describe("ResultsTab (view toggle)", () => {
  it("defaults to Flat view when no results are groupable", async () => {
    server.use(http.get("/api/v1/scans/7/results", () => HttpResponse.json(rows)));
    wrap(<ResultsTab scanId={7} />);
    await waitFor(() => expect(screen.getByText("Site 42")).toBeInTheDocument());
    expect(screen.getByRole("option", { name: "All campgrounds" })).toBeInTheDocument();
  });

  it("defaults to Grouped view when results are groupable, hiding the facility filter", async () => {
    const groupedRows = [
      { ...rows[0], facility_id: "232447", recreation_area_id: "2991", recreation_area: "Yosemite National Park" },
    ];
    server.use(http.get("/api/v1/scans/7/results", () => HttpResponse.json(groupedRows)));
    wrap(<ResultsTab scanId={7} />);
    await waitFor(() => expect(screen.getByText("Yosemite National Park")).toBeInTheDocument());
    expect(screen.queryByRole("option", { name: "All campgrounds" })).not.toBeInTheDocument();
  });

  it("switches to the flat list when the Flat toggle is clicked", async () => {
    const groupedRows = [
      { ...rows[0], facility_id: "232447", recreation_area_id: "2991", recreation_area: "Yosemite National Park" },
    ];
    server.use(http.get("/api/v1/scans/7/results", () => HttpResponse.json(groupedRows)));
    wrap(<ResultsTab scanId={7} />);
    await waitFor(() => expect(screen.getByText("Yosemite National Park")).toBeInTheDocument());
    await userEvent.click(screen.getByRole("button", { name: "Flat" }));
    expect(screen.queryByText("Yosemite National Park")).not.toBeInTheDocument();
    expect(screen.getByText("Site 42")).toBeInTheDocument();
    expect(screen.getByRole("option", { name: "All campgrounds" })).toBeInTheDocument();
  });

  it("switches back to the grouped view when the Grouped toggle is clicked", async () => {
    const groupedRows = [
      { ...rows[0], facility_id: "232447", recreation_area_id: "2991", recreation_area: "Yosemite National Park" },
    ];
    server.use(http.get("/api/v1/scans/7/results", () => HttpResponse.json(groupedRows)));
    wrap(<ResultsTab scanId={7} />);
    await waitFor(() => expect(screen.getByText("Yosemite National Park")).toBeInTheDocument());
    await userEvent.click(screen.getByRole("button", { name: "Flat" }));
    await waitFor(() => expect(screen.getByText("Site 42")).toBeInTheDocument());
    await userEvent.click(screen.getByRole("button", { name: "Grouped" }));
    expect(screen.getByText("Yosemite National Park")).toBeInTheDocument();
  });

  it("hides a group entirely when the type filter excludes all of its rows", async () => {
    const groupedRows = [
      { ...rows[0], id: 1, site_name: "Tent Site", campsite_type: "TENT", facility_id: "232447", facility_name: "Upper Pines", recreation_area_id: "2991", recreation_area: "Yosemite National Park" },
      { ...rows[0], id: 2, site_name: "RV Site", campsite_type: "RV", facility_id: "999", facility_name: "Lower Pines", recreation_area_id: "2991", recreation_area: "Yosemite National Park" },
    ];
    server.use(http.get("/api/v1/scans/7/results", () => HttpResponse.json(groupedRows)));
    wrap(<ResultsTab scanId={7} />);
    await waitFor(() => expect(screen.getAllByText("Upper Pines").length).toBeGreaterThan(0));
    expect(screen.getAllByText("Lower Pines").length).toBeGreaterThan(0);

    const typeSelect = screen.getByRole("option", { name: "All types" }).closest("select")!;
    await userEvent.selectOptions(typeSelect, "TENT");
    await waitFor(() => expect(screen.queryByText("Lower Pines")).not.toBeInTheDocument());
    expect(screen.getAllByText("Upper Pines").length).toBeGreaterThan(0);
  });
});

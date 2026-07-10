import type { ReactNode } from "react";
import { describe, it, expect, vi } from "vitest";
import { render, screen, waitFor } from "@testing-library/react";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { NotificationsFields, ProviderSitesFields } from "./ScanForm";
import type { ScanFormState } from "./useScanFormState";

vi.mock("../../api/search", () => ({
  search: {
    recreationAreas: vi.fn().mockResolvedValue([]),
    resolveRecreationAreas: vi.fn().mockResolvedValue([{ id: 2991, name: "Yosemite National Park" }]),
    campgrounds: vi.fn().mockResolvedValue([]),
    resolveCampgrounds: vi.fn().mockResolvedValue([]),
    campsites: vi.fn().mockResolvedValue([]),
    resolveCampsites: vi.fn().mockResolvedValue([]),
  },
}));

function wrapWithQueryClient(children: ReactNode) {
  const qc = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  return <QueryClientProvider client={qc}>{children}</QueryClientProvider>;
}

function makeState(pollingInterval: number): ScanFormState {
  return {
    name: "",
    provider: "RecreationDotGov",
    recAreaIds: [],
    campgroundIds: [],
    campsiteIds: [],
    windows: [],
    nights: 1,
    daysOfWeek: [],
    weekendsOnly: false,
    pollingInterval,
    notifyEmail: true,
    notifyTelegram: false,
    notifyNewOnly: true,
  };
}

const noop = () => {};

describe("NotificationsFields — polling interval options", () => {
  it("shows the seven curated options when pollingInterval is 300 (default)", () => {
    render(
      <NotificationsFields state={makeState(300)} set={noop as any} telegramAvailable={true} />,
    );

    expect(screen.getByRole("option", { name: "5 min" })).toBeInTheDocument();
    expect(screen.getByRole("option", { name: "15 min" })).toBeInTheDocument();
    expect(screen.getByRole("option", { name: "30 min" })).toBeInTheDocument();
    expect(screen.getByRole("option", { name: "45 min" })).toBeInTheDocument();
    expect(screen.getByRole("option", { name: "1 hour" })).toBeInTheDocument();
    expect(screen.getByRole("option", { name: "2 hours" })).toBeInTheDocument();
    expect(screen.getByRole("option", { name: "6 hours" })).toBeInTheDocument();

    // Intervals not in the curated list should NOT be present
    expect(screen.queryByRole("option", { name: "1 min" })).not.toBeInTheDocument();
    expect(screen.queryByRole("option", { name: "10 min" })).not.toBeInTheDocument();
  });

  it("prepends a legacy option when pollingInterval is not in the curated list (e.g. 600s → '10 min')", () => {
    render(
      <NotificationsFields state={makeState(600)} set={noop as any} telegramAvailable={true} />,
    );

    // Legacy value is present as an extra option
    expect(screen.getByRole("option", { name: "10 min" })).toBeInTheDocument();

    // Curated options are still all present
    expect(screen.getByRole("option", { name: "5 min" })).toBeInTheDocument();
    expect(screen.getByRole("option", { name: "15 min" })).toBeInTheDocument();
    expect(screen.getByRole("option", { name: "30 min" })).toBeInTheDocument();
    expect(screen.getByRole("option", { name: "45 min" })).toBeInTheDocument();
    expect(screen.getByRole("option", { name: "1 hour" })).toBeInTheDocument();
    expect(screen.getByRole("option", { name: "2 hours" })).toBeInTheDocument();
    expect(screen.getByRole("option", { name: "6 hours" })).toBeInTheDocument();
  });
});

describe("ProviderSitesFields — id resolution", () => {
  it("resolves a fallback 'ID {n}' label to the real name on mount", async () => {
    const state = makeState(300);
    state.recAreaIds = [{ id: 2991, name: "ID 2991" }];
    render(wrapWithQueryClient(<ProviderSitesFields state={state} set={() => {}} />));
    expect(screen.getByText("ID 2991")).toBeInTheDocument();
    await waitFor(() => expect(screen.getByText("Yosemite National Park")).toBeInTheDocument());
  });
});

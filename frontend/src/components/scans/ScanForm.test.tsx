import type { ReactNode } from "react";
import { useState } from "react";
import { describe, it, expect, vi } from "vitest";
import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { NotificationsFields, ProviderSitesFields, DatesFiltersFields } from "./ScanForm";
import { PROVIDERS } from "../../types";
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

function ControlledDatesFilters({ initial }: { initial: Partial<ScanFormState> }) {
  const [state, setState] = useState<ScanFormState>({ ...makeState(300), ...initial });
  const set = <K extends keyof ScanFormState>(key: K, value: ScanFormState[K]) =>
    setState((prev) => ({ ...prev, [key]: value }));
  return <DatesFiltersFields state={state} set={set} />;
}

describe("DatesFiltersFields — consecutive nights input", () => {
  it("allows clearing the field to empty instead of snapping back to 1 on every keystroke", async () => {
    const user = userEvent.setup();
    render(<ControlledDatesFilters initial={{ nights: 3 }} />);
    const input = screen.getByLabelText("Consecutive nights") as HTMLInputElement;

    await user.clear(input);

    expect(input.value).toBe("");
  });

  it("resets an empty field back to 1 on blur", async () => {
    const user = userEvent.setup();
    render(<ControlledDatesFilters initial={{ nights: 3 }} />);
    const input = screen.getByLabelText("Consecutive nights") as HTMLInputElement;

    await user.clear(input);
    await user.tab();

    expect(input.value).toBe("1");
  });

  it("shows a validation message when nights exceeds the shortest search window", () => {
    render(
      <ControlledDatesFilters
        initial={{
          nights: 5,
          windows: [{ start_date: "2026-07-03", end_date: "2026-07-06" }],
        }}
      />,
    );

    expect(screen.getByText(/can't be longer than the shortest search window/i)).toBeInTheDocument();
  });

  it("does not show a validation message when nights fits within the window", () => {
    render(
      <ControlledDatesFilters
        initial={{
          nights: 3,
          windows: [{ start_date: "2026-07-03", end_date: "2026-07-06" }],
        }}
      />,
    );

    expect(screen.queryByText(/can't be longer than the shortest search window/i)).not.toBeInTheDocument();
  });
});

describe("ProviderSitesFields — provider selection", () => {
  it("only enables RecreationDotGov; every other provider option is disabled", () => {
    render(wrapWithQueryClient(<ProviderSitesFields state={makeState(300)} set={() => {}} />));
    for (const provider of PROVIDERS) {
      const option = screen.getByRole("option", { name: provider }) as HTMLOptionElement;
      expect(option.disabled).toBe(provider !== "RecreationDotGov");
    }
  });
});

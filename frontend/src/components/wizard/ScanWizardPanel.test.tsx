import { describe, it, expect, vi, beforeEach, afterEach } from "vitest";
import { http, HttpResponse } from "msw";
import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { server } from "../../test/server";

const mockUser = vi.fn((): { id: number; email: string; has_telegram: boolean; scan_limit: number; scans_used: number } => ({
  id: 1, email: "a@b.c", has_telegram: true, scan_limit: 5, scans_used: 1,
}));
vi.mock("../../contexts/AuthContext", () => ({ useAuth: () => ({ user: mockUser() }) }));
vi.mock("../../lib/tour");

import { ScanWizardPanel } from "./ScanWizardPanel";
import {
  startWizardProviderTour,
  hasSeenWizardTour,
  startWizardDatesTour,
  hasSeenWizardDatesTour,
} from "../../lib/tour";

const startWizardProviderTourMock = vi.mocked(startWizardProviderTour);
const hasSeenWizardTourMock = vi.mocked(hasSeenWizardTour);
const startWizardDatesTourMock = vi.mocked(startWizardDatesTour);
const hasSeenWizardDatesTourMock = vi.mocked(hasSeenWizardDatesTour);

function wrap(ui: React.ReactNode) {
  const qc = new QueryClient({ defaultOptions: { mutations: { retry: false } } });
  return render(<QueryClientProvider client={qc}>{ui}</QueryClientProvider>);
}

describe("ScanWizardPanel", () => {
  // Date fixtures below are relative to this instant; pinning the clock keeps
  // them from silently drifting into the past as real time passes.
  beforeEach(() => {
    vi.useFakeTimers({ toFake: ["Date"] });
    vi.setSystemTime(new Date(2026, 5, 15, 12, 0, 0));
  });
  afterEach(() => vi.useRealTimers());

  beforeEach(() => {
    // Adding an id via the fallback "Add by ID" input triggers a resolve-on-mount
    // request for its real name; stub it so tests don't hit an unhandled request.
    server.use(
      http.get("/api/v1/search/recreation-areas/resolve", () =>
        HttpResponse.json([{ id: 2991, name: "Yosemite" }])
      )
    );
    mockUser.mockReturnValue({ id: 1, email: "a@b.c", has_telegram: true, scan_limit: 5, scans_used: 1 });
  });

  it("walks through the steps and creates a scan", async () => {
    server.use(http.post("/api/v1/scans", async ({ request }) => {
      const body: any = await request.json();
      expect(body.rec_area_ids).toEqual([2991]);
      return HttpResponse.json({ ...body, id: 99, user_id: 1, status: "active", created_at: "x" });
    }));
    const onCreated = vi.fn();
    wrap(<ScanWizardPanel onClose={vi.fn()} onCreated={onCreated} />);

    // Step 1 — add a Recreation Area by ID via the SearchSelect's fallback input
    await userEvent.type(screen.getAllByLabelText(/add by id/i)[0], "2991");
    await userEvent.click(screen.getAllByRole("button", { name: /^add$/i })[0]);
    await userEvent.click(screen.getByRole("button", { name: "Next →" }));
    // Step 2 — add a window
    await userEvent.click(screen.getByRole("button", { name: /add window/i }));
    const dates = screen.getAllByDisplayValue("");
    // first two empty inputs are the date pickers
    await userEvent.type(dates[0], "2026-07-01");
    await userEvent.type(dates[1], "2026-07-03");
    await userEvent.click(screen.getByRole("button", { name: "Next →" }));
    // Step 3 — create
    await userEvent.click(screen.getByRole("button", { name: /create scan/i }));
    await waitFor(() => expect(onCreated).toHaveBeenCalledWith(99));
  });

  it("disables Create Scan and shows a message when the user is at their scan limit", async () => {
    mockUser.mockReturnValue({ id: 1, email: "a@b.c", has_telegram: true, scan_limit: 5, scans_used: 5 });
    wrap(<ScanWizardPanel onClose={vi.fn()} onCreated={vi.fn()} />);

    await userEvent.type(screen.getAllByLabelText(/add by id/i)[0], "2991");
    await userEvent.click(screen.getAllByRole("button", { name: /^add$/i })[0]);
    await userEvent.click(screen.getByRole("button", { name: "Next →" }));
    await userEvent.click(screen.getByRole("button", { name: /add window/i }));
    const dates = screen.getAllByDisplayValue("");
    await userEvent.type(dates[0], "2026-07-01");
    await userEvent.type(dates[1], "2026-07-03");
    await userEvent.click(screen.getByRole("button", { name: "Next →" }));

    expect(screen.getByText(/reached your scan limit/i)).toBeInTheDocument();
    expect(screen.getByRole("button", { name: /create scan/i })).toBeDisabled();
  });

  it("shows a compact mobile step indicator that advances", async () => {
    wrap(<ScanWizardPanel onClose={vi.fn()} onCreated={vi.fn()} />);
    expect(screen.getByText(/step 1 of 3 · provider & sites/i)).toBeInTheDocument();
    await userEvent.type(screen.getAllByLabelText(/add by id/i)[0], "2991");
    await userEvent.click(screen.getAllByRole("button", { name: /^add$/i })[0]);
    await userEvent.click(screen.getByRole("button", { name: "Next →" }));
    expect(screen.getByText(/step 2 of 3 · dates & filters/i)).toBeInTheDocument();
  });

  beforeEach(() => {
    startWizardProviderTourMock.mockClear();
    hasSeenWizardTourMock.mockClear();
    hasSeenWizardTourMock.mockReturnValue(true);
    startWizardDatesTourMock.mockClear();
    hasSeenWizardDatesTourMock.mockClear();
    hasSeenWizardDatesTourMock.mockReturnValue(true);
  });

  it("auto-starts the provider tour on mount when it hasn't been seen", () => {
    hasSeenWizardTourMock.mockReturnValue(false);
    wrap(<ScanWizardPanel onClose={vi.fn()} onCreated={vi.fn()} />);
    expect(startWizardProviderTourMock).toHaveBeenCalledTimes(1);
  });

  it("does not auto-start the provider tour on mount when it has already been seen", () => {
    wrap(<ScanWizardPanel onClose={vi.fn()} onCreated={vi.fn()} />);
    expect(startWizardProviderTourMock).not.toHaveBeenCalled();
  });

  it("replays the tour for whichever step the user is on", async () => {
    wrap(<ScanWizardPanel onClose={vi.fn()} onCreated={vi.fn()} />);
    await userEvent.click(screen.getAllByRole("button", { name: /show tips for this step/i })[0]);
    expect(startWizardProviderTourMock).toHaveBeenCalledTimes(1);

    await userEvent.type(screen.getAllByLabelText(/add by id/i)[0], "2991");
    await userEvent.click(screen.getAllByRole("button", { name: /^add$/i })[0]);
    await userEvent.click(screen.getByRole("button", { name: "Next →" }));

    await userEvent.click(screen.getAllByRole("button", { name: /show tips for this step/i })[0]);
    expect(startWizardDatesTourMock).toHaveBeenCalledTimes(1);
    expect(startWizardProviderTourMock).toHaveBeenCalledTimes(1);
  });

  it("auto-starts the dates tour the first time the user reaches the dates step", async () => {
    hasSeenWizardDatesTourMock.mockReturnValue(false);
    wrap(<ScanWizardPanel onClose={vi.fn()} onCreated={vi.fn()} />);
    expect(startWizardDatesTourMock).not.toHaveBeenCalled();

    await userEvent.type(screen.getAllByLabelText(/add by id/i)[0], "2991");
    await userEvent.click(screen.getAllByRole("button", { name: /^add$/i })[0]);
    await userEvent.click(screen.getByRole("button", { name: "Next →" }));

    expect(startWizardDatesTourMock).toHaveBeenCalledTimes(1);
  });

  it("does not auto-start the dates tour once it has been seen", async () => {
    wrap(<ScanWizardPanel onClose={vi.fn()} onCreated={vi.fn()} />);
    await userEvent.type(screen.getAllByLabelText(/add by id/i)[0], "2991");
    await userEvent.click(screen.getAllByRole("button", { name: /^add$/i })[0]);
    await userEvent.click(screen.getByRole("button", { name: "Next →" }));

    expect(startWizardDatesTourMock).not.toHaveBeenCalled();
  });

  it("hides the help icon on the notifications step, which has no tour", async () => {
    wrap(<ScanWizardPanel onClose={vi.fn()} onCreated={vi.fn()} />);
    await userEvent.type(screen.getAllByLabelText(/add by id/i)[0], "2991");
    await userEvent.click(screen.getAllByRole("button", { name: /^add$/i })[0]);
    await userEvent.click(screen.getByRole("button", { name: "Next →" }));
    await userEvent.click(screen.getByRole("button", { name: /add window/i }));
    const dates = screen.getAllByDisplayValue("");
    await userEvent.type(dates[0], "2026-07-01");
    await userEvent.type(dates[1], "2026-07-03");
    await userEvent.click(screen.getByRole("button", { name: "Next →" }));

    expect(screen.queryByRole("button", { name: /show tips for this step/i })).not.toBeInTheDocument();
  });

  it("blocks advancing past the dates step when no search window has been added", async () => {
    wrap(<ScanWizardPanel onClose={vi.fn()} onCreated={vi.fn()} />);

    await userEvent.type(screen.getAllByLabelText(/add by id/i)[0], "2991");
    await userEvent.click(screen.getAllByRole("button", { name: /^add$/i })[0]);
    await userEvent.click(screen.getByRole("button", { name: "Next →" }));
    await userEvent.click(screen.getByRole("button", { name: "Next →" }));

    expect(screen.getByText(/add at least one search window with start and end dates/i))
      .toBeInTheDocument();
    expect(screen.getByText(/step 2 of 3 · dates & filters/i)).toBeInTheDocument();
  });

  it("blocks advancing past the dates step when every window has already ended", async () => {
    wrap(<ScanWizardPanel onClose={vi.fn()} onCreated={vi.fn()} />);

    await userEvent.type(screen.getAllByLabelText(/add by id/i)[0], "2991");
    await userEvent.click(screen.getAllByRole("button", { name: /^add$/i })[0]);
    await userEvent.click(screen.getByRole("button", { name: "Next →" }));
    await userEvent.click(screen.getByRole("button", { name: /add window/i }));
    const dates = screen.getAllByDisplayValue("");
    await userEvent.type(dates[0], "2026-04-01");
    await userEvent.type(dates[1], "2026-04-03");
    await userEvent.click(screen.getByRole("button", { name: "Next →" }));

    expect(screen.getByText(/at least one search window must end today or later/i))
      .toBeInTheDocument();
    expect(screen.getByText(/step 2 of 3 · dates & filters/i)).toBeInTheDocument();
  });
});

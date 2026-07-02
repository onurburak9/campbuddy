import { describe, it, expect, vi } from "vitest";
import { http, HttpResponse } from "msw";
import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { server } from "../../test/server";

vi.mock("../../contexts/AuthContext", () => ({ useAuth: () => ({ user: { id: 1, email: "a@b.c", has_telegram: true } }) }));
import { ScanWizardPanel } from "./ScanWizardPanel";

function wrap(ui: React.ReactNode) {
  const qc = new QueryClient({ defaultOptions: { mutations: { retry: false } } });
  return render(<QueryClientProvider client={qc}>{ui}</QueryClientProvider>);
}

describe("ScanWizardPanel", () => {
  it("walks through the steps and creates a scan", async () => {
    server.use(http.post("/api/v1/scans", async ({ request }) => {
      const body: any = await request.json();
      expect(body.rec_area_ids).toEqual([2991]);
      return HttpResponse.json({ ...body, id: 99, user_id: 1, status: "active", created_at: "x" });
    }));
    const onCreated = vi.fn();
    wrap(<ScanWizardPanel onClose={vi.fn()} onCreated={onCreated} />);

    // Step 1
    await userEvent.type(screen.getByLabelText(/recreation area ids/i), "2991");
    await userEvent.click(screen.getByRole("button", { name: /next/i }));
    // Step 2 — add a window
    await userEvent.click(screen.getByRole("button", { name: /add window/i }));
    const dates = screen.getAllByDisplayValue("");
    // first two empty inputs are the date pickers
    await userEvent.type(dates[0], "2026-07-01");
    await userEvent.type(dates[1], "2026-07-03");
    await userEvent.click(screen.getByRole("button", { name: /next/i }));
    // Step 3 — create
    await userEvent.click(screen.getByRole("button", { name: /create scan/i }));
    await waitFor(() => expect(onCreated).toHaveBeenCalledWith(99));
  });

  it("shows a compact mobile step indicator that advances", async () => {
    wrap(<ScanWizardPanel onClose={vi.fn()} onCreated={vi.fn()} />);
    expect(screen.getByText(/step 1 of 3 · provider & sites/i)).toBeInTheDocument();
    await userEvent.type(screen.getByLabelText(/recreation area ids/i), "2991");
    await userEvent.click(screen.getByRole("button", { name: /next/i }));
    expect(screen.getByText(/step 2 of 3 · dates & filters/i)).toBeInTheDocument();
  });
});

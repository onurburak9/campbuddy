import { describe, it, expect, vi } from "vitest";
import { http, HttpResponse } from "msw";
import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { server } from "../../test/server";

vi.mock("../../contexts/AuthContext", () => ({
  useAuth: () => ({ user: { id: 1, email: "a@b.c", scan_limit: 5, scans_used: 0, has_telegram: true } }),
}));
import type { Scan } from "../../types";
import { SettingsTab } from "./SettingsTab";

const scan: Scan = {
  id: 7, user_id: 1, provider: "RecreationDotGov", name: "Yosemite", status: "active",
  polling_interval: 300, rec_area_ids: [2991], campground_ids: null, campsite_ids: null,
  search_windows: [{ start_date: "2026-07-01", end_date: "2026-07-03" }], nights: 2,
  days_of_week: null, weekends_only: false, notify_via_email: true,
  notify_via_telegram: false, notify_on_new_only: true, created_at: "2026-06-01T00:00:00Z",
};

function wrap(ui: React.ReactNode) {
  const qc = new QueryClient({ defaultOptions: { mutations: { retry: false } } });
  return render(<QueryClientProvider client={qc}>{ui}</QueryClientProvider>);
}

describe("SettingsTab", () => {
  it("saves edits via PATCH", async () => {
    let patched: any = null;
    server.use(http.patch("/api/v1/scans/7", async ({ request }) => {
      patched = await request.json();
      return HttpResponse.json({ ...scan, name: patched.name });
    }));
    wrap(<SettingsTab scan={scan} />);
    const nameInput = screen.getByDisplayValue("Yosemite");
    await userEvent.clear(nameInput);
    await userEvent.type(nameInput, "Yosemite Fall");
    await userEvent.click(screen.getByRole("button", { name: /save/i }));
    await waitFor(() => expect(patched?.name).toBe("Yosemite Fall"));
  });

  it("shows 'Save failed' and does not throw when PATCH returns 500", async () => {
    server.use(http.patch("/api/v1/scans/7", () => HttpResponse.json({ detail: "error" }, { status: 500 })));
    wrap(<SettingsTab scan={scan} />);
    await userEvent.click(screen.getByRole("button", { name: /save/i }));
    expect(await screen.findByText(/save failed/i)).toBeInTheDocument();
  });

  it("sends notify_via_email=false when toggling the email switch off", async () => {
    let patched: any = null;
    server.use(http.patch("/api/v1/scans/7", async ({ request }) => {
      patched = await request.json();
      return HttpResponse.json({ ...scan, ...patched });
    }));
    wrap(<SettingsTab scan={scan} />);
    await userEvent.click(screen.getByRole("switch", { name: /notify via email/i }));
    await userEvent.click(screen.getByRole("button", { name: /save/i }));
    await waitFor(() => expect(patched?.notify_via_email).toBe(false));
  });
});

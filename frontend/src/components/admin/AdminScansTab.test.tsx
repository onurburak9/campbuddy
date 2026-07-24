import { describe, it, expect, vi } from "vitest";
import { http, HttpResponse } from "msw";
import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { server } from "../../test/server";
import { AdminScansTab } from "./AdminScansTab";

function renderTab() {
  const qc = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  return render(<QueryClientProvider client={qc}><AdminScansTab /></QueryClientProvider>);
}

const SCAN = {
  id: 1, user_id: 1, user_email: "user@e.com", provider: "RecreationDotGov",
  name: "Yosemite", status: "active", polling_interval: 300, created_at: "2026-01-01T00:00:00Z",
};

describe("AdminScansTab", () => {
  it("renders a row per scan with owner and status", async () => {
    server.use(http.get("/api/v1/admin/scans", () => HttpResponse.json([SCAN])));
    renderTab();
    expect(await screen.findByText("user@e.com")).toBeInTheDocument();
    expect(screen.getByText("Yosemite")).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Pause" })).toBeInTheDocument();
  });

  it("pauses an active scan and reflects the new status", async () => {
    let status = "active";
    server.use(
      http.get("/api/v1/admin/scans", () => HttpResponse.json([{ ...SCAN, status }])),
      http.post("/api/v1/admin/scans/1/pause", () => {
        status = "paused";
        return HttpResponse.json({ ...SCAN, status });
      }),
    );
    renderTab();
    await screen.findByText("Yosemite");
    await userEvent.click(screen.getByRole("button", { name: "Pause" }));
    await screen.findByRole("button", { name: "Resume" });
  });

  it("deletes a scan after confirmation", async () => {
    const confirmSpy = vi.spyOn(window, "confirm").mockReturnValue(true);
    let deleted = false;
    server.use(
      http.get("/api/v1/admin/scans", () => HttpResponse.json([SCAN])),
      http.delete("/api/v1/admin/scans/1", () => {
        deleted = true;
        return new HttpResponse(null, { status: 204 });
      }),
    );
    renderTab();
    await screen.findByText("Yosemite");
    await userEvent.click(screen.getByRole("button", { name: "Delete" }));
    expect(confirmSpy).toHaveBeenCalled();
    await waitFor(() => expect(deleted).toBe(true));
    confirmSpy.mockRestore();
  });

  it("shows an empty state when there are no scans", async () => {
    server.use(http.get("/api/v1/admin/scans", () => HttpResponse.json([])));
    renderTab();
    expect(await screen.findByText("No scans found.")).toBeInTheDocument();
  });
});

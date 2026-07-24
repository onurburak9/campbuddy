import { describe, it, expect } from "vitest";
import { http, HttpResponse } from "msw";
import { render, screen } from "@testing-library/react";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { server } from "../../test/server";
import { AdminUsersTab } from "./AdminUsersTab";

function renderTab() {
  const qc = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  return render(<QueryClientProvider client={qc}><AdminUsersTab /></QueryClientProvider>);
}

describe("AdminUsersTab", () => {
  it("renders a row per user with scan counts and role", async () => {
    server.use(http.get("/api/v1/admin/users", () => HttpResponse.json([
      { id: 1, email: "admin@e.com", is_admin: true, scan_limit: 5, scans_used: 2, has_telegram: true, created_at: "2026-01-01T00:00:00Z" },
      { id: 2, email: "user@e.com", is_admin: false, scan_limit: 5, scans_used: 0, has_telegram: false, created_at: "2026-01-02T00:00:00Z" },
    ])));
    renderTab();
    expect(await screen.findByText("admin@e.com")).toBeInTheDocument();
    expect(screen.getByText("user@e.com")).toBeInTheDocument();
    expect(screen.getByText("2 / 5")).toBeInTheDocument();
    expect(screen.getByText("Admin")).toBeInTheDocument();
  });

  it("shows an empty state when there are no users", async () => {
    server.use(http.get("/api/v1/admin/users", () => HttpResponse.json([])));
    renderTab();
    expect(await screen.findByText("No users found.")).toBeInTheDocument();
  });
});

import { describe, it, expect } from "vitest";
import { http, HttpResponse } from "msw";
import { render, screen, waitFor } from "@testing-library/react";
import { MemoryRouter, Routes, Route } from "react-router-dom";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { server } from "../../test/server";
import { AuthProvider } from "../../contexts/AuthContext";
import { HomeRoute } from "./HomeRoute";

function renderHome() {
  const qc = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  return render(
    <QueryClientProvider client={qc}>
      <AuthProvider>
        <MemoryRouter initialEntries={["/"]}>
          <Routes>
            <Route path="/" element={<HomeRoute><div>dashboard</div></HomeRoute>} />
          </Routes>
        </MemoryRouter>
      </AuthProvider>
    </QueryClientProvider>
  );
}

describe("HomeRoute", () => {
  it("shows the landing page when unauthenticated", async () => {
    server.use(http.get("/api/v1/auth/me", () => new HttpResponse(null, { status: 401 })));
    renderHome();
    await waitFor(() => expect(screen.getByRole("heading", { level: 1 })).toHaveTextContent("Sold-out campsite?"));
    expect(screen.queryByText("dashboard")).not.toBeInTheDocument();
  });

  it("shows the dashboard when authenticated", async () => {
    server.use(http.get("/api/v1/auth/me", () =>
      HttpResponse.json({ id: 1, email: "a@b.c", scan_limit: 5, scans_used: 0 })));
    renderHome();
    await waitFor(() => expect(screen.getByText("dashboard")).toBeInTheDocument());
    expect(screen.queryByRole("heading", { level: 1 })).not.toBeInTheDocument();
  });
});

import { describe, it, expect } from "vitest";
import { http, HttpResponse } from "msw";
import { render, screen, waitFor } from "@testing-library/react";
import { MemoryRouter, Routes, Route } from "react-router-dom";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { server } from "../../test/server";
import { AuthProvider } from "../../contexts/AuthContext";
import { ProtectedRoute } from "./ProtectedRoute";

function renderAt(path: string) {
  const qc = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  return render(
    <QueryClientProvider client={qc}>
      <AuthProvider>
        <MemoryRouter initialEntries={[path]}>
          <Routes>
            <Route path="/login" element={<div>login page</div>} />
            <Route path="/" element={<ProtectedRoute><div>secret</div></ProtectedRoute>} />
          </Routes>
        </MemoryRouter>
      </AuthProvider>
    </QueryClientProvider>
  );
}

describe("ProtectedRoute", () => {
  it("redirects to /login when unauthenticated", async () => {
    server.use(http.get("/api/v1/auth/me", () => new HttpResponse(null, { status: 401 })));
    renderAt("/");
    await waitFor(() => expect(screen.getByText("login page")).toBeInTheDocument());
  });

  it("renders children when authenticated", async () => {
    server.use(http.get("/api/v1/auth/me", () =>
      HttpResponse.json({ id: 1, email: "a@b.c", scan_limit: 5, scans_used: 0 })));
    renderAt("/");
    await waitFor(() => expect(screen.getByText("secret")).toBeInTheDocument());
    expect(screen.getByRole("button", { name: /feedback/i })).toBeInTheDocument();
  });
});

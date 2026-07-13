import { describe, it, expect } from "vitest";
import { http, HttpResponse } from "msw";
import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { server } from "../test/server";
import { AuthProvider, useAuth } from "./AuthContext";

function Probe() {
  const { isAuthenticated, isLoading, user, login } = useAuth();
  if (isLoading) return <span>loading</span>;
  return (
    <div>
      <span>{isAuthenticated ? `hi ${user?.email}` : "anon"}</span>
      <button onClick={() => login("a@b.c", "pw")}>login</button>
    </div>
  );
}

function wrap() {
  const qc = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  return render(
    <QueryClientProvider client={qc}>
      <AuthProvider><Probe /></AuthProvider>
    </QueryClientProvider>
  );
}

describe("AuthContext", () => {
  it("shows anon when /auth/me returns 401", async () => {
    server.use(http.get("/api/v1/auth/me", () => new HttpResponse(null, { status: 401 })));
    wrap();
    await waitFor(() => expect(screen.getByText("anon")).toBeInTheDocument());
  });

  it("authenticates after login", async () => {
    let logged = false;
    server.use(
      http.get("/api/v1/auth/me", () =>
        logged
          ? HttpResponse.json({ id: 1, email: "a@b.c", scan_limit: 5, scans_used: 0 })
          : new HttpResponse(null, { status: 401 })
      ),
      http.post("/api/v1/auth/login", () => { logged = true; return HttpResponse.json(undefined); })
    );
    wrap();
    await waitFor(() => expect(screen.getByText("anon")).toBeInTheDocument());
    await userEvent.click(screen.getByText("login"));
    await waitFor(() => expect(screen.getByText("hi a@b.c")).toBeInTheDocument());
  });

  it("registers and authenticates", async () => {
    let registered = false;
    server.use(
      http.get("/api/v1/auth/me", () =>
        registered
          ? HttpResponse.json({ id: 2, email: "new@e.com", scan_limit: 5, scans_used: 0 })
          : new HttpResponse(null, { status: 401 })
      ),
      http.post("/api/v1/auth/register", () => { registered = true; return HttpResponse.json(undefined); })
    );
    function RegisterProbe() {
      const { isAuthenticated, isLoading, register } = useAuth();
      if (isLoading) return <span>loading</span>;
      return (
        <div>
          <span>{isAuthenticated ? "in" : "out"}</span>
          <button onClick={() => register("new@e.com", "longenough")}>register</button>
        </div>
      );
    }
    const qc = new QueryClient({ defaultOptions: { queries: { retry: false } } });
    render(
      <QueryClientProvider client={qc}>
        <AuthProvider><RegisterProbe /></AuthProvider>
      </QueryClientProvider>
    );
    await waitFor(() => expect(screen.getByText("out")).toBeInTheDocument());
    await userEvent.click(screen.getByText("register"));
    await waitFor(() => expect(screen.getByText("in")).toBeInTheDocument());
  });
});

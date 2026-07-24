import { describe, it, expect, vi } from "vitest";
import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { MemoryRouter, Routes, Route } from "react-router-dom";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { http, HttpResponse } from "msw";
import { server } from "../../test/server";

const navigate = vi.fn();
const mockUser = vi.fn((): { email: string; is_admin: boolean } => ({ email: "admin@e.com", is_admin: true }));
vi.mock("../../contexts/AuthContext", () => ({ useAuth: () => ({ user: mockUser(), logout: vi.fn() }) }));
vi.mock("../../contexts/ThemeContext", () => ({ useTheme: () => ({ theme: "light", toggle: vi.fn() }) }));
vi.mock("react-router-dom", async (orig) => ({
  ...(await orig<typeof import("react-router-dom")>()),
  useNavigate: () => navigate,
}));

import { AdminPage } from "./AdminPage";

function renderPage() {
  const qc = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  return render(
    <QueryClientProvider client={qc}>
      <MemoryRouter><AdminPage /></MemoryRouter>
    </QueryClientProvider>
  );
}

describe("AdminPage", () => {
  it("renders the Users tab by default", () => {
    server.use(
      http.get("/api/v1/admin/users", () => HttpResponse.json([])),
      http.get("/api/v1/admin/scans", () => HttpResponse.json([])),
    );
    renderPage();
    expect(screen.getByRole("tab", { name: "Users" })).toHaveAttribute("aria-selected", "true");
  });

  it("switches to the Scans tab on click", async () => {
    server.use(
      http.get("/api/v1/admin/users", () => HttpResponse.json([])),
      http.get("/api/v1/admin/scans", () => HttpResponse.json([])),
    );
    renderPage();
    await userEvent.click(screen.getByRole("tab", { name: "Scans" }));
    expect(await screen.findByText("No scans found.")).toBeInTheDocument();
  });

  it("redirects to / when the user is not an admin", () => {
    mockUser.mockReturnValue({ email: "a@e.com", is_admin: false });
    const qc = new QueryClient({ defaultOptions: { queries: { retry: false } } });
    render(
      <QueryClientProvider client={qc}>
        <MemoryRouter initialEntries={["/admin"]}>
          <Routes>
            <Route path="/admin" element={<AdminPage />} />
            <Route path="/" element={<div>home</div>} />
          </Routes>
        </MemoryRouter>
      </QueryClientProvider>
    );
    expect(screen.getByText("home")).toBeInTheDocument();
    mockUser.mockReturnValue({ email: "admin@e.com", is_admin: true });
  });
});

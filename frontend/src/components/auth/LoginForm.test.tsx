import { describe, it, expect, vi } from "vitest";
import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { MemoryRouter } from "react-router-dom";
import { ApiError } from "../../api/client";

const login = vi.fn();
const navigate = vi.fn();
vi.mock("../../contexts/AuthContext", () => ({ useAuth: () => ({ login }) }));
vi.mock("react-router-dom", async (orig) => ({
  ...(await orig<typeof import("react-router-dom")>()),
  useNavigate: () => navigate,
}));

import { LoginForm } from "./LoginForm";

describe("LoginForm", () => {
  it("logs in and navigates home on success", async () => {
    login.mockResolvedValueOnce(undefined);
    render(<MemoryRouter><LoginForm /></MemoryRouter>);
    await userEvent.type(screen.getByLabelText(/email/i), "a@b.c");
    await userEvent.type(screen.getByLabelText(/password/i), "pw");
    await userEvent.click(screen.getByRole("button", { name: /sign in/i }));
    await waitFor(() => expect(navigate).toHaveBeenCalledWith("/"));
  });

  it("shows an error on 401", async () => {
    login.mockRejectedValueOnce(new ApiError(401, "Invalid credentials"));
    render(<MemoryRouter><LoginForm /></MemoryRouter>);
    await userEvent.type(screen.getByLabelText(/email/i), "a@b.c");
    await userEvent.type(screen.getByLabelText(/password/i), "bad");
    await userEvent.click(screen.getByRole("button", { name: /sign in/i }));
    await waitFor(() =>
      expect(screen.getByText(/invalid email or password/i)).toBeInTheDocument()
    );
  });
});

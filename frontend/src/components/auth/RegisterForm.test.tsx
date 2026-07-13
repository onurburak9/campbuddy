import { describe, it, expect, vi, beforeEach } from "vitest";
import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { MemoryRouter } from "react-router-dom";
import { ApiError } from "../../api/client";

const register = vi.fn();
const navigate = vi.fn();
vi.mock("../../contexts/AuthContext", () => ({ useAuth: () => ({ register }) }));
vi.mock("react-router-dom", async (orig) => ({
  ...(await orig<typeof import("react-router-dom")>()),
  useNavigate: () => navigate,
}));

import { RegisterForm } from "./RegisterForm";

describe("RegisterForm", () => {
  beforeEach(() => {
    register.mockClear();
    navigate.mockClear();
  });

  it("registers and navigates home on success", async () => {
    register.mockResolvedValueOnce(undefined);
    render(<MemoryRouter><RegisterForm /></MemoryRouter>);
    await userEvent.type(screen.getByLabelText(/^email/i), "a@b.c");
    await userEvent.type(screen.getByLabelText(/^password/i), "longenough");
    await userEvent.type(screen.getByLabelText(/confirm password/i), "longenough");
    await userEvent.click(screen.getByRole("button", { name: /create account/i }));
    await waitFor(() => expect(navigate).toHaveBeenCalledWith("/"));
  });

  it("shows an error when passwords don't match, without calling register", async () => {
    render(<MemoryRouter><RegisterForm /></MemoryRouter>);
    await userEvent.type(screen.getByLabelText(/^email/i), "a@b.c");
    await userEvent.type(screen.getByLabelText(/^password/i), "longenough");
    await userEvent.type(screen.getByLabelText(/confirm password/i), "different");
    await userEvent.click(screen.getByRole("button", { name: /create account/i }));
    await waitFor(() => expect(screen.getByText(/passwords do not match/i)).toBeInTheDocument());
    expect(register).not.toHaveBeenCalled();
  });

  it("shows an error on 409 duplicate email", async () => {
    register.mockRejectedValueOnce(new ApiError(409, "Email already in use"));
    render(<MemoryRouter><RegisterForm /></MemoryRouter>);
    await userEvent.type(screen.getByLabelText(/^email/i), "a@b.c");
    await userEvent.type(screen.getByLabelText(/^password/i), "longenough");
    await userEvent.type(screen.getByLabelText(/confirm password/i), "longenough");
    await userEvent.click(screen.getByRole("button", { name: /create account/i }));
    await waitFor(() => expect(screen.getByText(/email already in use/i)).toBeInTheDocument());
  });

  it("shows an error on 403 when registration is disabled", async () => {
    register.mockRejectedValueOnce(new ApiError(403, "Registration is currently disabled"));
    render(<MemoryRouter><RegisterForm /></MemoryRouter>);
    await userEvent.type(screen.getByLabelText(/^email/i), "a@b.c");
    await userEvent.type(screen.getByLabelText(/^password/i), "longenough");
    await userEvent.type(screen.getByLabelText(/confirm password/i), "longenough");
    await userEvent.click(screen.getByRole("button", { name: /create account/i }));
    await waitFor(() => expect(screen.getByText(/registration is currently disabled/i)).toBeInTheDocument());
  });
});

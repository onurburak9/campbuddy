import { describe, it, expect, vi, beforeEach } from "vitest";
import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { MemoryRouter } from "react-router-dom";
import { ApiError } from "../../api/client";

const resetPassword = vi.fn();
const navigate = vi.fn();
vi.mock("../../contexts/AuthContext", () => ({ useAuth: () => ({ resetPassword }) }));
vi.mock("react-router-dom", async (orig) => ({
  ...(await orig<typeof import("react-router-dom")>()),
  useNavigate: () => navigate,
  useSearchParams: () => [new URLSearchParams("token=abc123")],
}));

import { ResetPasswordForm } from "./ResetPasswordForm";

describe("ResetPasswordForm", () => {
  beforeEach(() => {
    resetPassword.mockClear();
    navigate.mockClear();
  });

  it("resets the password and navigates home on success", async () => {
    resetPassword.mockResolvedValueOnce(undefined);
    render(<MemoryRouter><ResetPasswordForm /></MemoryRouter>);
    await userEvent.type(screen.getByLabelText(/^new password/i), "longenough");
    await userEvent.type(screen.getByLabelText(/confirm password/i), "longenough");
    await userEvent.click(screen.getByRole("button", { name: /reset password/i }));
    await waitFor(() => expect(navigate).toHaveBeenCalledWith("/"));
    expect(resetPassword).toHaveBeenCalledWith("abc123", "longenough");
  });

  it("shows an error when passwords don't match, without calling resetPassword", async () => {
    render(<MemoryRouter><ResetPasswordForm /></MemoryRouter>);
    await userEvent.type(screen.getByLabelText(/^new password/i), "longenough");
    await userEvent.type(screen.getByLabelText(/confirm password/i), "different");
    await userEvent.click(screen.getByRole("button", { name: /reset password/i }));
    await waitFor(() => expect(screen.getByText(/passwords do not match/i)).toBeInTheDocument());
    expect(resetPassword).not.toHaveBeenCalled();
  });

  it("shows an error with a link to request a new one on 400 invalid/expired token", async () => {
    resetPassword.mockRejectedValueOnce(new ApiError(400, "Invalid or expired reset link"));
    render(<MemoryRouter><ResetPasswordForm /></MemoryRouter>);
    await userEvent.type(screen.getByLabelText(/^new password/i), "longenough");
    await userEvent.type(screen.getByLabelText(/confirm password/i), "longenough");
    await userEvent.click(screen.getByRole("button", { name: /reset password/i }));
    await waitFor(() => expect(screen.getByText(/invalid or expired reset link/i)).toBeInTheDocument());
    expect(screen.getByText(/request a new link/i)).toBeInTheDocument();
  });
});

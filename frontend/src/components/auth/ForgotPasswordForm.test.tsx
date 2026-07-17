import { describe, it, expect, vi } from "vitest";
import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { MemoryRouter } from "react-router-dom";

const forgotPassword = vi.fn();
vi.mock("../../api/auth", () => ({
  auth: { forgotPassword: (...args: unknown[]) => forgotPassword(...args) },
}));

import { ForgotPasswordForm } from "./ForgotPasswordForm";

describe("ForgotPasswordForm", () => {
  it("shows a check-your-email message on submit", async () => {
    forgotPassword.mockResolvedValueOnce(undefined);
    render(<MemoryRouter><ForgotPasswordForm /></MemoryRouter>);
    await userEvent.type(screen.getByLabelText(/email/i), "a@b.c");
    await userEvent.click(screen.getByRole("button", { name: /send reset link/i }));
    await waitFor(() => expect(screen.getByText(/check your email/i)).toBeInTheDocument());
    expect(forgotPassword).toHaveBeenCalledWith("a@b.c");
  });

  it("shows the same check-your-email message even for an unknown address", async () => {
    forgotPassword.mockResolvedValueOnce(undefined);
    render(<MemoryRouter><ForgotPasswordForm /></MemoryRouter>);
    await userEvent.type(screen.getByLabelText(/email/i), "ghost@b.c");
    await userEvent.click(screen.getByRole("button", { name: /send reset link/i }));
    await waitFor(() => expect(screen.getByText(/check your email/i)).toBeInTheDocument());
  });
});

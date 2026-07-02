import { describe, it, expect, vi } from "vitest";
import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { MemoryRouter } from "react-router-dom";

const toggle = vi.fn();
vi.mock("../../contexts/ThemeContext", () => ({ useTheme: () => ({ theme: "light", toggle }) }));
vi.mock("../../contexts/AuthContext", () => ({ useAuth: () => ({ logout: vi.fn(), user: { email: "a@b.c" } }) }));

import { IconSidebar } from "./IconSidebar";

describe("IconSidebar", () => {
  it("toggles theme when the theme button is clicked", async () => {
    render(<MemoryRouter><IconSidebar onOpenScans={vi.fn()} /></MemoryRouter>);
    await userEvent.click(screen.getByRole("button", { name: /theme/i }));
    expect(toggle).toHaveBeenCalledOnce();
  });

  it("closes on backdrop click when open", async () => {
    const onClose = vi.fn();
    render(<MemoryRouter><IconSidebar onOpenScans={vi.fn()} open onClose={onClose} /></MemoryRouter>);
    await userEvent.click(screen.getByTestId("sidebar-backdrop"));
    expect(onClose).toHaveBeenCalledOnce();
  });

  it("closes on Escape when open", async () => {
    const onClose = vi.fn();
    render(<MemoryRouter><IconSidebar onOpenScans={vi.fn()} open onClose={onClose} /></MemoryRouter>);
    await userEvent.keyboard("{Escape}");
    expect(onClose).toHaveBeenCalledOnce();
  });

  it("closes when a nav item is selected", async () => {
    const onClose = vi.fn();
    render(<MemoryRouter><IconSidebar onOpenScans={vi.fn()} open onClose={onClose} /></MemoryRouter>);
    await userEvent.click(screen.getByRole("link", { name: /settings/i }));
    expect(onClose).toHaveBeenCalledOnce();
  });
});

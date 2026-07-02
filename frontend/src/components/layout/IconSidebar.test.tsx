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

  it("moves focus into the drawer when it opens", () => {
    const { rerender } = render(
      <MemoryRouter>
        <button>Trigger</button>
        <IconSidebar onOpenScans={vi.fn()} open={false} onClose={vi.fn()} />
      </MemoryRouter>
    );
    rerender(
      <MemoryRouter>
        <button>Trigger</button>
        <IconSidebar onOpenScans={vi.fn()} open onClose={vi.fn()} />
      </MemoryRouter>
    );
    expect(document.activeElement).toBe(screen.getByRole("link", { name: /scans/i }));
  });

  it("restores focus to the previously-focused trigger when it closes", () => {
    const { rerender } = render(
      <MemoryRouter>
        <button>Trigger</button>
        <IconSidebar onOpenScans={vi.fn()} open={false} onClose={vi.fn()} />
      </MemoryRouter>
    );
    const trigger = screen.getByRole("button", { name: "Trigger" });
    trigger.focus();
    expect(document.activeElement).toBe(trigger);

    rerender(
      <MemoryRouter>
        <button>Trigger</button>
        <IconSidebar onOpenScans={vi.fn()} open onClose={vi.fn()} />
      </MemoryRouter>
    );
    expect(document.activeElement).not.toBe(trigger);

    rerender(
      <MemoryRouter>
        <button>Trigger</button>
        <IconSidebar onOpenScans={vi.fn()} open={false} onClose={vi.fn()} />
      </MemoryRouter>
    );
    expect(document.activeElement).toBe(trigger);
  });

  it("traps Tab within the drawer while open, wrapping at both ends", async () => {
    const user = userEvent.setup();
    render(<MemoryRouter><IconSidebar onOpenScans={vi.fn()} open onClose={vi.fn()} /></MemoryRouter>);

    const scansLink = screen.getByRole("link", { name: /scans/i });
    const logoutButton = screen.getByRole("button", { name: /log out/i });

    expect(document.activeElement).toBe(scansLink);

    await user.tab({ shift: true });
    expect(document.activeElement).toBe(logoutButton);

    await user.tab();
    expect(document.activeElement).toBe(scansLink);
  });
});

import { describe, it, expect, vi, afterEach } from "vitest";
import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { MemoryRouter } from "react-router-dom";

const mockUser = vi.fn((): { email: string; scan_limit: number; scans_used: number } => ({
  email: "a@b.c", scan_limit: 5, scans_used: 1,
}));
vi.mock("../../contexts/AuthContext", () => ({ useAuth: () => ({ user: mockUser() }) }));

import { MobileTopBar } from "./MobileTopBar";

function renderBar(props: React.ComponentProps<typeof MobileTopBar>) {
  return render(<MemoryRouter><MobileTopBar {...props} /></MemoryRouter>);
}

afterEach(() => {
  mockUser.mockReturnValue({ email: "a@b.c", scan_limit: 5, scans_used: 1 });
});

describe("MobileTopBar", () => {
  it("list mode: shows hamburger + new-scan and fires their handlers", async () => {
    const onOpenSidebar = vi.fn();
    const onNewScan = vi.fn();
    renderBar({ title: "Scans", onOpenSidebar, onNewScan });

    expect(screen.queryByRole("button", { name: /back to scans/i })).not.toBeInTheDocument();
    await userEvent.click(screen.getByRole("button", { name: /open menu/i }));
    expect(onOpenSidebar).toHaveBeenCalledOnce();
    await userEvent.click(screen.getByRole("button", { name: /new scan/i }));
    expect(onNewScan).toHaveBeenCalledOnce();
  });

  it("detail mode: shows back button (no hamburger) and fires onBack", async () => {
    const onBack = vi.fn();
    renderBar({ title: "Scans", onBack });

    expect(screen.queryByRole("button", { name: /open menu/i })).not.toBeInTheDocument();
    await userEvent.click(screen.getByRole("button", { name: /back to scans/i }));
    expect(onBack).toHaveBeenCalledOnce();
  });

  it("shows scan usage next to the title", () => {
    renderBar({ title: "Scans", onOpenSidebar: vi.fn(), onNewScan: vi.fn() });
    expect(screen.getByText("1/5")).toBeInTheDocument();
  });

  it("disables new-scan when at the scan limit", () => {
    mockUser.mockReturnValue({ email: "a@b.c", scan_limit: 5, scans_used: 5 });
    renderBar({ title: "Scans", onOpenSidebar: vi.fn(), onNewScan: vi.fn() });
    expect(screen.getByRole("button", { name: /new scan/i })).toBeDisabled();
  });

  it("renders a feedback trigger next to the title in both list and detail mode", async () => {
    const { unmount } = renderBar({ title: "Scans", onOpenSidebar: vi.fn(), onNewScan: vi.fn() });
    await userEvent.click(screen.getByRole("button", { name: /send feedback/i }));
    expect(screen.getByRole("heading", { name: /send feedback/i })).toBeInTheDocument();
    unmount();

    renderBar({ title: "Scans", onBack: vi.fn() });
    expect(screen.getByRole("button", { name: /send feedback/i })).toBeInTheDocument();
  });
});

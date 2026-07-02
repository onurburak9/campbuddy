import { describe, it, expect, vi } from "vitest";
import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { MobileTopBar } from "./MobileTopBar";

describe("MobileTopBar", () => {
  it("list mode: shows hamburger + new-scan and fires their handlers", async () => {
    const onOpenSidebar = vi.fn();
    const onNewScan = vi.fn();
    render(<MobileTopBar title="Scans" onOpenSidebar={onOpenSidebar} onNewScan={onNewScan} />);

    expect(screen.queryByRole("button", { name: /back to scans/i })).not.toBeInTheDocument();
    await userEvent.click(screen.getByRole("button", { name: /open menu/i }));
    expect(onOpenSidebar).toHaveBeenCalledOnce();
    await userEvent.click(screen.getByRole("button", { name: /new scan/i }));
    expect(onNewScan).toHaveBeenCalledOnce();
  });

  it("detail mode: shows back button (no hamburger) and fires onBack", async () => {
    const onBack = vi.fn();
    render(<MobileTopBar title="Scans" onBack={onBack} />);

    expect(screen.queryByRole("button", { name: /open menu/i })).not.toBeInTheDocument();
    await userEvent.click(screen.getByRole("button", { name: /back to scans/i }));
    expect(onBack).toHaveBeenCalledOnce();
  });
});

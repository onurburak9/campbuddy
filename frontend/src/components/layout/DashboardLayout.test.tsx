import { describe, it, expect, vi } from "vitest";
import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { MemoryRouter } from "react-router-dom";

vi.mock("./IconSidebar", () => ({ IconSidebar: () => <div data-testid="sidebar" /> }));
vi.mock("./ScanListPanel", () => ({
  ScanListPanel: ({ onSelect, onNewScan }: { onSelect: (id: number) => void; onNewScan: () => void }) => (
    <div>
      <button onClick={() => onSelect(7)}>select-scan</button>
      <button onClick={onNewScan}>list-plus</button>
    </div>
  ),
}));
vi.mock("../scans/ScanDetailPanel", () => ({ ScanDetailPanel: () => <div>detail-panel</div> }));
vi.mock("../scans/WelcomePanel", () => ({ WelcomePanel: () => <div>welcome-panel</div> }));
vi.mock("../wizard/ScanWizardPanel", () => ({ ScanWizardPanel: () => <div>wizard-panel</div> }));

import { DashboardLayout } from "./DashboardLayout";

const renderLayout = () => render(<MemoryRouter><DashboardLayout /></MemoryRouter>);

describe("DashboardLayout mobile collapse", () => {
  it("shows the hamburger initially and swaps to back after selecting a scan", async () => {
    renderLayout();
    expect(screen.getByRole("button", { name: /open menu/i })).toBeInTheDocument();
    expect(screen.queryByRole("button", { name: /back to scans/i })).not.toBeInTheDocument();

    await userEvent.click(screen.getByRole("button", { name: "select-scan" }));
    expect(screen.getByRole("button", { name: /back to scans/i })).toBeInTheDocument();
    expect(screen.queryByRole("button", { name: /open menu/i })).not.toBeInTheDocument();
  });

  it("returns to the list when back is clicked", async () => {
    renderLayout();
    await userEvent.click(screen.getByRole("button", { name: "select-scan" }));
    await userEvent.click(screen.getByRole("button", { name: /back to scans/i }));
    expect(screen.getByRole("button", { name: /open menu/i })).toBeInTheDocument();
  });

  it("opens the wizard from the top-bar new-scan button", async () => {
    renderLayout();
    await userEvent.click(screen.getByRole("button", { name: /new scan/i }));
    expect(screen.getByText("wizard-panel")).toBeInTheDocument();
    expect(screen.getByRole("button", { name: /back to scans/i })).toBeInTheDocument();
  });
});

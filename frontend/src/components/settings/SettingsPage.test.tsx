import { describe, it, expect, vi } from "vitest";
import { render, screen } from "@testing-library/react";
import { MemoryRouter } from "react-router-dom";

vi.mock("../layout/IconSidebar", () => ({ IconSidebar: () => <div data-testid="sidebar" /> }));
vi.mock("./ProfileForm", () => ({ ProfileForm: () => <div>profile-form</div> }));

import { SettingsPage } from "./SettingsPage";

describe("SettingsPage", () => {
  it("renders a mobile header with a hamburger and the Settings title", () => {
    render(<MemoryRouter><SettingsPage /></MemoryRouter>);
    expect(screen.getByRole("button", { name: /open menu/i })).toBeInTheDocument();
    expect(screen.getByText("Settings")).toBeInTheDocument();
    expect(screen.getByText("profile-form")).toBeInTheDocument();
  });
});

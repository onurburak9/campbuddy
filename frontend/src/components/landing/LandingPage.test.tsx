import { describe, it, expect } from "vitest";
import { render, screen, within } from "@testing-library/react";
import { MemoryRouter } from "react-router-dom";
import { LandingPage } from "./LandingPage";
import { PrivacyPage } from "./PrivacyPage";
import { COMPANY, FAQ, ROADMAP, STEPS } from "./content";

function renderIn(ui: React.ReactElement) {
  return render(<MemoryRouter>{ui}</MemoryRouter>);
}

describe("LandingPage", () => {
  it("points every signup CTA at /register and the nav at /login", () => {
    renderIn(<LandingPage />);
    const signups = screen.getAllByRole("link", { name: /start a (free )?scan/i });
    expect(signups.length).toBeGreaterThanOrEqual(3);
    signups.forEach((a) => expect(a).toHaveAttribute("href", "/register"));
    const nav = screen.getByRole("navigation", { name: "Main" });
    expect(within(nav).getByRole("link", { name: "Log in" })).toHaveAttribute("href", "/login");
  });

  it("renders every how-it-works step, roadmap item and FAQ", () => {
    renderIn(<LandingPage />);
    STEPS.forEach((s) => expect(screen.getByRole("heading", { name: s.title })).toBeInTheDocument());
    ROADMAP.forEach((r) => expect(screen.getByRole("heading", { name: r.title })).toBeInTheDocument());
    FAQ.forEach((f) => expect(screen.getByText(f.q)).toBeInTheDocument());
  });

  it("labels unbuilt AI features as not live", () => {
    renderIn(<LandingPage />);
    expect(screen.getAllByText("In development").length).toBeGreaterThan(0);
    expect(screen.getByText("Planned")).toBeInTheDocument();
    expect(screen.getByText(/concept previews · not live yet/i)).toBeInTheDocument();
  });

  it("credits the company with a contact email and privacy link in the footer", () => {
    renderIn(<LandingPage />);
    const footer = screen.getByRole("contentinfo");
    expect(within(footer).getByRole("link", { name: COMPANY.email })).toHaveAttribute("href", `mailto:${COMPANY.email}`);
    expect(within(footer).getByRole("link", { name: "Privacy" })).toHaveAttribute("href", "/privacy");
  });
});

describe("PrivacyPage", () => {
  it("renders the policy with a contact address", () => {
    renderIn(<PrivacyPage />);
    expect(screen.getByRole("heading", { level: 1, name: "Privacy policy" })).toBeInTheDocument();
    expect(screen.getByRole("heading", { name: "What we collect" })).toBeInTheDocument();
    expect(screen.getAllByRole("link", { name: COMPANY.email }).length).toBeGreaterThan(0);
  });
});

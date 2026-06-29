import { describe, it, expect, beforeEach } from "vitest";
import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { ThemeProvider, useTheme } from "./ThemeContext";

function Probe() {
  const { theme, toggle } = useTheme();
  return <button onClick={toggle}>theme:{theme}</button>;
}

describe("ThemeContext", () => {
  beforeEach(() => localStorage.clear());

  it("defaults to light and toggles to dark, applying the dark class", async () => {
    render(<ThemeProvider><Probe /></ThemeProvider>);
    expect(screen.getByText("theme:light")).toBeInTheDocument();
    await userEvent.click(screen.getByRole("button"));
    expect(screen.getByText("theme:dark")).toBeInTheDocument();
    expect(document.documentElement.classList.contains("dark")).toBe(true);
    expect(localStorage.getItem("theme")).toBe("dark");
  });
});

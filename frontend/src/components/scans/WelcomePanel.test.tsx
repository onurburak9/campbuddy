import { describe, it, expect, vi, beforeEach } from "vitest";
import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";

vi.mock("../../lib/tour");

import { WelcomePanel } from "./WelcomePanel";
import { startWelcomeTour, hasSeenWelcomeTour } from "../../lib/tour";

const startWelcomeTourMock = vi.mocked(startWelcomeTour);
const hasSeenWelcomeTourMock = vi.mocked(hasSeenWelcomeTour);

describe("WelcomePanel", () => {
  beforeEach(() => {
    startWelcomeTourMock.mockClear();
    hasSeenWelcomeTourMock.mockClear();
  });

  it("auto-starts the tour on mount when it hasn't been seen", () => {
    hasSeenWelcomeTourMock.mockReturnValue(false);
    render(<WelcomePanel />);
    expect(startWelcomeTourMock).toHaveBeenCalledTimes(1);
  });

  it("does not auto-start the tour on mount when it has already been seen", () => {
    hasSeenWelcomeTourMock.mockReturnValue(true);
    render(<WelcomePanel />);
    expect(startWelcomeTourMock).not.toHaveBeenCalled();
  });

  it("replays the tour when 'Take the tour' is clicked, regardless of seen state", async () => {
    hasSeenWelcomeTourMock.mockReturnValue(true);
    render(<WelcomePanel />);
    await userEvent.click(screen.getByRole("button", { name: /take the tour/i }));
    expect(startWelcomeTourMock).toHaveBeenCalledTimes(1);
  });
});

import { describe, it, expect } from "vitest";
import { render, screen } from "@testing-library/react";
import { NotificationsFields } from "./ScanForm";
import type { ScanFormState } from "./useScanFormState";

function makeState(pollingInterval: number): ScanFormState {
  return {
    name: "",
    provider: "RecreationDotGov",
    recAreaIds: "",
    campgroundIds: "",
    campsiteIds: "",
    windows: [],
    nights: 1,
    daysOfWeek: [],
    weekendsOnly: false,
    pollingInterval,
    notifyEmail: true,
    notifyTelegram: false,
    notifyNewOnly: true,
  };
}

const noop = () => {};

describe("NotificationsFields — polling interval options", () => {
  it("shows the seven curated options when pollingInterval is 300 (default)", () => {
    render(
      <NotificationsFields state={makeState(300)} set={noop as any} telegramAvailable={true} />,
    );

    expect(screen.getByRole("option", { name: "5 min" })).toBeInTheDocument();
    expect(screen.getByRole("option", { name: "15 min" })).toBeInTheDocument();
    expect(screen.getByRole("option", { name: "30 min" })).toBeInTheDocument();
    expect(screen.getByRole("option", { name: "45 min" })).toBeInTheDocument();
    expect(screen.getByRole("option", { name: "1 hour" })).toBeInTheDocument();
    expect(screen.getByRole("option", { name: "2 hours" })).toBeInTheDocument();
    expect(screen.getByRole("option", { name: "6 hours" })).toBeInTheDocument();

    // Intervals not in the curated list should NOT be present
    expect(screen.queryByRole("option", { name: "1 min" })).not.toBeInTheDocument();
    expect(screen.queryByRole("option", { name: "10 min" })).not.toBeInTheDocument();
  });

  it("prepends a legacy option when pollingInterval is not in the curated list (e.g. 600s → '10 min')", () => {
    render(
      <NotificationsFields state={makeState(600)} set={noop as any} telegramAvailable={true} />,
    );

    // Legacy value is present as an extra option
    expect(screen.getByRole("option", { name: "10 min" })).toBeInTheDocument();

    // Curated options are still all present
    expect(screen.getByRole("option", { name: "5 min" })).toBeInTheDocument();
    expect(screen.getByRole("option", { name: "15 min" })).toBeInTheDocument();
    expect(screen.getByRole("option", { name: "30 min" })).toBeInTheDocument();
    expect(screen.getByRole("option", { name: "45 min" })).toBeInTheDocument();
    expect(screen.getByRole("option", { name: "1 hour" })).toBeInTheDocument();
    expect(screen.getByRole("option", { name: "2 hours" })).toBeInTheDocument();
    expect(screen.getByRole("option", { name: "6 hours" })).toBeInTheDocument();
  });
});

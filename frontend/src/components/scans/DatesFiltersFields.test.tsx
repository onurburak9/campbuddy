import { useState } from "react";
import { describe, it, expect, vi, beforeEach, afterEach } from "vitest";
import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { DatesFiltersFields } from "./DatesFiltersFields";
import type { ScanFormState } from "./useScanFormState";

function makeState(): ScanFormState {
  return {
    name: "",
    provider: "RecreationDotGov",
    recAreaIds: [],
    campgroundIds: [],
    campsiteIds: [],
    windows: [],
    nights: 1,
    daysOfWeek: [],
    weekendsOnly: false,
    pollingInterval: 300,
    notifyEmail: true,
    notifyTelegram: false,
    notifyNewOnly: true,
  };
}

function ControlledDatesFilters({ initial }: { initial: Partial<ScanFormState> }) {
  const [state, setState] = useState<ScanFormState>({ ...makeState(), ...initial });
  const set = <K extends keyof ScanFormState>(key: K, value: ScanFormState[K]) =>
    setState((prev) => ({ ...prev, [key]: value }));
  return <DatesFiltersFields state={state} set={set} />;
}

describe("DatesFiltersFields — consecutive nights input", () => {
  it("allows clearing the field to empty instead of snapping back to 1 on every keystroke", async () => {
    const user = userEvent.setup();
    render(<ControlledDatesFilters initial={{ nights: 3 }} />);
    const input = screen.getByLabelText("Consecutive nights") as HTMLInputElement;

    await user.clear(input);

    expect(input.value).toBe("");
  });

  it("resets an empty field back to 1 on blur", async () => {
    const user = userEvent.setup();
    render(<ControlledDatesFilters initial={{ nights: 3 }} />);
    const input = screen.getByLabelText("Consecutive nights") as HTMLInputElement;

    await user.clear(input);
    await user.tab();

    expect(input.value).toBe("1");
  });

  it("shows a validation message when nights exceeds the shortest search window", () => {
    render(
      <ControlledDatesFilters
        initial={{
          nights: 5,
          windows: [{ start_date: "2026-07-03", end_date: "2026-07-06" }],
        }}
      />,
    );

    expect(screen.getByText(/can't be longer than the shortest search window/i)).toBeInTheDocument();
  });

  it("does not show a validation message when nights fits within the window", () => {
    render(
      <ControlledDatesFilters
        initial={{
          nights: 3,
          windows: [{ start_date: "2026-07-03", end_date: "2026-07-06" }],
        }}
      />,
    );

    expect(screen.queryByText(/can't be longer than the shortest search window/i)).not.toBeInTheDocument();
  });
});

describe("DatesFiltersFields — quick-pick date templates", () => {
  // Sun 20 Sep 2026. Fridays that month: 4, 11, 18, 25.
  beforeEach(() => {
    vi.useFakeTimers({ toFake: ["Date"] });
    vi.setSystemTime(new Date(2026, 8, 20, 12));
  });
  afterEach(() => vi.useRealTimers());

  const dateValues = (container: HTMLElement) =>
    Array.from(container.querySelectorAll<HTMLInputElement>('input[type="date"]')).map((i) => i.value);

  it("fills one Friday-to-Sunday window from 'Next weekend', skipping the weekend in progress", async () => {
    const user = userEvent.setup();
    const { container } = render(<ControlledDatesFilters initial={{}} />);

    await user.click(screen.getByRole("button", { name: "Next weekend" }));

    expect(dateValues(container)).toEqual(["2026-09-25", "2026-09-27"]);
  });

  it("fills two windows from 'Next 2 weekends'", async () => {
    const user = userEvent.setup();
    const { container } = render(<ControlledDatesFilters initial={{}} />);

    await user.click(screen.getByRole("button", { name: "Next 2 weekends" }));

    expect(dateValues(container)).toEqual(["2026-09-25", "2026-09-27", "2026-10-02", "2026-10-04"]);
  });

  it("spans the selected month end to end without enabling weekends-only", async () => {
    const user = userEvent.setup();
    const { container } = render(<ControlledDatesFilters initial={{}} />);

    await user.selectOptions(screen.getByLabelText("Month"), "2026-10");
    await user.click(screen.getByRole("button", { name: "All of October" }));

    expect(dateValues(container)).toEqual(["2026-10-01", "2026-10-31"]);
    expect(screen.getByRole("switch", { name: "Weekends only" })).toHaveAttribute("aria-checked", "false");
  });

  it("turns on weekends-only and two nights for 'Weekends in <month>'", async () => {
    const user = userEvent.setup();
    const { container } = render(<ControlledDatesFilters initial={{}} />);

    await user.selectOptions(screen.getByLabelText("Month"), "2026-10");
    await user.click(screen.getByRole("button", { name: "Weekends in October" }));

    expect(dateValues(container)).toEqual(["2026-10-01", "2026-10-31"]);
    expect(screen.getByRole("switch", { name: "Weekends only" })).toHaveAttribute("aria-checked", "true");
    expect(screen.getByLabelText("Consecutive nights")).toHaveValue(2);
  });

  it("clamps the current month to today so a template never emits a past date", async () => {
    const user = userEvent.setup();
    const { container } = render(<ControlledDatesFilters initial={{}} />);

    await user.click(screen.getByRole("button", { name: "All of September" }));

    expect(dateValues(container)).toEqual(["2026-09-20", "2026-09-30"]);
  });

  it("replaces existing windows and filters instead of appending to them", async () => {
    const user = userEvent.setup();
    const { container } = render(
      <ControlledDatesFilters
        initial={{
          windows: [{ start_date: "2026-12-01", end_date: "2026-12-05" }],
          weekendsOnly: true,
          nights: 4,
          daysOfWeek: [0, 1],
        }}
      />,
    );

    await user.click(screen.getByRole("button", { name: "Next weekend" }));

    expect(dateValues(container)).toEqual(["2026-09-25", "2026-09-27"]);
    expect(screen.getByRole("switch", { name: "Weekends only" })).toHaveAttribute("aria-checked", "false");
    expect(screen.getByLabelText("Consecutive nights")).toHaveValue(2);
  });

  it("leaves a generated window editable afterwards", async () => {
    const user = userEvent.setup();
    const { container } = render(<ControlledDatesFilters initial={{}} />);

    await user.click(screen.getByRole("button", { name: "Next weekend" }));
    const [start] = Array.from(container.querySelectorAll<HTMLInputElement>('input[type="date"]'));
    await user.clear(start);
    await user.type(start, "2026-09-24");

    expect(dateValues(container)).toEqual(["2026-09-24", "2026-09-27"]);
  });
});

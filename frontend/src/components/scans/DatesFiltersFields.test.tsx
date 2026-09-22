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
    equipmentTypes: [],
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
    const input = screen.getByLabelText(/consecutive nights/i) as HTMLInputElement;

    await user.clear(input);

    expect(input.value).toBe("");
  });

  it("resets an empty field back to 1 on blur", async () => {
    const user = userEvent.setup();
    render(<ControlledDatesFilters initial={{ nights: 3 }} />);
    const input = screen.getByLabelText(/consecutive nights/i) as HTMLInputElement;

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

  // Each window's trigger button carries its current start/end as data
  // attributes (see WindowRangePicker) since there's no plain <input> to read.
  const dateValues = (container: HTMLElement) =>
    Array.from(container.querySelectorAll<HTMLButtonElement>("[data-start-date]")).flatMap((b) => [
      b.dataset.startDate ?? "",
      b.dataset.endDate ?? "",
    ]);

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

    expect(dateValues(container)).toEqual(["2026-10-01", "2026-11-01"]);
    expect(screen.getByRole("switch", { name: "Weekends only" })).toHaveAttribute("aria-checked", "false");
  });

  it("turns on weekends-only and two nights for 'Weekends in <month>'", async () => {
    const user = userEvent.setup();
    const { container } = render(<ControlledDatesFilters initial={{}} />);

    await user.selectOptions(screen.getByLabelText("Month"), "2026-10");
    await user.click(screen.getByRole("button", { name: "Weekends in October" }));

    expect(dateValues(container)).toEqual(["2026-10-01", "2026-11-01"]);
    expect(screen.getByRole("switch", { name: "Weekends only" })).toHaveAttribute("aria-checked", "true");
    expect(screen.getByLabelText(/consecutive nights/i)).toHaveValue(2);
  });

  it("clamps the current month to today so a template never emits a past date", async () => {
    const user = userEvent.setup();
    const { container } = render(<ControlledDatesFilters initial={{}} />);

    await user.click(screen.getByRole("button", { name: "All of September" }));

    expect(dateValues(container)).toEqual(["2026-09-20", "2026-10-01"]);
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
    expect(screen.getByLabelText(/consecutive nights/i)).toHaveValue(2);
  });

  it("leaves a generated window editable afterwards", async () => {
    const user = userEvent.setup();
    const { container } = render(<ControlledDatesFilters initial={{}} />);

    await user.click(screen.getByRole("button", { name: "Next weekend" }));
    await user.click(screen.getByRole("button", { name: "Search dates" }));
    await user.click(screen.getByRole("button", { name: /^September 24, 2026$/ }));
    await user.click(screen.getByRole("button", { name: /^September 30, 2026$/ }));

    expect(dateValues(container)).toEqual(["2026-09-24", "2026-09-30"]);
  });
});

describe("DatesFiltersFields — search summary and window labels", () => {
  beforeEach(() => {
    vi.useFakeTimers({ toFake: ["Date"] });
    vi.setSystemTime(new Date(2026, 8, 20, 12));
  });
  afterEach(() => vi.useRealTimers());

  it("prompts rather than going blank until a window is complete", () => {
    render(<ControlledDatesFilters initial={{}} />);
    expect(screen.getByTestId("search-summary")).toHaveTextContent(/pick|add/i);
  });

  it("summarises a month template in nights, never showing the exclusive end date", async () => {
    const user = userEvent.setup();
    render(<ControlledDatesFilters initial={{}} />);

    await user.selectOptions(screen.getByLabelText("Month"), "2026-10");
    await user.click(screen.getByRole("button", { name: "All of October" }));

    const summary = screen.getByTestId("search-summary");
    expect(summary).toHaveTextContent("Any 1 night between Oct 1 and Oct 31, 2026");
    expect(summary).not.toHaveTextContent("Nov");
  });

  it("keeps the summary in step when the nights preference is edited afterwards", async () => {
    const user = userEvent.setup();
    render(<ControlledDatesFilters initial={{}} />);

    await user.selectOptions(screen.getByLabelText("Month"), "2026-10");
    await user.click(screen.getByRole("button", { name: "All of October" }));
    const nights = screen.getByLabelText(/consecutive nights/i);
    await user.clear(nights);
    await user.type(nights, "3");

    expect(screen.getByTestId("search-summary")).toHaveTextContent("Any 3 nights between Oct 1 and Oct 31, 2026");
  });

  it("describes a weekend template as a Fri-Sun weekend", async () => {
    const user = userEvent.setup();
    render(<ControlledDatesFilters initial={{}} />);

    await user.click(screen.getByRole("button", { name: "Next weekend" }));

    expect(screen.getByTestId("search-summary")).toHaveTextContent("2 nights — Sep 25 to Sep 27, 2026");
  });

  it("labels the window dates as a range rather than a booking", async () => {
    const user = userEvent.setup();
    render(<ControlledDatesFilters initial={{}} />);

    await user.click(screen.getByRole("button", { name: "Next weekend" }));

    const trigger = screen.getByRole("button", { name: "Search dates" });
    expect(trigger).toHaveTextContent("Sep 25");
    expect(trigger).toHaveTextContent("Sep 27");
  });
});

describe("DatesFiltersFields — single weekend night template", () => {
  beforeEach(() => {
    vi.useFakeTimers({ toFake: ["Date"] });
    vi.setSystemTime(new Date(2026, 8, 20, 12));
  });
  afterEach(() => vi.useRealTimers());

  it("keeps weekends-only but drops to one night, catching single-night openings", async () => {
    const user = userEvent.setup();
    render(<ControlledDatesFilters initial={{}} />);

    await user.selectOptions(screen.getByLabelText("Month"), "2026-10");
    await user.click(screen.getByRole("button", { name: "Any Fri/Sat night in October" }));

    expect(screen.getByRole("switch", { name: "Weekends only" })).toHaveAttribute("aria-checked", "true");
    expect(screen.getByLabelText(/consecutive nights/i)).toHaveValue(1);
    expect(screen.getByTestId("search-summary")).toHaveTextContent(
      "Any Fri or Sat night between Oct 1 and Oct 31, 2026",
    );
  });
});

describe("DatesFiltersFields — guidance", () => {
  beforeEach(() => {
    vi.useFakeTimers({ toFake: ["Date"] });
    vi.setSystemTime(new Date(2026, 8, 20, 12));
  });
  afterEach(() => vi.useRealTimers());

  it("anchors the three tour stops the dates tour walks through", () => {
    const { container } = render(<ControlledDatesFilters initial={{}} />);
    for (const anchor of ["quick-picks", "search-summary", "nights-field"]) {
      expect(container.querySelector(`[data-tour="${anchor}"]`)).not.toBeNull();
    }
  });

  it("warns on the nights field that a quick pick will overwrite it", () => {
    render(<ControlledDatesFilters initial={{}} />);
    expect(screen.getByTitle(/quick pick/i)).toBeInTheDocument();
    expect(screen.getByTitle(/exactly/i)).toBeInTheDocument();
  });

  it("explains that the end day is checkout, not the last night", () => {
    render(<ControlledDatesFilters initial={{ windows: [{ start_date: "", end_date: "" }] }} />);
    expect(screen.getByText(/checkout|last night/i)).toBeInTheDocument();
  });
});

describe("DatesFiltersFields — equipment types", () => {
  it("toggles an equipment type on click and back off on a second click", async () => {
    const user = userEvent.setup();
    render(<ControlledDatesFilters initial={{}} />);
    const horseButton = screen.getByRole("button", { name: "Horse camping" });

    await user.click(horseButton);
    expect(horseButton).toHaveClass("bg-forest-600");

    await user.click(horseButton);
    expect(horseButton).not.toHaveClass("bg-forest-600");
  });

  it("supports selecting more than one equipment type independently", async () => {
    const user = userEvent.setup();
    render(<ControlledDatesFilters initial={{}} />);

    await user.click(screen.getByRole("button", { name: "Tent" }));
    await user.click(screen.getByRole("button", { name: "RV" }));

    expect(screen.getByRole("button", { name: "Tent" })).toHaveClass("bg-forest-600");
    expect(screen.getByRole("button", { name: "RV" })).toHaveClass("bg-forest-600");
    expect(screen.getByRole("button", { name: "Trailer" })).not.toHaveClass("bg-forest-600");
  });
});

import { useState } from "react";
import { describe, it, expect, vi, beforeEach, afterEach } from "vitest";
import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { WindowRangePicker } from "./WindowRangePicker";
import type { SearchWindow } from "../../types";

function ControlledPicker({
  initial,
  index = 0,
  isFirst = true,
  onRemove = vi.fn(),
}: {
  initial: SearchWindow;
  index?: number;
  isFirst?: boolean;
  onRemove?: () => void;
}) {
  const [w, setW] = useState<SearchWindow>(initial);
  const nights =
    w.start_date && w.end_date
      ? Math.round((new Date(w.end_date).getTime() - new Date(w.start_date).getTime()) / 86_400_000)
      : null;
  return (
    <WindowRangePicker
      window={w}
      index={index}
      isFirst={isFirst}
      nights={nights}
      onChange={(patch) => setW((prev) => ({ ...prev, ...patch }))}
      onRemove={onRemove}
    />
  );
}

describe("WindowRangePicker", () => {
  beforeEach(() => {
    vi.useFakeTimers({ toFake: ["Date"] });
    vi.setSystemTime(new Date(2026, 8, 20, 12)); // Sun 20 Sep 2026
  });
  afterEach(() => vi.useRealTimers());

  it("shows placeholder text and no night count before a range is picked", () => {
    render(<ControlledPicker initial={{ start_date: "", end_date: "" }} />);
    const trigger = screen.getByRole("button", { name: "Search dates" });
    expect(trigger).toHaveTextContent("Search from");
    expect(trigger).toHaveTextContent("Search until");
    expect(trigger).not.toHaveTextContent("night");
  });

  it("opens a two-month calendar and picks a start then end day into a range", async () => {
    const user = userEvent.setup();
    render(<ControlledPicker initial={{ start_date: "", end_date: "" }} />);

    await user.click(screen.getByRole("button", { name: "Search dates" }));
    expect(screen.getByText("September 2026")).toBeInTheDocument();
    expect(screen.getByText("October 2026")).toBeInTheDocument();

    await user.click(screen.getByRole("button", { name: "September 24, 2026" }));
    await user.click(screen.getByRole("button", { name: "September 27, 2026" }));

    const trigger = screen.getByRole("button", { name: "Search dates" });
    expect(trigger).toHaveTextContent("Sep 24");
    expect(trigger).toHaveTextContent("Sep 27");
    expect(trigger).toHaveTextContent("3 nights");
  });

  it("starts a fresh range when clicking again after both ends are set", async () => {
    const user = userEvent.setup();
    render(<ControlledPicker initial={{ start_date: "2026-09-24", end_date: "2026-09-27" }} />);

    await user.click(screen.getByRole("button", { name: "Search dates" }));
    await user.click(screen.getByRole("button", { name: "September 21, 2026" }));

    const trigger = screen.getByRole("button", { name: "Search dates" });
    expect(trigger).toHaveTextContent("Sep 21");
    expect(trigger).toHaveTextContent("Search until");
  });

  it("hides days before today so a past window can't be picked", async () => {
    const user = userEvent.setup();
    render(<ControlledPicker initial={{ start_date: "", end_date: "" }} />);

    await user.click(screen.getByRole("button", { name: "Search dates" }));

    // Past days are rendered invisible with no accessible name, rather than
    // merely disabled, so there's no way to select or announce them.
    expect(screen.queryByRole("button", { name: "September 19, 2026" })).not.toBeInTheDocument();
    expect(screen.getByRole("button", { name: "September 20, 2026" })).toBeEnabled();
  });

  it("clears the range via the Clear button without closing the picker", async () => {
    const user = userEvent.setup();
    render(<ControlledPicker initial={{ start_date: "2026-09-24", end_date: "2026-09-27" }} />);

    await user.click(screen.getByRole("button", { name: "Search dates" }));
    await user.click(screen.getByRole("button", { name: "Clear" }));

    const trigger = screen.getByRole("button", { name: "Search dates" });
    expect(trigger).toHaveTextContent("Search from");
    expect(trigger).toHaveTextContent("Search until");
  });

  it("calls onRemove when Remove window is clicked", async () => {
    const user = userEvent.setup();
    const onRemove = vi.fn();
    render(<ControlledPicker initial={{ start_date: "", end_date: "" }} onRemove={onRemove} />);

    await user.click(screen.getByRole("button", { name: "Search dates" }));
    await user.click(screen.getByRole("button", { name: "Remove window" }));

    expect(onRemove).toHaveBeenCalledOnce();
  });

  it("labels a second window's trigger distinctly for multi-window scans", () => {
    render(<ControlledPicker initial={{ start_date: "", end_date: "" }} index={1} isFirst={false} />);
    expect(screen.getByRole("button", { name: "Search dates (range 2)" })).toBeInTheDocument();
  });
});

import { describe, it, expect, vi } from "vitest";
import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { Toggle } from "./Toggle";

describe("Toggle", () => {
  it("renders with role=switch and aria-checked reflecting the checked prop", () => {
    const onChange = vi.fn();
    const { rerender } = render(<Toggle checked={false} onChange={onChange} label="Email" />);
    const sw = screen.getByRole("switch", { name: /email/i });
    expect(sw).toHaveAttribute("aria-checked", "false");

    rerender(<Toggle checked={true} onChange={onChange} label="Email" />);
    expect(sw).toHaveAttribute("aria-checked", "true");
  });

  it("calls onChange with the negation of checked when clicked", async () => {
    const onChange = vi.fn();
    render(<Toggle checked={false} onChange={onChange} label="Email" />);
    await userEvent.click(screen.getByRole("switch", { name: /email/i }));
    expect(onChange).toHaveBeenCalledOnce();
    expect(onChange).toHaveBeenCalledWith(true);
  });

  it("does not call onChange when disabled", async () => {
    const onChange = vi.fn();
    render(<Toggle checked={false} onChange={onChange} label="Email" disabled />);
    await userEvent.click(screen.getByRole("switch", { name: /email/i }));
    expect(onChange).not.toHaveBeenCalled();
  });
});

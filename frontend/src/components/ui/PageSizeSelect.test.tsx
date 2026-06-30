import { describe, it, expect, vi } from "vitest";
import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { PageSizeSelect } from "./PageSizeSelect";

describe("PageSizeSelect", () => {
  it("renders options and emits a number on change", async () => {
    const onChange = vi.fn();
    render(<PageSizeSelect value={20} onChange={onChange} />);
    await userEvent.selectOptions(screen.getByRole("combobox"), "50");
    expect(onChange).toHaveBeenCalledWith(50);
  });
});

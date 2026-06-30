import { describe, it, expect, vi } from "vitest";
import { render, screen } from "@testing-library/react";
import { Pagination } from "./Pagination";

describe("Pagination", () => {
  it("disables Prev on page 1 and Next when no more pages", () => {
    render(<Pagination page={1} hasNext={false} onPrev={vi.fn()} onNext={vi.fn()} />);
    expect(screen.getByRole("button", { name: /prev/i })).toBeDisabled();
    expect(screen.getByRole("button", { name: /next/i })).toBeDisabled();
  });
});

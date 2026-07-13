import { describe, it, expect, vi } from "vitest";
import { render, screen } from "@testing-library/react";
import { Pagination } from "./Pagination";

describe("Pagination", () => {
  it("disables Prev on page 1 and hides Next when no more pages", () => {
    render(<Pagination page={1} hasNext={false} onPrev={vi.fn()} onNext={vi.fn()} />);
    expect(screen.getByRole("button", { name: /prev/i })).toBeDisabled();
    expect(screen.queryByRole("button", { name: /next/i })).not.toBeInTheDocument();
  });

  it("shows an enabled Next button when there are more pages", () => {
    render(<Pagination page={1} hasNext onPrev={vi.fn()} onNext={vi.fn()} />);
    expect(screen.getByRole("button", { name: /next/i })).toBeEnabled();
  });

  it("shows total pages when provided", () => {
    render(<Pagination page={2} hasNext totalPages={5} onPrev={vi.fn()} onNext={vi.fn()} />);
    expect(screen.getByText("Page 2 of 5")).toBeInTheDocument();
  });

  it("falls back to a bare page number when totalPages is unknown", () => {
    render(<Pagination page={2} hasNext onPrev={vi.fn()} onNext={vi.fn()} />);
    expect(screen.getByText("Page 2")).toBeInTheDocument();
  });
});

import { describe, it, expect } from "vitest";
import { render, screen } from "@testing-library/react";
import { Input } from "./Input";

describe("Input", () => {
  it("renders the label without a hint icon by default", () => {
    render(<Input label="Recreation Areas" />);
    expect(screen.getByText("Recreation Areas")).toBeInTheDocument();
    expect(screen.queryByTitle(/./)).not.toBeInTheDocument();
  });

  it("renders a hint icon with the given text as its title when hint is provided", () => {
    render(<Input label="Add by ID" hint="Find this in the URL" />);
    expect(screen.getByTitle("Find this in the URL")).toBeInTheDocument();
  });

  it("keeps the hint icon out of the field's accessible name", () => {
    render(<Input label="Consecutive nights" hint="Quick picks overwrite this" />);
    expect(screen.getByTitle("Quick picks overwrite this")).toHaveAttribute("aria-hidden", "true");
  });
});

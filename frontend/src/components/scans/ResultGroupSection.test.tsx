import { describe, it, expect } from "vitest";
import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { ResultGroupSection } from "./ResultGroupSection";

describe("ResultGroupSection", () => {
  it("renders the title and available/gone count badges", () => {
    render(
      <ResultGroupSection title="Upper Pines" availableCount={3} goneCount={1} defaultOpen>
        <p>leaf</p>
      </ResultGroupSection>,
    );
    expect(screen.getByText("Upper Pines")).toBeInTheDocument();
    expect(screen.getByText("3 available")).toBeInTheDocument();
    expect(screen.getByText("1 gone")).toBeInTheDocument();
  });

  it("hides the gone badge when goneCount is 0", () => {
    render(
      <ResultGroupSection title="Upper Pines" availableCount={3} goneCount={0} defaultOpen>
        <p>leaf</p>
      </ResultGroupSection>,
    );
    expect(screen.queryByText("0 gone")).not.toBeInTheDocument();
  });

  it("shows children when defaultOpen is true", () => {
    render(
      <ResultGroupSection title="Upper Pines" availableCount={1} goneCount={0} defaultOpen>
        <p>leaf content</p>
      </ResultGroupSection>,
    );
    expect(screen.getByText("leaf content")).toBeVisible();
  });

  it("hides children when defaultOpen is false", () => {
    render(
      <ResultGroupSection title="Upper Pines" availableCount={1} goneCount={0} defaultOpen={false}>
        <p>leaf content</p>
      </ResultGroupSection>,
    );
    expect(screen.getByText("leaf content")).not.toBeVisible();
  });

  it("reveals children when the summary is clicked", async () => {
    render(
      <ResultGroupSection title="Upper Pines" availableCount={1} goneCount={0} defaultOpen={false}>
        <p>leaf content</p>
      </ResultGroupSection>,
    );
    await userEvent.click(screen.getByText("Upper Pines"));
    expect(screen.getByText("leaf content")).toBeVisible();
  });

  it("renders the subtitle when provided", () => {
    render(
      <ResultGroupSection title="Other" subtitle="results without a resolved campground" availableCount={0} goneCount={0} defaultOpen>
        <p>leaf</p>
      </ResultGroupSection>,
    );
    expect(screen.getByText("results without a resolved campground")).toBeInTheDocument();
  });
});

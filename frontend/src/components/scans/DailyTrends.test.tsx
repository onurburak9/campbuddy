import { describe, it, expect } from "vitest";
import { render, screen } from "@testing-library/react";
import { DailyTrends, successRate } from "./DailyTrends";
import type { DailyStatsBucket } from "../../types";

function bucket(overrides: Partial<DailyStatsBucket>): DailyStatsBucket {
  return { date: "2026-06-30", runs: 0, successes: 0, no_results: 0, errors: 0, new_sites: 0, ...overrides };
}

describe("successRate", () => {
  it("counts no_results as healthy and returns null for days without runs", () => {
    expect(successRate(bucket({ runs: 4, successes: 1, no_results: 2, errors: 1 }))).toBe(75);
    expect(successRate(bucket({}))).toBeNull();
  });
});

describe("DailyTrends", () => {
  it("summarises totals across the window", () => {
    render(
      <DailyTrends
        days={[
          bucket({ date: "2026-06-29", runs: 2, successes: 2, new_sites: 1 }),
          bucket({ date: "2026-06-30", runs: 2, errors: 2, new_sites: 2 }),
        ]}
      />,
    );
    expect(screen.getByText("4 total")).toBeInTheDocument();
    expect(screen.getByText("50% overall")).toBeInTheDocument();
    expect(screen.getByText("3 total")).toBeInTheDocument();
  });

  it("exposes per-day breakdown in bar tooltips", () => {
    render(<DailyTrends days={[bucket({ runs: 3, successes: 1, no_results: 1, errors: 1, new_sites: 5 })]} />);
    expect(screen.getByTitle(/3 runs \(1 success, 1 no results, 1 errors\)/)).toBeInTheDocument();
    expect(screen.getByTitle(/67%$/)).toBeInTheDocument();
    expect(screen.getByTitle(/5 new sites/)).toBeInTheDocument();
  });

  it("shows 'no runs' when the window is empty", () => {
    render(<DailyTrends days={[bucket({})]} />);
    expect(screen.getByText("no runs")).toBeInTheDocument();
  });
});

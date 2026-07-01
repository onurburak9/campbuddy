import { describe, it, expect } from "vitest";
import { render, screen } from "@testing-library/react";
import { RunHealthBar } from "./RunHealthBar";

const runs = [
  { id: 2, scan_id: 1, started_at: "2026-06-24T11:00:00Z", finished_at: "2026-06-24T11:00:05Z", outcome: "success", sites_found: 3, error_message: null },
  { id: 1, scan_id: 1, started_at: "2026-06-24T10:00:00Z", finished_at: "2026-06-24T10:00:04Z", outcome: "error", sites_found: 0, error_message: "boom" },
] as const;

describe("RunHealthBar", () => {
  it("renders one bar per run with a tooltip", () => {
    render(<RunHealthBar runs={[...runs]} />);
    const bars = screen.getAllByTitle(/ago|now/);
    expect(bars).toHaveLength(2);
  });
});

import { describe, it, expect } from "vitest";
import { render, screen } from "@testing-library/react";
import { ResultCard } from "./ResultCard";
import type { ScanResult } from "../../types";

const base: ScanResult = {
  id: 10,
  scan_run_id: 42,
  scan_id: 7,
  campsite_id: "A1",
  facility_name: "Sunset Campground",
  site_name: "Hawk Hollow",
  campsite_type: "TENT",
  booking_date: "2026-08-01",
  booking_end_date: "2026-08-03",
  booking_url: "https://www.recreation.gov/camping/campsites/A1",
  first_seen_at: "2026-06-01T10:00:00Z",
  cart_added: true,
  notified: true,
};

describe("ResultCard", () => {
  it("renders site name, facility name, campsite type, and date range", () => {
    render(<ResultCard result={base} />);
    expect(screen.getByText("Hawk Hollow")).toBeInTheDocument();
    expect(screen.getByText("Sunset Campground")).toBeInTheDocument();
    // campsite_type appears in the date-range / type line
    expect(screen.getByText(/TENT/)).toBeInTheDocument();
    // date range text (locale-formatted) — just check both dates are represented
    expect(screen.getByText(/Aug/)).toBeInTheDocument();
  });

  it("renders campsite_id with # prefix", () => {
    render(<ResultCard result={base} />);
    expect(screen.getByText("#A1")).toBeInTheDocument();
  });

  it("renders 'First seen' text and the scan_run_id", () => {
    render(<ResultCard result={base} />);
    expect(screen.getByText(/first seen/i)).toBeInTheDocument();
    expect(screen.getByText(/run #42/i)).toBeInTheDocument();
  });

  it("shows 'In cart' badge when cart_added is true", () => {
    render(<ResultCard result={base} />);
    expect(screen.getByText("In cart")).toBeInTheDocument();
    expect(screen.queryByText("Not in cart")).not.toBeInTheDocument();
  });

  it("shows 'Not in cart' badge when cart_added is false", () => {
    render(<ResultCard result={{ ...base, cart_added: false }} />);
    expect(screen.getByText("Not in cart")).toBeInTheDocument();
    expect(screen.queryByText("In cart")).not.toBeInTheDocument();
  });

  it("shows Notified badge when notified is true", () => {
    render(<ResultCard result={base} />);
    expect(screen.getByText("Notified")).toBeInTheDocument();
  });

  it("does not show Notified badge when notified is false", () => {
    render(<ResultCard result={{ ...base, notified: false }} />);
    expect(screen.queryByText("Notified")).not.toBeInTheDocument();
  });

  it("renders the 'Book →' link with correct href, target, and rel", () => {
    render(<ResultCard result={base} />);
    const link = screen.getByRole("link", { name: /book/i });
    expect(link).toHaveAttribute("href", "https://www.recreation.gov/camping/campsites/A1");
    expect(link).toHaveAttribute("target", "_blank");
    expect(link).toHaveAttribute("rel", "noopener noreferrer");
  });
});

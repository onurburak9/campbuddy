import { describe, it, expect, vi } from "vitest";
import { render, screen } from "@testing-library/react";
import { Tabs } from "./Tabs";

describe("Tabs", () => {
  const tabs = [{ id: "a", label: "Alpha" }, { id: "b", label: "Beta" }];

  it("makes the tablist horizontally scrollable and tabs non-wrapping", () => {
    render(<Tabs tabs={tabs} active="a" onChange={vi.fn()} />);
    expect(screen.getByRole("tablist").className).toContain("overflow-x-auto");
    expect(screen.getByRole("tab", { name: "Alpha" }).className).toContain("whitespace-nowrap");
    expect(screen.getByRole("tab", { name: "Alpha" }).className).toContain("shrink-0");
  });
});

import { describe, it, expect } from "vitest";
import { renderHook, act } from "@testing-library/react";
import { useScanFormState } from "./useScanFormState";
import type { Scan } from "../../types";

describe("useScanFormState", () => {
  it("builds a create payload from selected id items", () => {
    const { result } = renderHook(() => useScanFormState());
    act(() => {
      result.current.set("provider", "RecreationDotGov");
      result.current.set("recAreaIds", [{ id: 2991, name: "Yosemite" }, { id: 2992, name: "Sequoia" }]);
      result.current.set("windows", [{ start_date: "2026-07-01", end_date: "2026-07-03" }]);
      result.current.set("nights", 2);
    });
    const payload = result.current.toScanCreatePayload();
    expect(payload.rec_area_ids).toEqual([2991, 2992]);
    expect(payload.search_windows).toHaveLength(1);
    expect(payload.nights).toBe(2);
  });

  it("omits empty id fields as null", () => {
    const { result } = renderHook(() => useScanFormState());
    const payload = result.current.toScanCreatePayload();
    expect(payload.campground_ids).toBeNull();
    expect(payload.campsite_ids).toBeNull();
  });

  it("pre-fills id fields from an existing scan with a fallback 'ID {n}' label", () => {
    const scan = {
      rec_area_ids: [2991],
      campground_ids: [232447],
      campsite_ids: null,
    } as unknown as Scan;
    const { result } = renderHook(() => useScanFormState(scan));
    expect(result.current.state.recAreaIds).toEqual([{ id: 2991, name: "ID 2991" }]);
    expect(result.current.state.campgroundIds).toEqual([{ id: 232447, name: "ID 232447" }]);
    expect(result.current.state.campsiteIds).toEqual([]);
  });
});

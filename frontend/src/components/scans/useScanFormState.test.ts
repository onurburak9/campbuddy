import { describe, it, expect } from "vitest";
import { renderHook, act } from "@testing-library/react";
import { useScanFormState } from "./useScanFormState";

describe("useScanFormState", () => {
  it("parses comma-separated ids and builds a create payload", () => {
    const { result } = renderHook(() => useScanFormState());
    act(() => {
      result.current.set("provider", "RecreationDotGov");
      result.current.set("recAreaIds", "2991, 2992 ,");
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
});

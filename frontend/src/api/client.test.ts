import { describe, it, expect } from "vitest";
import { http, HttpResponse } from "msw";
import { server } from "../test/server";
import { fetchApi } from "./client";
import type { ApiError as _ApiError } from "./client";

describe("fetchApi", () => {
  it("prepends /api/v1 and returns parsed JSON", async () => {
    server.use(http.get("/api/v1/scans", () => HttpResponse.json([{ id: 1 }])));
    const data = await fetchApi<{ id: number }[]>("/scans");
    expect(data).toEqual([{ id: 1 }]);
  });

  it("throws ApiError with status on 4xx", async () => {
    server.use(
      http.get("/api/v1/scans", () =>
        HttpResponse.json({ detail: "nope" }, { status: 403 })
      )
    );
    await expect(fetchApi("/scans")).rejects.toMatchObject({
      name: "ApiError",
      status: 403,
    });
  });

  it("returns undefined for 204 No Content", async () => {
    server.use(http.delete("/api/v1/scans/1", () => new HttpResponse(null, { status: 204 })));
    const out = await fetchApi("/scans/1", { method: "DELETE" });
    expect(out).toBeUndefined();
  });
});

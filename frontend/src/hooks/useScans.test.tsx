import { describe, it, expect } from "vitest";
import { http, HttpResponse } from "msw";
import { renderHook, waitFor } from "@testing-library/react";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { server } from "../test/server";
import { useScans } from "./useScans";

function wrapper({ children }: { children: React.ReactNode }) {
  const qc = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  return <QueryClientProvider client={qc}>{children}</QueryClientProvider>;
}

describe("useScans", () => {
  it("fetches the scan list", async () => {
    server.use(http.get("/api/v1/scans", () =>
      HttpResponse.json([{ id: 1, name: "Yosemite" }])));
    const { result } = renderHook(() => useScans(), { wrapper });
    await waitFor(() => expect(result.current.isSuccess).toBe(true));
    expect(result.current.data).toHaveLength(1);
  });
});

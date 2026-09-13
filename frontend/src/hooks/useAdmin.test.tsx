import { describe, it, expect } from "vitest";
import { http, HttpResponse } from "msw";
import { renderHook, waitFor } from "@testing-library/react";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { server } from "../test/server";
import { useAdminUsers, useAdminScans, useAdminScan, useAdminScanRuns } from "./useAdmin";

function wrapper({ children }: { children: React.ReactNode }) {
  const qc = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  return <QueryClientProvider client={qc}>{children}</QueryClientProvider>;
}

describe("useAdmin", () => {
  it("fetches the admin user list", async () => {
    server.use(http.get("/api/v1/admin/users", () =>
      HttpResponse.json([{ id: 1, email: "a@b.c" }])));
    const { result } = renderHook(() => useAdminUsers(), { wrapper });
    await waitFor(() => expect(result.current.isSuccess).toBe(true));
    expect(result.current.data).toHaveLength(1);
  });

  it("fetches the admin scan list", async () => {
    server.use(http.get("/api/v1/admin/scans", () =>
      HttpResponse.json([{ id: 1, user_email: "a@b.c" }])));
    const { result } = renderHook(() => useAdminScans(), { wrapper });
    await waitFor(() => expect(result.current.isSuccess).toBe(true));
    expect(result.current.data).toHaveLength(1);
  });

  it("fetches a single admin scan's detail", async () => {
    server.use(http.get("/api/v1/admin/scans/7", () =>
      HttpResponse.json({ id: 7, user_email: "a@b.c" })));
    const { result } = renderHook(() => useAdminScan(7), { wrapper });
    await waitFor(() => expect(result.current.isSuccess).toBe(true));
    expect(result.current.data?.id).toBe(7);
  });

  it("fetches an admin scan's recent runs", async () => {
    server.use(http.get("/api/v1/admin/scans/7/runs", () =>
      HttpResponse.json([{ id: 1 }, { id: 2 }])));
    const { result } = renderHook(() => useAdminScanRuns(7, 1, 10), { wrapper });
    await waitFor(() => expect(result.current.isSuccess).toBe(true));
    expect(result.current.data).toHaveLength(2);
  });
});

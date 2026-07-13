export const queryKeys = {
  me: ["me"] as const,
  profile: ["profile"] as const,
  scans: ["scans"] as const,
  scan: (id: number) => ["scans", id] as const,
  stats: (id: number) => ["scans", id, "stats"] as const,
  runs: (id: number, page: number, pageSize: number, outcome?: string, startedAfter?: string) =>
    ["scans", id, "runs", { page, pageSize, outcome: outcome ?? null, startedAfter: startedAfter ?? null }] as const,
  runsCount: (id: number, outcome?: string, startedAfter?: string) =>
    ["scans", id, "runs", "count", { outcome: outcome ?? null, startedAfter: startedAfter ?? null }] as const,
  runResults: (id: number, runId: number) =>
    ["scans", id, "runs", runId, "results"] as const,
  results: (id: number, page: number, pageSize: number) =>
    ["scans", id, "results", { page, pageSize }] as const,
  allResults: (id: number) => ["scans", id, "results", "all"] as const,
};

export const queryKeys = {
  me: ["me"] as const,
  profile: ["profile"] as const,
  scans: ["scans"] as const,
  scan: (id: number) => ["scans", id] as const,
  stats: (id: number) => ["scans", id, "stats"] as const,
  runs: (id: number, page: number) => ["scans", id, "runs", page] as const,
  results: (id: number, page: number) => ["scans", id, "results", page] as const,
};

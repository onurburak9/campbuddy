import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { scans } from "../api/scans";
import { queryKeys } from "./queryKeys";
import type { ScanCreatePayload, ScanUpdatePayload } from "../types";

export function useScans() {
  return useQuery({ queryKey: queryKeys.scans, queryFn: scans.list });
}

export function useScan(id: number | null) {
  return useQuery({
    queryKey: id ? queryKeys.scan(id) : ["scans", "none"],
    queryFn: () => scans.get(id as number),
    enabled: id != null,
  });
}

export function useScanStats(id: number | null) {
  return useQuery({
    queryKey: id ? queryKeys.stats(id) : ["scans", "none", "stats"],
    queryFn: () => scans.stats(id as number),
    enabled: id != null,
  });
}

export function useCreateScan() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (payload: ScanCreatePayload) => scans.create(payload),
    onSuccess: () => qc.invalidateQueries({ queryKey: queryKeys.scans }),
  });
}

export function useUpdateScan() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: ({ id, payload }: { id: number; payload: ScanUpdatePayload }) =>
      scans.update(id, payload),
    onSuccess: (scan) => {
      qc.invalidateQueries({ queryKey: queryKeys.scans });
      qc.invalidateQueries({ queryKey: queryKeys.scan(scan.id) });
    },
  });
}

export function useDeleteScan() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (id: number) => scans.remove(id),
    onSuccess: () => qc.invalidateQueries({ queryKey: queryKeys.scans }),
  });
}

export function usePauseScan() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (id: number) => scans.pause(id),
    onSuccess: (scan) => {
      qc.invalidateQueries({ queryKey: queryKeys.scans });
      qc.invalidateQueries({ queryKey: queryKeys.scan(scan.id) });
    },
  });
}

export function useResumeScan() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (id: number) => scans.resume(id),
    onSuccess: (scan) => {
      qc.invalidateQueries({ queryKey: queryKeys.scans });
      qc.invalidateQueries({ queryKey: queryKeys.scan(scan.id) });
    },
  });
}

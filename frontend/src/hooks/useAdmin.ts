import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { admin } from "../api/admin";
import { queryKeys } from "./queryKeys";

export function useAdminUsers() {
  return useQuery({ queryKey: queryKeys.adminUsers, queryFn: admin.listUsers });
}

export function useAdminScans() {
  return useQuery({ queryKey: queryKeys.adminScans, queryFn: admin.listScans });
}

export function useAdminPauseScan() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (id: number) => admin.pauseScan(id),
    onSuccess: () => qc.invalidateQueries({ queryKey: queryKeys.adminScans }),
  });
}

export function useAdminResumeScan() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (id: number) => admin.resumeScan(id),
    onSuccess: () => qc.invalidateQueries({ queryKey: queryKeys.adminScans }),
  });
}

export function useAdminDeleteScan() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (id: number) => admin.deleteScan(id),
    onSuccess: () => qc.invalidateQueries({ queryKey: queryKeys.adminScans }),
  });
}

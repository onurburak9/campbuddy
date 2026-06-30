import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { users } from "../api/users";
import { queryKeys } from "./queryKeys";
import type { ProfileUpdatePayload } from "../types";

export function useProfile() {
  return useQuery({ queryKey: queryKeys.profile, queryFn: users.getProfile });
}

export function useUpdateProfile() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (payload: ProfileUpdatePayload) => users.updateProfile(payload),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: queryKeys.me });
      qc.invalidateQueries({ queryKey: queryKeys.profile });
    },
  });
}

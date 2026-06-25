import { fetchApi } from "./client";
import type { Profile, ProfileUpdatePayload } from "../types";

export const users = {
  getProfile: () => fetchApi<Profile>("/users/me"),
  updateProfile: (payload: ProfileUpdatePayload) =>
    fetchApi<Profile>("/users/me", { method: "PATCH", body: JSON.stringify(payload) }),
};

import { fetchApi } from "./client";
import type { User } from "../types";

export const auth = {
  login: (email: string, password: string) =>
    fetchApi<void>("/auth/login", { method: "POST", body: JSON.stringify({ email, password }) }),
  logout: () => fetchApi<void>("/auth/logout", { method: "POST" }),
  me: () => fetchApi<User>("/auth/me"),
};

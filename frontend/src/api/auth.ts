import { fetchApi } from "./client";
import type { User } from "../types";

export const auth = {
  login: (email: string, password: string) =>
    fetchApi<void>("/auth/login", { method: "POST", body: JSON.stringify({ email, password }) }),
  register: (email: string, password: string) =>
    fetchApi<void>("/auth/register", { method: "POST", body: JSON.stringify({ email, password }) }),
  forgotPassword: (email: string) =>
    fetchApi<void>("/auth/forgot-password", { method: "POST", body: JSON.stringify({ email }) }),
  resetPassword: (token: string, password: string) =>
    fetchApi<void>("/auth/reset-password", { method: "POST", body: JSON.stringify({ token, password }) }),
  logout: () => fetchApi<void>("/auth/logout", { method: "POST" }),
  me: () => fetchApi<User>("/auth/me"),
};

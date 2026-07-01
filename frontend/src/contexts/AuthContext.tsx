import { createContext, useContext, type ReactNode } from "react";
import { useQuery, useQueryClient } from "@tanstack/react-query";
import { auth } from "../api/auth";
import { ApiError } from "../api/client";
import type { User } from "../types";

interface AuthCtx {
  user: User | null;
  isLoading: boolean;
  isAuthenticated: boolean;
  login: (email: string, password: string) => Promise<void>;
  logout: () => Promise<void>;
}

const Ctx = createContext<AuthCtx | null>(null);

export function AuthProvider({ children }: { children: ReactNode }) {
  const qc = useQueryClient();
  const { data, isLoading } = useQuery({
    queryKey: ["me"],
    queryFn: auth.me,
    retry: (count, err) => !(err instanceof ApiError && err.status === 401) && count < 1,
    staleTime: 5 * 60 * 1000,
  });

  const login = async (email: string, password: string) => {
    await auth.login(email, password);
    await qc.invalidateQueries({ queryKey: ["me"] });
  };
  const logout = async () => {
    await auth.logout();
    qc.clear();
  };

  return (
    <Ctx.Provider
      value={{ user: data ?? null, isLoading, isAuthenticated: !!data, login, logout }}
    >
      {children}
    </Ctx.Provider>
  );
}

export function useAuth(): AuthCtx {
  const ctx = useContext(Ctx);
  if (!ctx) throw new Error("useAuth must be used within AuthProvider");
  return ctx;
}

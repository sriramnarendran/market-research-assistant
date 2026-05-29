import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import {
  createContext,
  useCallback,
  useContext,
  useMemo,
  type ReactNode,
} from "react";

import { api, ApiError } from "@/api/client";
import type { LoginRequest, SignupRequest, UserResponse } from "@/api/types";

interface AuthContextValue {
  user: UserResponse | null | undefined;
  isLoading: boolean;
  isAuthenticated: boolean;
  isAdmin: boolean;
  login: (body: LoginRequest) => Promise<void>;
  signup: (body: SignupRequest) => Promise<void>;
  logout: () => Promise<void>;
}

const AuthContext = createContext<AuthContextValue | null>(null);

export function AuthProvider({ children }: { children: ReactNode }) {
  const queryClient = useQueryClient();

  const meQuery = useQuery({
    queryKey: ["auth", "me"],
    queryFn: api.auth.me,
    retry: (count, err) => {
      if (err instanceof ApiError && err.status === 401) return false;
      return count < 1;
    },
  });

  const invalidate = useCallback(() => {
    void queryClient.invalidateQueries({ queryKey: ["auth", "me"] });
  }, [queryClient]);

  const loginMutation = useMutation({
    mutationFn: api.auth.login,
    onSuccess: () => invalidate(),
  });

  const signupMutation = useMutation({
    mutationFn: api.auth.signup,
    onSuccess: () => invalidate(),
  });

  const logoutMutation = useMutation({
    mutationFn: api.auth.logout,
    onSuccess: () => {
      queryClient.setQueryData(["auth", "me"], null);
      void queryClient.invalidateQueries({ queryKey: ["auth", "me"] });
    },
  });

  const value = useMemo<AuthContextValue>(
    () => ({
      user: meQuery.data,
      isLoading: meQuery.isLoading,
      isAuthenticated: !!meQuery.data,
      isAdmin: meQuery.data?.role === "admin",
      login: async (body) => {
        await loginMutation.mutateAsync(body);
      },
      signup: async (body) => {
        await signupMutation.mutateAsync(body);
      },
      logout: async () => {
        await logoutMutation.mutateAsync();
      },
    }),
    [meQuery.data, meQuery.isLoading, loginMutation, signupMutation, logoutMutation],
  );

  return <AuthContext.Provider value={value}>{children}</AuthContext.Provider>;
}

export function useAuth(): AuthContextValue {
  const ctx = useContext(AuthContext);
  if (!ctx) throw new Error("useAuth must be used within AuthProvider");
  return ctx;
}

"use client";

import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";

import { api, problemTitle, setCsrfToken } from "./api/client";

const SESSION_KEY = ["session"] as const;

/** The signed-in user, or null when signed out. Also keeps the CSRF token current. */
export function useSession() {
  return useQuery({
    queryKey: SESSION_KEY,
    queryFn: async () => {
      const { data, response } = await api.GET("/api/v1/auth/me");
      if (response.status === 401) {
        setCsrfToken(null);
        return null;
      }
      if (!data) throw new Error("Could not load the session");
      setCsrfToken(data.csrf_token);
      return data;
    },
    staleTime: 60_000,
    retry: false,
  });
}

export function useLogin() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: async (credentials: { email: string; password: string }) => {
      const { data, error, response } = await api.POST("/api/v1/auth/login", {
        body: credentials,
      });
      if (!data) {
        const retryAfter = response.headers.get("Retry-After");
        const title = problemTitle(error, "Sign-in failed");
        throw new Error(retryAfter ? `${title}. Try again in ${retryAfter} seconds.` : title);
      }
      setCsrfToken(data.csrf_token);
      return data;
    },
    onSuccess: (data) => queryClient.setQueryData(SESSION_KEY, data),
  });
}

export function useLogout() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: async () => {
      await api.POST("/api/v1/auth/logout");
      setCsrfToken(null);
    },
    onSuccess: () => queryClient.setQueryData(SESSION_KEY, null),
  });
}

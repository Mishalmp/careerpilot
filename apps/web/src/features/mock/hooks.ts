"use client";

import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";

import { api, unwrap } from "@/lib/api/client";
import type { components } from "@/lib/api/schema";

type Schemas = components["schemas"];
export type StartMock = Schemas["StartMockRequest"];

const LIST = ["mock", "sessions"] as const;
const one = (id: string) => ["mock", "session", id] as const;

export function useMockSessions() {
  return useQuery({
    queryKey: LIST,
    queryFn: async () => unwrap(await api.GET("/api/v1/mock/sessions")),
  });
}

export function useMockSession(id: string) {
  return useQuery({
    queryKey: one(id),
    queryFn: async () =>
      unwrap(
        await api.GET("/api/v1/mock/sessions/{session_id}", {
          params: { path: { session_id: id } },
        }),
      ),
  });
}

export function useStartMock() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: async (body: StartMock) =>
      unwrap(await api.POST("/api/v1/mock/sessions", { body })),
    onSuccess: (data) => {
      queryClient.setQueryData(one(data.id), data);
      void queryClient.invalidateQueries({ queryKey: LIST });
    },
  });
}

export function useAnswerMock(id: string) {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: async (args: { turn: number; answer: string }) =>
      unwrap(
        await api.POST("/api/v1/mock/sessions/{session_id}/answer", {
          params: { path: { session_id: id } },
          body: args,
        }),
      ),
    onSuccess: (data) => {
      queryClient.setQueryData(one(id), data);
      void queryClient.invalidateQueries({ queryKey: LIST });
    },
    // A stale page (answered elsewhere) should show the saved state, not an old one.
    onError: () => queryClient.invalidateQueries({ queryKey: one(id) }),
  });
}

export function useDeleteMock() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: async (id: string) => {
      const { error, response } = await api.DELETE(
        "/api/v1/mock/sessions/{session_id}",
        {
          params: { path: { session_id: id } },
        },
      );
      if (!response.ok) unwrap({ error, response });
    },
    onSuccess: () => queryClient.invalidateQueries({ queryKey: LIST }),
  });
}

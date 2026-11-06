"use client";

import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";

import { api, unwrap } from "@/lib/api/client";
import type { components } from "@/lib/api/schema";

type Schemas = components["schemas"];
export type Checkpoint = Schemas["LearnCheckpointOut"];
export type CheckpointItem = Schemas["LearnCheckpointItemOut"];
export type CheckpointSummary = Schemas["LearnCheckpointSummary"];

const ROOT = ["learn", "checkpoints"] as const;

export function useCheckpoints() {
  return useQuery({
    queryKey: ROOT,
    queryFn: async () => unwrap(await api.GET("/api/v1/learn/checkpoints")),
  });
}

export function useCreateCheckpoint() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: async (body: { topic_ids: string[]; size: number; pass_mark: number }) =>
      unwrap(await api.POST("/api/v1/learn/checkpoints", { body })),
    onSuccess: () => queryClient.invalidateQueries({ queryKey: ROOT }),
  });
}

export function useCheckpoint(id: string) {
  return useQuery({
    queryKey: [...ROOT, id],
    queryFn: async () =>
      unwrap(
        await api.GET("/api/v1/learn/checkpoints/{checkpoint_id}", {
          params: { path: { checkpoint_id: id } },
        }),
      ),
    // The exam is the source of truth on the server (time limit, saved answers); do not refetch
    // while taking it, so the screen does not jump.
    staleTime: Infinity,
    refetchOnWindowFocus: false,
  });
}

export function useSaveItem(id: string) {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: async (input: { position: number; selected?: number[]; flagged?: boolean }) =>
      unwrap(
        await api.PUT("/api/v1/learn/checkpoints/{checkpoint_id}/items/{position}", {
          params: { path: { checkpoint_id: id, position: input.position } },
          body: { selected: input.selected, flagged: input.flagged },
        }),
      ),
    onSuccess: (data) => queryClient.setQueryData([...ROOT, id], data),
  });
}

export function useSubmitCheckpoint(id: string) {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: async () =>
      unwrap(
        await api.POST("/api/v1/learn/checkpoints/{checkpoint_id}/submit", {
          params: { path: { checkpoint_id: id } },
        }),
      ),
    onSuccess: (data) => {
      queryClient.setQueryData([...ROOT, id], data);
      void queryClient.invalidateQueries({ queryKey: ROOT });
      void queryClient.invalidateQueries({ queryKey: ["learn"] });
    },
  });
}

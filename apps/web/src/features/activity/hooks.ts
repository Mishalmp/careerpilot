"use client";

import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";

import { api, unwrap } from "@/lib/api/client";
import type { components } from "@/lib/api/schema";

type Schemas = components["schemas"];
export type TaskStatus = Schemas["TaskStatus"];
export type Task = Schemas["TaskOut"];
export type TaskDetail = Schemas["TaskDetail"];
export type AiCall = Schemas["AiCallOut"];

const ROOT = ["tasks"] as const;

const busy = (tasks: Task[] | undefined) => tasks?.some((t) => t.status === "running" || t.status === "queued");

/** Faster polling while something is running, so progress looks live; slow when all is quiet. */
export function useTasks(status?: TaskStatus) {
  return useQuery({
    queryKey: [...ROOT, "list", status ?? "all"],
    queryFn: async () => unwrap(await api.GET("/api/v1/tasks", { params: { query: { status } } })),
    refetchInterval: (query) => (busy(query.state.data?.items) ? 3000 : 15_000),
  });
}

export function useTask(id: string, open: boolean) {
  return useQuery({
    queryKey: [...ROOT, "detail", id],
    enabled: open,
    queryFn: async () => unwrap(await api.GET("/api/v1/tasks/{task_id}", { params: { path: { task_id: id } } })),
    refetchInterval: (query) => {
      const status = query.state.data?.task.status;
      return status === "running" || status === "queued" ? 2000 : false;
    },
  });
}

function useRefresh() {
  const queryClient = useQueryClient();
  return () => void queryClient.invalidateQueries({ queryKey: ROOT });
}

export function useRetryTask() {
  const refresh = useRefresh();
  return useMutation({
    mutationFn: async (id: string) => unwrap(await api.POST("/api/v1/tasks/{task_id}/retry", { params: { path: { task_id: id } } })),
    onSuccess: refresh,
  });
}

export function useCancelTask() {
  const refresh = useRefresh();
  return useMutation({
    mutationFn: async (id: string) => unwrap(await api.POST("/api/v1/tasks/{task_id}/cancel", { params: { path: { task_id: id } } })),
    onSuccess: refresh,
  });
}

export function useRetryFailed() {
  const refresh = useRefresh();
  return useMutation({
    mutationFn: async () => unwrap(await api.POST("/api/v1/tasks/retry-failed")),
    onSuccess: refresh,
  });
}

export function useAiCalls(problemsOnly: boolean) {
  return useQuery({
    queryKey: ["system", "ai-calls", problemsOnly],
    queryFn: async () => unwrap(await api.GET("/api/v1/system/ai-calls", { params: { query: { problems_only: problemsOnly, limit: 100 } } })),
    refetchInterval: 15_000,
  });
}

"use client";

import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";

import { api, unwrap } from "@/lib/api/client";
import type { components } from "@/lib/api/schema";

type Schemas = components["schemas"];
export type DiscoverySource = Schemas["DiscoverySourceOut"];
export type NewSource = Schemas["DiscoverySourceCreate"];
export type Candidate = Schemas["CandidateOut"];
export type TaskStatus = Schemas["TaskStatus"];
export type CandidateStatus = Schemas["CandidateStatus"];

const SOURCES = ["discovery", "sources"] as const;
const CANDIDATES = ["discovery", "candidates"] as const;
const TASKS = ["tasks"] as const;

export function useSources() {
  return useQuery({
    queryKey: SOURCES,
    queryFn: async () => unwrap(await api.GET("/api/v1/discovery/sources")),
  });
}

function useRefresh() {
  const queryClient = useQueryClient();
  return () => {
    void queryClient.invalidateQueries({ queryKey: SOURCES });
    void queryClient.invalidateQueries({ queryKey: CANDIDATES });
    void queryClient.invalidateQueries({ queryKey: TASKS });
    void queryClient.invalidateQueries({ queryKey: ["digest"] });
  };
}

export function useAddSource() {
  const refresh = useRefresh();
  return useMutation({
    mutationFn: async (body: NewSource) =>
      unwrap(await api.POST("/api/v1/discovery/sources", { body })),
    onSuccess: refresh,
  });
}

export function useUpdateSource() {
  const refresh = useRefresh();
  return useMutation({
    mutationFn: async (args: { id: string; enabled: boolean }) =>
      unwrap(
        await api.PATCH("/api/v1/discovery/sources/{source_id}", {
          params: { path: { source_id: args.id } },
          body: { enabled: args.enabled },
        }),
      ),
    onSuccess: refresh,
  });
}

export function useDeleteSource() {
  const refresh = useRefresh();
  return useMutation({
    mutationFn: async (id: string) => {
      const { error, response } = await api.DELETE(
        "/api/v1/discovery/sources/{source_id}",
        {
          params: { path: { source_id: id } },
        },
      );
      if (!response.ok) unwrap({ error, response });
    },
    onSuccess: refresh,
  });
}

export function useRunSource() {
  const refresh = useRefresh();
  return useMutation({
    mutationFn: async (id: string) =>
      unwrap(
        await api.POST("/api/v1/discovery/sources/{source_id}/run", {
          params: { path: { source_id: id } },
        }),
      ),
    // A failed run is recorded on the source too, so refresh either way.
    onSettled: refresh,
  });
}

export function useCandidates(status: CandidateStatus) {
  return useQuery({
    queryKey: [...CANDIDATES, status],
    queryFn: async () =>
      unwrap(
        await api.GET("/api/v1/discovery/candidates", {
          params: { query: { status } },
        }),
      ),
  });
}

export function useAcceptCandidate() {
  const refresh = useRefresh();
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: async (id: string) =>
      unwrap(
        await api.POST("/api/v1/discovery/candidates/{candidate_id}/accept", {
          params: { path: { candidate_id: id } },
        }),
      ),
    onSuccess: () => {
      refresh();
      void queryClient.invalidateQueries({ queryKey: ["jobs"] });
      void queryClient.invalidateQueries({ queryKey: ["today"] });
    },
  });
}

export function useSetCandidate() {
  const refresh = useRefresh();
  return useMutation({
    mutationFn: async (args: { id: string; action: "dismiss" | "restore" }) => {
      const path =
        args.action === "dismiss"
          ? "/api/v1/discovery/candidates/{candidate_id}/dismiss"
          : "/api/v1/discovery/candidates/{candidate_id}/restore";
      const { error, response } = await api.POST(path, {
        params: { path: { candidate_id: args.id } },
      });
      if (!response.ok) unwrap({ error, response });
    },
    onSuccess: refresh,
  });
}

export function useDigest() {
  return useQuery({
    queryKey: ["digest", "latest"],
    queryFn: async () => unwrap(await api.GET("/api/v1/digest/latest")),
  });
}

export function useTasks(status?: TaskStatus) {
  return useQuery({
    queryKey: [...TASKS, status ?? "all"],
    queryFn: async () =>
      unwrap(await api.GET("/api/v1/tasks", { params: { query: { status } } })),
    refetchInterval: 15_000,
  });
}

export function useRetryTask() {
  const refresh = useRefresh();
  return useMutation({
    mutationFn: async (id: string) =>
      unwrap(
        await api.POST("/api/v1/tasks/{task_id}/retry", {
          params: { path: { task_id: id } },
        }),
      ),
    onSuccess: refresh,
  });
}

export function useRetryFailed() {
  const refresh = useRefresh();
  return useMutation({
    mutationFn: async () =>
      unwrap(await api.POST("/api/v1/tasks/retry-failed")),
    onSuccess: refresh,
  });
}

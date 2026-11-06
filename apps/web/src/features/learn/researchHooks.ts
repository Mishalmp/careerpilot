"use client";

import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";

import { api, unwrap } from "@/lib/api/client";
import type { components } from "@/lib/api/schema";

type Schemas = components["schemas"];
export type ResearchRun = Schemas["ResearchRunOut"];
export type ResearchFinding = Schemas["ResearchFindingOut"];

const ROOT = ["research"] as const;

/** Runs for one job. While one is waiting or working the list refreshes every 3 seconds. */
export function useResearchRuns(jobId: string) {
  return useQuery({
    queryKey: [...ROOT, "runs", jobId],
    queryFn: async () =>
      unwrap(await api.GET("/api/v1/research/runs", { params: { query: { job_id: jobId } } })),
    refetchInterval: (query) =>
      query.state.data?.some((r) => r.status === "queued" || r.status === "running") ? 3000 : false,
  });
}

export function useStartResearch(jobId: string) {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: async () =>
      unwrap(await api.POST("/api/v1/research/runs", { body: { job_id: jobId } })),
    onSuccess: () => queryClient.invalidateQueries({ queryKey: [...ROOT, "runs", jobId] }),
  });
}

export function useFindings(limit = 50) {
  return useQuery({
    queryKey: [...ROOT, "findings", limit],
    queryFn: async () =>
      unwrap(
        await api.GET("/api/v1/research/findings", {
          params: { query: { status: "pending", limit } },
        }),
      ),
  });
}

export function useDecide() {
  const queryClient = useQueryClient();
  const refresh = () => {
    void queryClient.invalidateQueries({ queryKey: ROOT });
    void queryClient.invalidateQueries({ queryKey: ["learn"] });
  };
  return {
    approve: useMutation({
      mutationFn: async (id: string) =>
        unwrap(
          await api.POST("/api/v1/research/findings/{finding_id}/approve", {
            params: { path: { finding_id: id } },
          }),
        ),
      onSuccess: refresh,
    }),
    reject: useMutation({
      mutationFn: async (id: string) => {
        const { error, response } = await api.POST("/api/v1/research/findings/{finding_id}/reject", {
          params: { path: { finding_id: id } },
        });
        if (!response.ok) unwrap({ error, response });
      },
      onSuccess: refresh,
    }),
  };
}

"use client";

import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";

import { api, unwrap } from "@/lib/api/client";
import type { components } from "@/lib/api/schema";

type Schemas = components["schemas"];
export type ApplyItem = Schemas["ApplyItemOut"];
export type ApplyQueue = Schemas["ApplyQueueOut"];

const ROOT = ["apply"] as const;

/** The list. While a build is running (just asked for) it refreshes every 4 seconds. */
export function useApplyQueue(building: boolean) {
  return useQuery({
    queryKey: [...ROOT, "queue"],
    queryFn: async () => unwrap(await api.GET("/api/v1/apply/queue")),
    refetchInterval: building ? 4000 : false,
  });
}

export function useBuildQueue() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: async () => unwrap(await api.POST("/api/v1/apply/build")),
    onSuccess: () => queryClient.invalidateQueries({ queryKey: ROOT }),
  });
}

/** Research one listed job on the web now (pay, interview, same job elsewhere, company check). */
export function useResearchItem() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: async (id: string) =>
      unwrap(await api.POST("/api/v1/apply/items/{item_id}/research", { params: { path: { item_id: id } } })),
    onSuccess: () => queryClient.invalidateQueries({ queryKey: ROOT }),
  });
}

type Action = "approve" | "applied" | "skip";

export function useDecideItem() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: async ({ id, action }: { id: string; action: Action }) => {
      const path = {
        approve: "/api/v1/apply/items/{item_id}/approve",
        applied: "/api/v1/apply/items/{item_id}/applied",
        skip: "/api/v1/apply/items/{item_id}/skip",
      } as const;
      return unwrap(await api.POST(path[action], { params: { path: { item_id: id } }, body: {} }));
    },
    onSuccess: () => {
      void queryClient.invalidateQueries({ queryKey: ROOT });
      void queryClient.invalidateQueries({ queryKey: ["jobs"] });
      void queryClient.invalidateQueries({ queryKey: ["today"] });
    },
  });
}

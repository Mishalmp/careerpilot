"use client";

import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";

import { api, unwrap } from "@/lib/api/client";
import type { components } from "@/lib/api/schema";

type Schemas = components["schemas"];
export type AskResult = Schemas["AskOut"];
export type Hit = Schemas["HitOut"];

const STATUS = ["knowledge", "status"] as const;

export function useKnowledgeStatus() {
  return useQuery({
    queryKey: STATUS,
    queryFn: async () => unwrap(await api.GET("/api/v1/knowledge/status")),
  });
}

export function useIngest() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: async () => unwrap(await api.POST("/api/v1/knowledge/ingest")),
    onSuccess: () => queryClient.invalidateQueries({ queryKey: STATUS }),
  });
}

export function useAsk() {
  return useMutation({
    mutationFn: async (question: string) =>
      unwrap(await api.POST("/api/v1/knowledge/ask", { body: { question } })),
  });
}

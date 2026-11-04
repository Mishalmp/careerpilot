"use client";

import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";

import { api, unwrap } from "@/lib/api/client";
import type { DayStatus, StudyKind, TopicStatus } from "@/lib/api/types";

const PREP = ["prep"] as const;

function useRefreshPrep() {
  const queryClient = useQueryClient();
  return () => {
    void queryClient.invalidateQueries({ queryKey: PREP });
    void queryClient.invalidateQueries({ queryKey: ["today"] });
  };
}

export function useDays() {
  return useQuery({
    queryKey: [...PREP, "days"],
    queryFn: async () => unwrap(await api.GET("/api/v1/prep/days")),
  });
}

export function useTopics(filters: { area?: string; status?: TopicStatus }) {
  return useQuery({
    queryKey: [...PREP, "topics", filters],
    queryFn: async () => unwrap(await api.GET("/api/v1/prep/topics", { params: { query: filters } })),
  });
}

export function useGuides() {
  return useQuery({
    queryKey: [...PREP, "guides"],
    queryFn: async () => unwrap(await api.GET("/api/v1/prep/guides")),
  });
}

export function useGuide(name: string) {
  return useQuery({
    queryKey: [...PREP, "guide", name],
    queryFn: async () =>
      unwrap(await api.GET("/api/v1/prep/guides/{name}", { params: { path: { name } } })),
  });
}

export function useSeedPrep() {
  const refresh = useRefreshPrep();
  return useMutation({
    mutationFn: async () => unwrap(await api.POST("/api/v1/prep/seed")),
    onSuccess: refresh,
  });
}

export function useSetStartDate() {
  const refresh = useRefreshPrep();
  return useMutation({
    mutationFn: async (startDate: string) =>
      unwrap(await api.PUT("/api/v1/prep/plan", { body: { start_date: startDate } })),
    onSuccess: refresh,
  });
}

export function useUpdateDay() {
  const refresh = useRefreshPrep();
  return useMutation({
    mutationFn: async (args: { day: number; status?: DayStatus; notes?: string | null }) =>
      unwrap(
        await api.PATCH("/api/v1/prep/days/{number}", {
          params: { path: { number: args.day } },
          body: { status: args.status, notes: args.notes },
        }),
      ),
    onSuccess: refresh,
  });
}

export function useUpdateTopic() {
  const refresh = useRefreshPrep();
  return useMutation({
    mutationFn: async (args: {
      id: string;
      confidence?: number | null;
      status?: TopicStatus;
      notes?: string | null;
    }) => {
      const { id, ...body } = args;
      return unwrap(
        await api.PATCH("/api/v1/prep/topics/{topic_id}", {
          params: { path: { topic_id: id } },
          body,
        }),
      );
    },
    onSuccess: refresh,
  });
}

export function useLogSession() {
  const refresh = useRefreshPrep();
  return useMutation({
    mutationFn: async (args: { topicId: string; minutes: number; kind: StudyKind; notes?: string }) =>
      unwrap(
        await api.POST("/api/v1/prep/topics/{topic_id}/sessions", {
          params: { path: { topic_id: args.topicId } },
          body: { minutes: args.minutes, kind: args.kind, notes: args.notes },
        }),
      ),
    onSuccess: refresh,
  });
}

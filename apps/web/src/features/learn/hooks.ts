"use client";

import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";

import { api, unwrap } from "@/lib/api/client";
import type { components } from "@/lib/api/schema";

type Schemas = components["schemas"];
export type LearnTopic = Schemas["LearnTopicOut"];
export type LearnTopicCreate = Schemas["LearnTopicCreate"];
export type LearnTopicUpdate = Schemas["LearnTopicUpdate"];
export type LearnQuestion = Schemas["LearnQuestionOut"];
export type LearnQuestionCreate = Schemas["LearnQuestionCreate"];
export type LearnQuestionType = Schemas["QuestionType"];
export type QuestionToAnswer = Schemas["LearnQuestionToAnswer"];
export type AnswerResult = Schemas["LearnAnswerOut"];
export type ReviewQueue = Schemas["LearnReviewQueue"];
export type LearnStats = Schemas["LearnStats"];

const ROOT = ["learn"] as const;

export const QUESTION_TYPES: { value: LearnQuestionType; label: string }[] = [
  { value: "mcq_single", label: "Multiple choice (one answer)" },
  { value: "mcq_multi", label: "Multiple choice (several answers)" },
  { value: "short", label: "Short answer" },
  { value: "explain", label: "Explain in your own words" },
  { value: "scenario", label: "Scenario or design" },
];

export function typeLabel(type: LearnQuestionType): string {
  const found = QUESTION_TYPES.find((t) => t.value === type);
  if (found) return found.label;
  return type === "practical" ? "Practical (code)" : type;
}

export function useLearnStats() {
  return useQuery({
    queryKey: [...ROOT, "stats"],
    queryFn: async () => unwrap(await api.GET("/api/v1/learn/stats")),
  });
}

export function useLearnTopics(archived = false) {
  return useQuery({
    queryKey: [...ROOT, "topics", { archived }],
    queryFn: async () =>
      unwrap(await api.GET("/api/v1/learn/topics", { params: { query: { archived } } })),
  });
}

export function useCreateTopic() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: async (body: LearnTopicCreate) =>
      unwrap(await api.POST("/api/v1/learn/topics", { body })),
    onSuccess: () => queryClient.invalidateQueries({ queryKey: ROOT }),
  });
}

export function useUpdateTopic() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: async ({ id, body }: { id: string; body: LearnTopicUpdate }) =>
      unwrap(
        await api.PATCH("/api/v1/learn/topics/{topic_id}", {
          params: { path: { topic_id: id } },
          body,
        }),
      ),
    onSuccess: () => queryClient.invalidateQueries({ queryKey: ROOT }),
  });
}

export function useDeleteTopic() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: async (id: string) => {
      const { error, response } = await api.DELETE("/api/v1/learn/topics/{topic_id}", {
        params: { path: { topic_id: id } },
      });
      if (!response.ok) unwrap({ error, response });
    },
    onSuccess: () => queryClient.invalidateQueries({ queryKey: ROOT }),
  });
}

export function useLearnQuestions(topicId: string) {
  return useQuery({
    queryKey: [...ROOT, "questions", topicId],
    queryFn: async () =>
      unwrap(
        await api.GET("/api/v1/learn/questions", {
          params: { query: { topic_id: topicId, limit: 100 } },
        }),
      ),
  });
}

export function useCreateQuestion() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: async (body: LearnQuestionCreate) =>
      unwrap(await api.POST("/api/v1/learn/questions", { body })),
    onSuccess: () => queryClient.invalidateQueries({ queryKey: ROOT }),
  });
}

export function useDeleteQuestion() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: async (id: string) => {
      const { error, response } = await api.DELETE("/api/v1/learn/questions/{question_id}", {
        params: { path: { question_id: id } },
      });
      if (!response.ok) unwrap({ error, response });
    },
    onSuccess: () => queryClient.invalidateQueries({ queryKey: ROOT }),
  });
}

/** The queue is read once per session: refetching mid-session would reshuffle the questions. */
export function useReviewQueue(limit = 20) {
  return useQuery({
    queryKey: [...ROOT, "review", limit],
    queryFn: async () =>
      unwrap(await api.GET("/api/v1/learn/review", { params: { query: { limit } } })),
    staleTime: Infinity,
    gcTime: 0,
    refetchOnWindowFocus: false,
  });
}

export function useAnswer() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: async (input: {
      questionId: string;
      token: string;
      selected?: number[];
      text?: string;
      selfScore?: number;
      confidence: number;
      seconds?: number;
    }) =>
      unwrap(
        await api.POST("/api/v1/learn/questions/{question_id}/answer", {
          params: { path: { question_id: input.questionId } },
          body: {
            token: input.token,
            selected: input.selected,
            text: input.text,
            self_score: input.selfScore,
            confidence: input.confidence,
            seconds: input.seconds,
          },
        }),
      ),
    // Stats and topic mastery change; the queue snapshot is deliberately left alone.
    onSuccess: () => {
      void queryClient.invalidateQueries({ queryKey: [...ROOT, "stats"] });
      void queryClient.invalidateQueries({ queryKey: [...ROOT, "topics"] });
    },
  });
}

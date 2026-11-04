"use client";

import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";

import { api, unwrap } from "@/lib/api/client";
import type { components } from "@/lib/api/schema";

type Schemas = components["schemas"];
export type ProblemSummary = Schemas["ProblemSummary"];
export type ProblemDetail = Schemas["ProblemDetail"];
export type SubmissionCreate = Schemas["SubmissionCreate"];
export type Submission = Schemas["SubmissionOut"];

export type ProblemFilters = {
  difficulty?: Schemas["Difficulty"];
  kind?: Schemas["Kind"];
  progress?: Schemas["ProgressStatus"];
  topic?: string;
  q?: string;
};

const PRACTICE = ["practice"] as const;

export function useProblems(filters: ProblemFilters = {}) {
  return useQuery({
    queryKey: [...PRACTICE, "problems", filters],
    queryFn: async () =>
      unwrap(await api.GET("/api/v1/practice/problems", { params: { query: filters } })),
  });
}

export function useProblem(slug: string) {
  return useQuery({
    queryKey: [...PRACTICE, "problem", slug],
    queryFn: async () =>
      unwrap(await api.GET("/api/v1/practice/problems/{slug}", { params: { path: { slug } } })),
  });
}

export function useSubmissions(slug: string) {
  return useQuery({
    queryKey: [...PRACTICE, "submissions", slug],
    queryFn: async () =>
      unwrap(
        await api.GET("/api/v1/practice/problems/{slug}/submissions", { params: { path: { slug } } }),
      ),
  });
}

export function useSubmit(slug: string) {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: async (body: SubmissionCreate) =>
      unwrap(
        await api.POST("/api/v1/practice/problems/{slug}/submissions", {
          params: { path: { slug } },
          body,
        }),
      ),
    onSuccess: () => queryClient.invalidateQueries({ queryKey: PRACTICE }),
  });
}

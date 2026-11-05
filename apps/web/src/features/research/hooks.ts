"use client";

import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";

import { api, unwrap } from "@/lib/api/client";
import type { components } from "@/lib/api/schema";

type Schemas = components["schemas"];
export type CheckOut = Schemas["CheckOut"];
export type CheckUpdate = Schemas["CheckUpdate"];
export type OutreachDraft = Schemas["DraftOut"];
export type GenerateRequest = Schemas["GenerateRequest"];
export type OutreachStatus = Schemas["OutreachStatus"];
export type IntelItem = Schemas["ItemOut"];
export type SourceCreate = Schemas["SourceCreate"];

const key = (kind: string, jobId: string) => ["research", kind, jobId] as const;
const path = (job_id: string) => ({ params: { path: { job_id } } });

// --- verification --------------------------------------------------------------------------

export function useVerification(jobId: string) {
  return useQuery({
    queryKey: key("verification", jobId),
    queryFn: async () =>
      unwrap(await api.GET("/api/v1/jobs/{job_id}/verification", path(jobId))),
  });
}

export function useRunVerification(jobId: string) {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: async (ai: boolean) =>
      unwrap(
        await api.POST("/api/v1/jobs/{job_id}/verification/run", {
          params: { path: { job_id: jobId }, query: { ai } },
        }),
      ),
    onSuccess: (data) => {
      queryClient.setQueryData(key("verification", jobId), data);
      void queryClient.invalidateQueries({ queryKey: key("score", jobId) });
    },
  });
}

export function useSetCheck(jobId: string) {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: async (
      args:
        | { key: CheckOut["key"]; body: CheckUpdate }
        | { key: CheckOut["key"]; clear: true },
    ) => {
      const params = { path: { job_id: jobId, key: args.key } };
      return "clear" in args
        ? unwrap(
            await api.DELETE(
              "/api/v1/jobs/{job_id}/verification/checks/{key}",
              { params },
            ),
          )
        : unwrap(
            await api.PUT("/api/v1/jobs/{job_id}/verification/checks/{key}", {
              params,
              body: args.body,
            }),
          );
    },
    onSuccess: (data) =>
      queryClient.setQueryData(key("verification", jobId), data),
  });
}

// --- score ---------------------------------------------------------------------------------

export function useScore(jobId: string) {
  return useQuery({
    queryKey: key("score", jobId),
    queryFn: async () =>
      unwrap(await api.GET("/api/v1/jobs/{job_id}/score", path(jobId))),
  });
}

export function useComputeScore(jobId: string) {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: async (ai: boolean) =>
      unwrap(
        await api.POST("/api/v1/jobs/{job_id}/score", {
          params: { path: { job_id: jobId }, query: { ai } },
        }),
      ),
    onSuccess: (data) => queryClient.setQueryData(key("score", jobId), data),
  });
}

// --- outreach ------------------------------------------------------------------------------

export function useOutreach(jobId: string) {
  return useQuery({
    queryKey: key("outreach", jobId),
    queryFn: async () =>
      unwrap(await api.GET("/api/v1/jobs/{job_id}/outreach", path(jobId))),
  });
}

function useOutreachRefresh(jobId: string) {
  const queryClient = useQueryClient();
  return () => {
    void queryClient.invalidateQueries({ queryKey: key("outreach", jobId) });
    void queryClient.invalidateQueries({ queryKey: ["job", jobId] });
  };
}

export function useGenerateOutreach(jobId: string) {
  const refresh = useOutreachRefresh(jobId);
  return useMutation({
    mutationFn: async (body: GenerateRequest) =>
      unwrap(
        await api.POST("/api/v1/jobs/{job_id}/outreach/generate", {
          params: { path: { job_id: jobId } },
          body,
        }),
      ),
    onSuccess: refresh,
  });
}

export function useCreateOutreach(jobId: string) {
  const refresh = useOutreachRefresh(jobId);
  return useMutation({
    mutationFn: async (body: Schemas["DraftCreate"]) =>
      unwrap(
        await api.POST("/api/v1/jobs/{job_id}/outreach", {
          params: { path: { job_id: jobId } },
          body,
        }),
      ),
    onSuccess: refresh,
  });
}

export function useEditOutreach(jobId: string) {
  const refresh = useOutreachRefresh(jobId);
  return useMutation({
    mutationFn: async (args: { id: string; body: Schemas["DraftEdit"] }) =>
      unwrap(
        await api.PATCH("/api/v1/outreach/{draft_id}", {
          params: { path: { draft_id: args.id } },
          body: args.body,
        }),
      ),
    onSuccess: refresh,
  });
}

export function useMoveOutreach(jobId: string) {
  const refresh = useOutreachRefresh(jobId);
  return useMutation({
    mutationFn: async (args: {
      id: string;
      status: OutreachStatus;
      acknowledge?: boolean;
    }) =>
      unwrap(
        await api.POST("/api/v1/outreach/{draft_id}/status", {
          params: { path: { draft_id: args.id } },
          body: {
            status: args.status,
            acknowledge_flags: args.acknowledge ?? false,
          },
        }),
      ),
    onSuccess: refresh,
  });
}

export function useDeleteOutreach(jobId: string) {
  const refresh = useOutreachRefresh(jobId);
  return useMutation({
    mutationFn: async (id: string) => {
      const { error, response } = await api.DELETE(
        "/api/v1/outreach/{draft_id}",
        {
          params: { path: { draft_id: id } },
        },
      );
      if (!response.ok) unwrap({ error, response });
    },
    onSuccess: refresh,
  });
}

// --- interview intel -----------------------------------------------------------------------

export function useIntel(jobId: string) {
  return useQuery({
    queryKey: key("intel", jobId),
    queryFn: async () =>
      unwrap(await api.GET("/api/v1/jobs/{job_id}/intel", path(jobId))),
  });
}

export function useAddSource(jobId: string) {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: async (body: SourceCreate) =>
      unwrap(
        await api.POST("/api/v1/jobs/{job_id}/intel/sources", {
          params: { path: { job_id: jobId } },
          body,
        }),
      ),
    onSuccess: () =>
      queryClient.invalidateQueries({ queryKey: key("intel", jobId) }),
  });
}

export function useDeleteSource(jobId: string) {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: async (sourceId: string) => {
      const { error, response } = await api.DELETE(
        "/api/v1/jobs/{job_id}/intel/sources/{source_id}",
        {
          params: { path: { job_id: jobId, source_id: sourceId } },
        },
      );
      if (!response.ok) unwrap({ error, response });
    },
    onSuccess: () =>
      queryClient.invalidateQueries({ queryKey: key("intel", jobId) }),
  });
}

export function usePeers(jobId: string) {
  return useMutation({
    mutationFn: async () =>
      unwrap(await api.POST("/api/v1/jobs/{job_id}/intel/peers", path(jobId))),
  });
}

export function useQuestionsToAsk(jobId: string) {
  return useMutation({
    mutationFn: async () =>
      unwrap(
        await api.POST(
          "/api/v1/jobs/{job_id}/intel/questions-to-ask",
          path(jobId),
        ),
      ),
  });
}

export function useSetWebsite(jobId: string) {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: async (website: string | null) =>
      unwrap(
        await api.PATCH("/api/v1/jobs/{job_id}/company", {
          params: { path: { job_id: jobId } },
          body: { website },
        }),
      ),
    onSuccess: () => {
      void queryClient.invalidateQueries({ queryKey: ["job", jobId] });
      void queryClient.invalidateQueries({
        queryKey: key("verification", jobId),
      });
    },
  });
}

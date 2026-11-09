"use client";

import {
  useInfiniteQuery,
  useMutation,
  useQuery,
  useQueryClient,
} from "@tanstack/react-query";

import { api, unwrap } from "@/lib/api/client";
import type {
  ApplicationUpdate,
  ContactCreate,
  JobCreate,
  JobDetail,
  JobUpdate,
  LinkResult,
  Region,
  Status,
  WorkMode,
} from "@/lib/api/types";

export type JobFilters = {
  status?: Status[];
  q?: string;
  region?: Region;
  work_mode?: WorkMode;
  limit?: number;
};

const JOBS = ["jobs"] as const;
const jobKey = (id: string) => ["job", id] as const;

function useRefreshAfterChange() {
  const queryClient = useQueryClient();
  return (detail?: JobDetail) => {
    if (detail) queryClient.setQueryData(jobKey(detail.id), detail);
    void queryClient.invalidateQueries({ queryKey: JOBS });
    void queryClient.invalidateQueries({ queryKey: ["today"] });
  };
}

export function useJobs(filters: JobFilters) {
  return useInfiniteQuery({
    queryKey: [...JOBS, filters],
    initialPageParam: undefined as string | undefined,
    queryFn: async ({ pageParam }) =>
      unwrap(
        await api.GET("/api/v1/jobs", {
          params: { query: { ...filters, cursor: pageParam } },
        }),
      ),
    getNextPageParam: (last) => last.next_cursor ?? undefined,
  });
}

export function useJob(id: string) {
  return useQuery({
    queryKey: jobKey(id),
    queryFn: async () =>
      unwrap(
        await api.GET("/api/v1/jobs/{job_id}", {
          params: { path: { job_id: id } },
        }),
      ),
  });
}

export function useCreateJob() {
  const refresh = useRefreshAfterChange();
  return useMutation({
    mutationFn: async (body: JobCreate) => {
      const result = await api.POST("/api/v1/jobs", { body });
      return { job: unwrap(result), existed: result.response.status === 200 };
    },
    onSuccess: () => refresh(),
  });
}

export function useAddLinks() {
  const refresh = useRefreshAfterChange();
  return useMutation({
    mutationFn: async (links: string[]): Promise<LinkResult[]> =>
      unwrap(await api.POST("/api/v1/jobs/links", { body: { links } })).results,
    onSuccess: () => refresh(),
  });
}

export function useChangeStatus() {
  const refresh = useRefreshAfterChange();
  return useMutation({
    mutationFn: async (args: {
      job: { application: { id: string; version: number } };
      status: Status;
      note?: string;
      reopen?: boolean;
      nextFollowupOn?: string;
    }) =>
      unwrap(
        await api.POST("/api/v1/applications/{application_id}/status", {
          params: { path: { application_id: args.job.application.id } },
          body: {
            status: args.status,
            expected_version: args.job.application.version,
            note: args.note,
            reopen: args.reopen ?? false,
            next_followup_on: args.nextFollowupOn,
          },
        }),
      ),
    onSuccess: refresh,
    // A 409 means someone else changed it: reload so the next attempt uses the new version.
    onError: () => refresh(),
  });
}

export function useUpdateJob(id: string) {
  const refresh = useRefreshAfterChange();
  return useMutation({
    mutationFn: async (body: JobUpdate) =>
      unwrap(
        await api.PATCH("/api/v1/jobs/{job_id}", {
          params: { path: { job_id: id } },
          body,
        }),
      ),
    onSuccess: refresh,
  });
}

export function useUpdateApplication() {
  const refresh = useRefreshAfterChange();
  return useMutation({
    mutationFn: async (args: {
      applicationId: string;
      body: ApplicationUpdate;
    }) =>
      unwrap(
        await api.PATCH("/api/v1/applications/{application_id}", {
          params: { path: { application_id: args.applicationId } },
          body: args.body,
        }),
      ),
    onSuccess: refresh,
  });
}

export function useDeleteJob() {
  const refresh = useRefreshAfterChange();
  return useMutation({
    mutationFn: async (id: string) => {
      const { error, response } = await api.DELETE("/api/v1/jobs/{job_id}", {
        params: { path: { job_id: id } },
      });
      if (!response.ok) unwrap({ error, response });
    },
    onSuccess: () => refresh(),
  });
}

export function useAddContact(jobId: string) {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: async (body: ContactCreate) =>
      unwrap(
        await api.POST("/api/v1/jobs/{job_id}/contacts", {
          params: { path: { job_id: jobId } },
          body,
        }),
      ),
    onSuccess: () => queryClient.invalidateQueries({ queryKey: jobKey(jobId) }),
  });
}

export function useFindContacts(jobId: string) {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: async () =>
      unwrap(
        await api.POST("/api/v1/jobs/{job_id}/contacts/find", {
          params: { path: { job_id: jobId } },
        }),
      ),
    onSuccess: () => queryClient.invalidateQueries({ queryKey: jobKey(jobId) }),
  });
}

export function useDeleteContact(jobId: string) {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: async (contactId: string) => {
      const { error, response } = await api.DELETE(
        "/api/v1/contacts/{contact_id}",
        {
          params: { path: { contact_id: contactId } },
        },
      );
      if (!response.ok) unwrap({ error, response });
    },
    onSuccess: () => queryClient.invalidateQueries({ queryKey: jobKey(jobId) }),
  });
}

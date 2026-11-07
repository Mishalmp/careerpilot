"use client";

import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";

import { api, unwrap } from "@/lib/api/client";
import type { components } from "@/lib/api/schema";

type Schemas = components["schemas"];
export type SearchProfile = Schemas["SearchProfileOut"];
type Full = Schemas["SearchProfileIn"];
/** What you send: the lists and the on/off switch have defaults, so they may be left out. */
export type NewSearchProfile = Omit<Full, "enabled" | "cities" | "keywords" | "exclude"> &
  Partial<Pick<Full, "enabled" | "cities" | "keywords" | "exclude">>;

const KEY = ["discovery", "searches"] as const;

export function useSearches() {
  return useQuery({ queryKey: KEY, queryFn: async () => unwrap(await api.GET("/api/v1/discovery/searches")) });
}

export function useCreateSearch() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: async (body: NewSearchProfile) => unwrap(await api.POST("/api/v1/discovery/searches", { body: body as Full })),
    onSuccess: () => qc.invalidateQueries({ queryKey: KEY }),
  });
}

export function useToggleSearch() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: async ({ id, enabled }: { id: string; enabled: boolean }) =>
      unwrap(await api.PATCH("/api/v1/discovery/searches/{profile_id}", { params: { path: { profile_id: id } }, body: { enabled } })),
    onSuccess: () => qc.invalidateQueries({ queryKey: KEY }),
  });
}

export function useDeleteSearch() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: async (id: string) => {
      const { error, response } = await api.DELETE("/api/v1/discovery/searches/{profile_id}", { params: { path: { profile_id: id } } });
      if (!response.ok) unwrap({ error, response });
    },
    onSuccess: () => qc.invalidateQueries({ queryKey: KEY }),
  });
}

"use client";

import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";

import { api, unwrap } from "@/lib/api/client";
import type { components } from "@/lib/api/schema";

type Schemas = components["schemas"];
export type Analytics = Schemas["AnalyticsOut"];
export type Offer = Schemas["OfferIn"];
export type Story = Schemas["StoryOut"];
export type StoryDraft = Schemas["StoryCreate"];

export function useAnalytics() {
  return useQuery({
    queryKey: ["analytics"],
    queryFn: async () => unwrap(await api.GET("/api/v1/analytics")),
  });
}

// --- offers --------------------------------------------------------------------------------

const RATES = ["offers", "rates"] as const;

export function useRates() {
  return useQuery({
    queryKey: RATES,
    queryFn: async () => unwrap(await api.GET("/api/v1/offers/rates")),
  });
}

export function useSetRate() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: async (body: Schemas["RateIn"]) =>
      unwrap(await api.PUT("/api/v1/offers/rates", { body })),
    onSuccess: () => queryClient.invalidateQueries({ queryKey: RATES }),
  });
}

export function useDeleteRate() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: async (currency: string) => {
      const { error, response } = await api.DELETE(
        "/api/v1/offers/rates/{currency}",
        {
          params: { path: { currency } },
        },
      );
      if (!response.ok) unwrap({ error, response });
    },
    onSuccess: () => queryClient.invalidateQueries({ queryKey: RATES }),
  });
}

export function useCompareOffers() {
  return useMutation({
    mutationFn: async (offers: Offer[]) =>
      unwrap(await api.POST("/api/v1/offers/compare", { body: { offers } })),
  });
}

// --- stories -------------------------------------------------------------------------------

const STORIES = ["stories"] as const;

export function useStories(tag: string, q: string) {
  return useQuery({
    queryKey: [...STORIES, tag, q],
    queryFn: async () =>
      unwrap(
        await api.GET("/api/v1/stories", {
          params: { query: { tag: tag || undefined, q: q || undefined } },
        }),
      ),
  });
}

export function useSaveStory() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: async (args: { id?: string; body: StoryDraft }) =>
      args.id
        ? unwrap(
            await api.PATCH("/api/v1/stories/{story_id}", {
              params: { path: { story_id: args.id } },
              body: args.body,
            }),
          )
        : unwrap(await api.POST("/api/v1/stories", { body: args.body })),
    onSuccess: () => queryClient.invalidateQueries({ queryKey: STORIES }),
  });
}

export function useDeleteStory() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: async (id: string) => {
      const { error, response } = await api.DELETE(
        "/api/v1/stories/{story_id}",
        {
          params: { path: { story_id: id } },
        },
      );
      if (!response.ok) unwrap({ error, response });
    },
    onSuccess: () => queryClient.invalidateQueries({ queryKey: STORIES }),
  });
}

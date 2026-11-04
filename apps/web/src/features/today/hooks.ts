"use client";

import { useQuery } from "@tanstack/react-query";

import { api, unwrap } from "@/lib/api/client";

export function useTodayData() {
  return useQuery({
    queryKey: ["today"],
    queryFn: async () => unwrap(await api.GET("/api/v1/today")),
  });
}

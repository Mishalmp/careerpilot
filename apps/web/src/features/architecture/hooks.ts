"use client";

import { useQuery } from "@tanstack/react-query";

import { api, unwrap } from "@/lib/api/client";
import type { components } from "@/lib/api/schema";

type Schemas = components["schemas"];
export type Diagram = Schemas["Diagram"];
export type DiagramNode = Schemas["DiagramNode"];
export type DiagramEdge = Schemas["DiagramEdge"];
export type Flow = Schemas["Flow"];
export type FlowStep = Schemas["FlowStep"];
export type ConceptSummary = Schemas["ConceptSummary"];
export type ConceptDetail = Schemas["ConceptDetail"];

// The content only changes when the app is updated, so it is safe to keep it for a long time.
const STALE = 10 * 60_000;

export function useDiagrams() {
  return useQuery({
    queryKey: ["architecture", "diagrams"],
    queryFn: async () => unwrap(await api.GET("/api/v1/architecture/diagrams")),
    staleTime: STALE,
  });
}

export function useFlows() {
  return useQuery({
    queryKey: ["architecture", "flows"],
    queryFn: async () => unwrap(await api.GET("/api/v1/architecture/flows")),
    staleTime: STALE,
  });
}

export function useConcepts() {
  return useQuery({
    queryKey: ["architecture", "concepts"],
    queryFn: async () => unwrap(await api.GET("/api/v1/architecture/concepts")),
    staleTime: STALE,
  });
}

export function useConcept(id: string) {
  return useQuery({
    queryKey: ["architecture", "concept", id],
    queryFn: async () =>
      unwrap(
        await api.GET("/api/v1/architecture/concepts/{concept_id}", {
          params: { path: { concept_id: id } },
        }),
      ),
    staleTime: STALE,
  });
}

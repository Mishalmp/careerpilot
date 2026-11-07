"use client";

import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";

import { api, unwrap } from "@/lib/api/client";
import type { components } from "@/lib/api/schema";

type Schemas = components["schemas"];
export type Profile = Schemas["ProfileOut"];
export type ProfileUpdate = Schemas["ProfileUpdate"];
export type ProfileLink = Schemas["ProfileLink"];
export type CvUpload = Schemas["CvUploadOut"];
export type GithubReading = Schemas["GithubReading"];

const KEY = ["profile"] as const;

export function useProfile() {
  return useQuery({ queryKey: KEY, queryFn: async () => unwrap(await api.GET("/api/v1/profile")) });
}

export function useUpdateProfile() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: async (body: ProfileUpdate) => unwrap(await api.PATCH("/api/v1/profile", { body })),
    onSuccess: (data) => qc.setQueryData(KEY, data),
  });
}

export function useAnalyseCv() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: async (text: string) => unwrap(await api.PUT("/api/v1/profile/cv", { body: { text } })),
    onSuccess: (data) => qc.setQueryData(KEY, data),
  });
}

/** Sends the file as multipart form data; the server reads it in memory and does not keep it. */
export function useUploadCv() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: async (file: File) => {
      const form = new FormData();
      form.append("file", file);
      return unwrap(
        await api.POST("/api/v1/profile/cv/file", {
          body: { file: "" },
          bodySerializer: () => form,
        }),
      );
    },
    onSuccess: (data) => qc.setQueryData(KEY, data.profile),
  });
}

export function useForgetCv() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: async () => {
      const { error, response } = await api.DELETE("/api/v1/profile/cv");
      if (!response.ok) unwrap({ error, response });
    },
    onSuccess: () => qc.invalidateQueries({ queryKey: KEY }),
  });
}

export function useCompleteSetup() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: async () => unwrap(await api.POST("/api/v1/profile/setup/complete")),
    onSuccess: (data) => qc.setQueryData(KEY, data),
  });
}

export function useReadGithub() {
  return useMutation({ mutationFn: async () => unwrap(await api.POST("/api/v1/profile/github/read")) });
}

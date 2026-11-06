"use client";

import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { FileText, Plus, X } from "lucide-react";
import { useState } from "react";

import { Button } from "@/components/ui/button";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { Field, Input, Textarea } from "@/components/ui/field";
import { PageHeader } from "@/components/ui/page-header";
import { Skeleton } from "@/components/ui/skeleton";
import { Alert, ErrorState } from "@/components/ui/states";
import { api, unwrap } from "@/lib/api/client";
import type { components } from "@/lib/api/schema";

type Profile = components["schemas"]["ProfileOut"];
const KEY = ["profile"] as const;

function useProfile() {
  return useQuery({ queryKey: KEY, queryFn: async () => unwrap(await api.GET("/api/v1/profile")) });
}

function useAnalyse() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: async (text: string) => unwrap(await api.PUT("/api/v1/profile/cv", { body: { text } })),
    onSuccess: (data) => qc.setQueryData(KEY, data),
  });
}

function useUpdate() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: async (body: { skills?: string[]; role_titles?: string[]; years_experience?: number | null }) =>
      unwrap(await api.PATCH("/api/v1/profile", { body })),
    onSuccess: (data) => qc.setQueryData(KEY, data),
  });
}

/** A list of short items you can remove or add to. Saves each change straight away. */
function Chips({
  label,
  items,
  onChange,
  placeholder,
  busy,
}: {
  label: string;
  items: string[];
  onChange: (next: string[]) => void;
  placeholder: string;
  busy: boolean;
}) {
  const [draft, setDraft] = useState("");
  return (
    <div className="flex flex-col gap-2">
      <h3 className="text-[0.8125rem] font-medium">{label}</h3>
      {items.length === 0 ? (
        <p className="text-sm text-muted-foreground">None yet.</p>
      ) : (
        <ul className="flex flex-wrap gap-1.5" aria-label={label}>
          {items.map((item) => (
            <li key={item} className="inline-flex items-center gap-1 rounded-full bg-accent-soft py-0.5 pl-2.5 pr-1 text-[0.8125rem] text-accent-text">
              {item}
              <button
                type="button"
                aria-label={`Remove ${item}`}
                disabled={busy}
                onClick={() => onChange(items.filter((i) => i !== item))}
                className="rounded-full p-0.5 hover:bg-accent-soft-hover"
              >
                <X className="size-3.5" aria-hidden="true" />
              </button>
            </li>
          ))}
        </ul>
      )}
      <form
        className="flex gap-2"
        onSubmit={(e) => {
          e.preventDefault();
          if (draft.trim()) {
            onChange([...items, draft.trim()]);
            setDraft("");
          }
        }}
      >
        <Input aria-label={`Add to ${label}`} placeholder={placeholder} value={draft} onChange={(e) => setDraft(e.target.value)} className="max-w-xs" />
        <Button type="submit" disabled={busy || !draft.trim()}>
          <Plus aria-hidden="true" /> Add
        </Button>
      </form>
    </div>
  );
}

export function ProfilePage() {
  const profile = useProfile();
  const analyse = useAnalyse();
  const update = useUpdate();
  const [cv, setCv] = useState("");

  return (
    <div className="mx-auto flex w-full max-w-3xl flex-col gap-5">
      <PageHeader
        title="Your profile"
        description="Paste your CV once. Your skills and the roles you fit are read from it, and used to aim research at what you need. Nothing here is hard-coded: edit anything that is wrong."
      />

      <Card>
        <CardHeader>
          <CardTitle>Your CV</CardTitle>
          <CardDescription>
            It is read by rules on this computer. The text is stored here, never shown again and never sent to a search service or a model.
            Only skills and role titles are used in searches.
          </CardDescription>
        </CardHeader>
        <CardContent>
          <form
            className="flex flex-col gap-3"
            onSubmit={(e) => {
              e.preventDefault();
              analyse.mutate(cv, { onSuccess: () => setCv("") });
            }}
          >
            <Field label="CV text" help={profile.data?.has_cv ? "A CV is stored. Paste a new one to replace what was read from it." : "Plain text works best."}>
              {(p) => <Textarea rows={8} value={cv} onChange={(e) => setCv(e.target.value)} {...p} />}
            </Field>
            {analyse.error && (
              <p role="alert" className="text-sm text-danger-text">
                {analyse.error.message}
              </p>
            )}
            <div>
              <Button type="submit" variant="primary" loading={analyse.isPending} disabled={cv.trim().length < 20}>
                <FileText aria-hidden="true" /> Read my CV
              </Button>
            </div>
          </form>
        </CardContent>
      </Card>

      {profile.isPending && <Skeleton className="h-48" aria-busy="true" aria-label="Loading profile" />}
      {profile.isError && <ErrorState title="Could not load your profile" description={profile.error.message} onRetry={() => void profile.refetch()} />}
      {profile.data && <Reading key={profile.data.updated_at ?? "none"} profile={profile.data} busy={update.isPending} onSave={(b) => update.mutate(b)} error={update.error?.message} />}
    </div>
  );
}

function Reading({
  profile,
  busy,
  onSave,
  error,
}: {
  profile: Profile;
  busy: boolean;
  onSave: (body: { skills?: string[]; role_titles?: string[]; years_experience?: number | null }) => void;
  error?: string;
}) {
  const [years, setYears] = useState<string>(profile.years_experience?.toString() ?? "");
  if (!profile.has_cv && profile.skills.length === 0 && profile.role_titles.length === 0) {
    return <Alert tone="info">Nothing yet. Paste your CV above and choose “Read my CV”.</Alert>;
  }
  return (
    <Card>
      <CardHeader>
        <CardTitle>What was read</CardTitle>
        <CardDescription>Changes save as you make them.</CardDescription>
      </CardHeader>
      <CardContent className="flex flex-col gap-5">
        <Chips label="Role titles" items={profile.role_titles} placeholder="e.g. Backend Developer" busy={busy} onChange={(next) => onSave({ role_titles: next })} />
        <Chips label="Skills" items={profile.skills} placeholder="e.g. postgresql" busy={busy} onChange={(next) => onSave({ skills: next })} />
        <form
          className="flex items-end gap-2"
          onSubmit={(e) => {
            e.preventDefault();
            onSave({ years_experience: years.trim() === "" ? null : Number(years) });
          }}
        >
          <Field label="Years of experience">
            {(p) => <Input type="number" min={0} max={60} value={years} onChange={(e) => setYears(e.target.value)} className="w-28" {...p} />}
          </Field>
          <Button type="submit" disabled={busy}>
            Save
          </Button>
        </form>
        {error && (
          <p role="alert" className="text-sm text-danger-text">
            {error}
          </p>
        )}
      </CardContent>
    </Card>
  );
}

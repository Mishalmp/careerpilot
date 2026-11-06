"use client";

import { ChevronLeft, ClipboardCheck } from "lucide-react";
import Link from "next/link";
import { useRouter } from "next/navigation";
import { useState } from "react";

import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { Field, Select } from "@/components/ui/field";
import { PageHeader } from "@/components/ui/page-header";
import { Skeleton } from "@/components/ui/skeleton";
import { EmptyState, ErrorState } from "@/components/ui/states";

import { useCheckpoints, useCreateCheckpoint } from "./checkpointHooks";
import { useLearnTopics } from "./hooks";

/** Start a timed exam from what you have studied, and see past results. */
export function CheckpointsPage() {
  const router = useRouter();
  const topics = useLearnTopics();
  const history = useCheckpoints();
  const create = useCreateCheckpoint();
  const [size, setSize] = useState("10");
  const [passMark, setPassMark] = useState("0.8");
  const [chosen, setChosen] = useState<string[]>([]);

  function toggle(id: string) {
    setChosen((c) => (c.includes(id) ? c.filter((x) => x !== id) : [...c, id]));
  }

  return (
    <div className="flex flex-col gap-6">
      <Link href="/learn" className="inline-flex w-fit items-center gap-1 text-sm text-muted-foreground hover:text-foreground">
        <ChevronLeft className="size-4" aria-hidden="true" /> Learn
      </Link>
      <PageHeader
        title="Checkpoints"
        description="A timed exam from questions you have already studied. Missed questions come back for review."
      />

      <Card>
        <CardHeader>
          <CardTitle>New checkpoint</CardTitle>
          <CardDescription>Only verified multiple-choice questions you have answered before are used.</CardDescription>
        </CardHeader>
        <CardContent>
          <form
            className="flex flex-col gap-4"
            onSubmit={(event) => {
              event.preventDefault();
              create.mutate(
                { topic_ids: chosen, size: Number(size), pass_mark: Number(passMark) },
                { onSuccess: (cp) => router.push(`/learn/checkpoints/${cp.id}`) },
              );
            }}
          >
            <div className="grid gap-3 sm:grid-cols-2">
              <Field label="Questions" help="You get 1.5 minutes per question.">
                {(p) => (
                  <Select value={size} onChange={(e) => setSize(e.target.value)} {...p}>
                    {[5, 10, 15, 20, 30].map((n) => (
                      <option key={n} value={n}>
                        {n}
                      </option>
                    ))}
                  </Select>
                )}
              </Field>
              <Field label="Pass mark">
                {(p) => (
                  <Select value={passMark} onChange={(e) => setPassMark(e.target.value)} {...p}>
                    <option value="0.7">70%</option>
                    <option value="0.8">80%</option>
                    <option value="0.9">90%</option>
                    <option value="1">100%</option>
                  </Select>
                )}
              </Field>
            </div>
            {topics.data && topics.data.length > 0 && (
              <fieldset className="flex flex-col gap-2">
                <legend className="mb-1 text-[0.8125rem] font-medium">
                  Topics <span className="font-normal text-muted-foreground">(none selected means all)</span>
                </legend>
                <div className="flex flex-wrap gap-2">
                  {topics.data.map((t) => (
                    <label
                      key={t.id}
                      className="flex cursor-pointer items-center gap-2 rounded-full border border-border px-3 py-1 text-[0.8125rem] has-[:checked]:border-primary has-[:checked]:bg-accent-soft has-[:checked]:text-accent-text has-[:focus-visible]:outline-2 has-[:focus-visible]:outline-ring"
                    >
                      <input
                        type="checkbox"
                        className="sr-only"
                        checked={chosen.includes(t.id)}
                        onChange={() => toggle(t.id)}
                      />
                      {t.title}
                    </label>
                  ))}
                </div>
              </fieldset>
            )}
            {create.error && (
              <p role="alert" className="text-sm text-danger-text">
                {create.error.message}
              </p>
            )}
            <div>
              <Button type="submit" variant="primary" loading={create.isPending}>
                <ClipboardCheck aria-hidden="true" /> Start checkpoint
              </Button>
            </div>
          </form>
        </CardContent>
      </Card>

      <section aria-labelledby="past-heading" className="flex flex-col gap-3">
        <h2 id="past-heading" className="text-lg font-semibold tracking-tight">
          Past checkpoints
        </h2>
        {history.isPending && <Skeleton className="h-16" aria-busy="true" />}
        {history.isError && <ErrorState title="Could not load past checkpoints" description={history.error.message} />}
        {history.isSuccess && history.data.length === 0 && (
          <EmptyState title="No checkpoints yet" description="Review some questions first, then test yourself here." />
        )}
        {history.isSuccess && history.data.length > 0 && (
          <ul className="divide-y divide-border-subtle rounded-lg border border-border-subtle bg-surface">
            {history.data.map((c) => (
              <li key={c.id} className="flex flex-wrap items-center justify-between gap-2 p-3">
                <Link href={`/learn/checkpoints/${c.id}`} className="font-medium hover:text-accent-text hover:underline">
                  {new Date(c.started_at).toLocaleString()} · {c.size} questions
                </Link>
                {c.status === "in_progress" ? (
                  <Badge tone="accent">In progress</Badge>
                ) : (
                  <span className="flex items-center gap-2">
                    <span className="tabular text-sm">{Math.round((c.score ?? 0) * 100)}%</span>
                    <Badge tone={c.passed ? "success" : "danger"}>{c.passed ? "Passed" : "Not passed"}</Badge>
                  </span>
                )}
              </li>
            ))}
          </ul>
        )}
      </section>
    </div>
  );
}

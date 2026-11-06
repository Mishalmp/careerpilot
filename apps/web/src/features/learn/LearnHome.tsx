"use client";

import { BookOpen, Flame, GraduationCap, ListChecks, Play, Plus, Timer } from "lucide-react";
import Link from "next/link";
import { useState } from "react";

import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardDescription, CardHeader } from "@/components/ui/card";
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog";
import { Field, Input, Select, Textarea } from "@/components/ui/field";
import { PageHeader } from "@/components/ui/page-header";
import { Skeleton } from "@/components/ui/skeleton";
import { EmptyState, ErrorState } from "@/components/ui/states";
import { cn } from "@/lib/utils";

import { type LearnTopic, useCreateTopic, useLearnStats, useLearnTopics } from "./hooks";
import { ResearchInbox } from "./ResearchInbox";
import { useFindings } from "./researchHooks";

function Stat({ label, value, hint, icon: Icon }: { label: string; value: number | string; hint?: string; icon: typeof Timer }) {
  return (
    <Card>
      <CardHeader className="flex-row items-center justify-between space-y-0">
        <CardDescription>{label}</CardDescription>
        <Icon className="size-4 text-muted-foreground" aria-hidden="true" />
      </CardHeader>
      <CardContent className="pt-2">
        <p className="text-3xl font-semibold tracking-tight">{value}</p>
        {hint ? <p className="mt-1 text-xs text-muted-foreground">{hint}</p> : null}
      </CardContent>
    </Card>
  );
}

const PRIORITY = { 1: "High", 2: "Medium", 3: "Low" } as const;

/** A bar with the number beside it: colour is never the only signal. */
function Mastery({ value }: { value: number | null | undefined }) {
  if (value == null) return <span className="text-xs text-muted-foreground">Not reviewed yet</span>;
  return (
    <div className="flex items-center gap-2" role="img" aria-label={`Mastery ${Math.round(value)} percent`}>
      <div className="h-1.5 w-24 overflow-hidden rounded-full bg-surface-hover">
        <div className="h-full rounded-full bg-primary" style={{ width: `${Math.max(2, Math.min(100, value))}%` }} />
      </div>
      <span className="tabular text-xs text-muted-foreground">{Math.round(value)}%</span>
    </div>
  );
}

export function LearnHome() {
  const stats = useLearnStats();
  const topics = useLearnTopics();
  const [adding, setAdding] = useState(false);
  const inbox = useFindings(1);
  const due = (stats.data?.due_now ?? 0) + (stats.data?.new_today_left ?? 0);
  const available = Math.min(due, stats.data?.questions ?? 0);

  return (
    <div className="flex flex-col gap-6">
      <PageHeader
        title="Learn"
        description="Topics and questions you choose, reviewed on a schedule so they stay in memory."
        actions={
          <>
            <Button onClick={() => setAdding(true)}>
              <Plus aria-hidden="true" /> Add topic
            </Button>
            {available > 0 ? (
              <Button asChild variant="primary">
                <Link href="/learn/review">
                  <Play aria-hidden="true" /> Start review ({available})
                </Link>
              </Button>
            ) : (
              <Button variant="primary" disabled>
                <Play aria-hidden="true" /> Start review
              </Button>
            )}
          </>
        }
      />

      {stats.isError ? (
        <ErrorState title="Could not load your progress" description={stats.error.message} onRetry={() => void stats.refetch()} />
      ) : (
        <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-4">
          <Stat label="Due for review" value={stats.data?.due_now ?? "-"} icon={Timer} hint="Questions you may be forgetting" />
          <Stat label="New today" value={stats.data?.new_today_left ?? "-"} icon={ListChecks} hint="Daily allowance left" />
          <Stat label="Streak" value={stats.data ? `${stats.data.streak_days} d` : "-"} icon={Flame} hint="Days in a row with an answer" />
          <Stat label="Questions" value={stats.data?.questions ?? "-"} icon={BookOpen} hint={`${stats.data?.topics ?? 0} topics`} />
        </div>
      )}

      <section aria-labelledby="topics-heading" className="flex flex-col gap-3">
        <h2 id="topics-heading" className="text-lg font-semibold tracking-tight">
          Topics
        </h2>
        {topics.isPending && (
          <div className="flex flex-col gap-2" aria-busy="true" aria-label="Loading topics">
            {[0, 1, 2].map((i) => (
              <Skeleton key={i} className="h-14" />
            ))}
          </div>
        )}
        {topics.isError && (
          <ErrorState title="Could not load topics" description={topics.error.message} onRetry={() => void topics.refetch()} />
        )}
        {topics.isSuccess && topics.data.length === 0 && (
          <EmptyState
            icon={<GraduationCap aria-hidden="true" />}
            title="Nothing to learn yet"
            description="Nothing is predefined. Add a topic you need for the jobs you are applying to, then add questions to it, or open a job and choose “Research interview topics” to get suggestions with sources."
            action={
              <Button variant="primary" onClick={() => setAdding(true)}>
                <Plus aria-hidden="true" /> Add your first topic
              </Button>
            }
          />
        )}
        {topics.isSuccess && topics.data.length > 0 && <TopicTable topics={topics.data} />}
      </section>

      <section id="inbox" aria-labelledby="inbox-heading" className="flex scroll-mt-20 flex-col gap-3">
        <h2 id="inbox-heading" className="text-lg font-semibold tracking-tight">
          Research inbox{inbox.data && inbox.data.total > 0 ? ` (${inbox.data.total})` : ""}
        </h2>
        <ResearchInbox />
      </section>

      <AddTopicDialog open={adding} onOpenChange={setAdding} />
    </div>
  );
}

function TopicTable({ topics }: { topics: LearnTopic[] }) {
  return (
    <div className="overflow-x-auto rounded-lg border border-border-subtle bg-surface">
      <table className="w-full min-w-[40rem] text-left text-[length:var(--text-base)]">
        <caption className="sr-only">Your topics</caption>
        <thead className="border-b border-border-subtle bg-surface-muted">
          <tr>
            {["Topic", "Priority", "Questions", "Mastery"].map((h) => (
              <th key={h} scope="col" className="px-3 py-2 text-xs font-medium text-muted-foreground">
                {h}
              </th>
            ))}
          </tr>
        </thead>
        <tbody className="divide-y divide-border-subtle">
          {topics.map((topic) => (
            <tr key={topic.id} className="transition-colors hover:bg-surface-muted">
              <td className="px-3 py-3">
                <Link
                  href={`/learn/topics/${topic.id}`}
                  className="font-medium text-foreground hover:text-accent-text hover:underline"
                >
                  {topic.title}
                </Link>
                {topic.area ? <div className="text-xs text-muted-foreground">{topic.area}</div> : null}
              </td>
              <td className="px-3 py-3">
                <Badge tone={topic.priority === 1 ? "accent" : "neutral"}>
                  {PRIORITY[topic.priority as 1 | 2 | 3] ?? "Medium"}
                </Badge>
              </td>
              <td className={cn("px-3 py-3", topic.question_count === 0 && "text-muted-foreground")}>
                {topic.question_count}
              </td>
              <td className="px-3 py-3">
                <Mastery value={topic.mastery} />
              </td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}

function AddTopicDialog({ open, onOpenChange }: { open: boolean; onOpenChange: (open: boolean) => void }) {
  const create = useCreateTopic();
  const [title, setTitle] = useState("");
  const [area, setArea] = useState("");
  const [priority, setPriority] = useState("2");
  const [summary, setSummary] = useState("");

  function close(next: boolean) {
    if (!next) {
      setTitle("");
      setArea("");
      setPriority("2");
      setSummary("");
      create.reset();
    }
    onOpenChange(next);
  }

  return (
    <Dialog open={open} onOpenChange={close}>
      <DialogContent>
        <form
          className="flex flex-col gap-4"
          onSubmit={(event) => {
            event.preventDefault();
            create.mutate(
              { title, area: area || undefined, priority: Number(priority), summary: summary || undefined },
              { onSuccess: () => close(false) },
            );
          }}
        >
          <DialogHeader>
            <DialogTitle>Add a topic</DialogTitle>
            <DialogDescription>Something you need to know, such as “database transactions”.</DialogDescription>
          </DialogHeader>
          <Field label="Title" required>
            {(p) => <Input required value={title} onChange={(e) => setTitle(e.target.value)} {...p} />}
          </Field>
          <div className="grid gap-3 sm:grid-cols-2">
            <Field label="Area" help="Optional grouping, such as Databases.">
              {(p) => <Input value={area} onChange={(e) => setArea(e.target.value)} {...p} />}
            </Field>
            <Field label="Priority">
              {(p) => (
                <Select value={priority} onChange={(e) => setPriority(e.target.value)} {...p}>
                  <option value="1">High</option>
                  <option value="2">Medium</option>
                  <option value="3">Low</option>
                </Select>
              )}
            </Field>
          </div>
          <Field label="Summary">
            {(p) => <Textarea rows={3} value={summary} onChange={(e) => setSummary(e.target.value)} {...p} />}
          </Field>
          <p role="alert" className="min-h-5 text-sm text-danger-text">
            {create.error?.message}
          </p>
          <DialogFooter>
            <Button type="button" onClick={() => close(false)}>
              Cancel
            </Button>
            <Button type="submit" variant="primary" loading={create.isPending}>
              Add topic
            </Button>
          </DialogFooter>
        </form>
      </DialogContent>
    </Dialog>
  );
}

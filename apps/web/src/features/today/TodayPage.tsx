"use client";

import { ArrowRight, BookOpen, Briefcase, CalendarClock, Plus } from "lucide-react";
import Link from "next/link";

import { Button } from "@/components/ui/button";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { PageHeader } from "@/components/ui/page-header";
import { Skeleton } from "@/components/ui/skeleton";
import { EmptyState, ErrorState } from "@/components/ui/states";
import { useUpdateDay } from "@/features/prep/hooks";
import { FollowUp } from "@/features/tracker/JobsTable";
import { StatusBadge } from "@/features/tracker/StatusBadge";
import type { TodayPrep } from "@/lib/api/types";

import { useTodayData } from "./hooks";

function Stat({ label, value, hint, icon: Icon }: { label: string; value: number | string; hint?: string; icon: typeof Briefcase }) {
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

export function TodayPage() {
  const today = useTodayData();

  if (today.isPending) {
    return (
      <div className="flex flex-col gap-6" aria-busy="true" aria-label="Loading today">
        <Skeleton className="h-9 w-40" />
        <div className="grid gap-4 sm:grid-cols-3">
          {[0, 1, 2].map((i) => (
            <Skeleton key={i} className="h-28" />
          ))}
        </div>
        <Skeleton className="h-48" />
      </div>
    );
  }
  if (today.isError) {
    return (
      <ErrorState title="Could not load Today" description={today.error.message} onRetry={() => void today.refetch()} />
    );
  }
  const { prep, pipeline, due_followups: followups } = today.data;
  const active = pipeline.filter((p) => p.count > 0);
  const totalJobs = pipeline.reduce((sum, p) => sum + p.count, 0);
  const reviewsDue = prep.due_reviews.length;

  return (
    <div className="flex flex-col gap-6">
      <PageHeader
        title="Today"
        description="What needs your attention, chosen by rules, not by a model."
        actions={
          <Button asChild variant="primary">
            <Link href="/jobs">
              <Plus aria-hidden="true" /> Add job
            </Link>
          </Button>
        }
      />

      <div className="grid gap-4 sm:grid-cols-3">
        <Stat label="Jobs tracked" value={totalJobs} icon={Briefcase} hint={active.length ? `${active.length} stages in use` : "Start by adding one"} />
        <Stat label="Follow-ups due" value={followups.length} icon={CalendarClock} hint={followups.length ? "Open them below" : "Nothing overdue"} />
        <Stat label="Topics to review" value={reviewsDue} icon={BookOpen} hint={reviewsDue ? "From your prep plan" : "All caught up"} />
      </div>

      <div className="grid gap-4 lg:grid-cols-2">
        <Card>
          <CardHeader>
            <CardTitle>Prep</CardTitle>
          </CardHeader>
          <CardContent>
            <PrepToday prep={prep} />
          </CardContent>
        </Card>

        <Card>
          <CardHeader>
            <CardTitle>Follow-ups due</CardTitle>
          </CardHeader>
          <CardContent>
            {followups.length === 0 ? (
              <p className="text-sm text-muted-foreground">Nothing is due.</p>
            ) : (
              <ul className="flex flex-col divide-y divide-border-subtle text-sm">
                {followups.map((job) => (
                  <li key={job.id} className="flex items-center justify-between gap-3 py-2 first:pt-0 last:pb-0">
                    <Link href={`/jobs/${job.id}`} className="min-w-0 truncate hover:underline">
                      <strong className="font-medium">{job.company.name}</strong>
                      <span className="text-muted-foreground"> · {job.title}</span>
                    </Link>
                    <span className="flex shrink-0 items-center gap-2">
                      <StatusBadge status={job.application.status} />
                      <FollowUp job={job} />
                    </span>
                  </li>
                ))}
              </ul>
            )}
          </CardContent>
        </Card>
      </div>

      <Card>
        <CardHeader>
          <CardTitle>Pipeline</CardTitle>
        </CardHeader>
        <CardContent>
          {active.length === 0 ? (
            <EmptyState
              title="No jobs yet"
              description="Add the first job you are considering and it will show up here."
              action={
                <Button asChild variant="primary">
                  <Link href="/jobs">
                    Add your first job <ArrowRight aria-hidden="true" />
                  </Link>
                </Button>
              }
              className="border-0 p-0 py-4"
            />
          ) : (
            <ul className="flex flex-wrap gap-x-5 gap-y-2">
              {active.map((p) => (
                <li key={p.status} className="flex items-center gap-2 text-sm">
                  <StatusBadge status={p.status} /> <span className="font-medium">{p.count}</span>
                </li>
              ))}
            </ul>
          )}
        </CardContent>
      </Card>
    </div>
  );
}

function PrepToday({ prep }: { prep: TodayPrep }) {
  const update = useUpdateDay();
  const reviews = prep.due_reviews;

  return (
    <div className="flex flex-col gap-3 text-sm">
      {prep.phase === "not_configured" && (
        <p>
          The 45-day plan has not started.{" "}
          <Link href="/prep" className="font-medium text-accent-text underline underline-offset-2">
            Open Prep
          </Link>{" "}
          to load it and pick day 1.
        </p>
      )}
      {prep.phase === "upcoming" && <p>The plan starts on {prep.start_date}.</p>}
      {prep.phase === "finished" && <p>The 45-day plan is finished. Review your weak topics.</p>}
      {prep.phase === "active" && prep.day && (
        <div className="flex flex-col gap-1.5">
          <p className="font-medium">
            Day {prep.day_number} of {prep.total_days}: {prep.day.focus}
          </p>
          <p>
            <strong className="font-medium">Learn:</strong> {prep.day.core_topics}
          </p>
          <p>
            <strong className="font-medium">Practise:</strong> {prep.day.practice}
          </p>
          <p>
            <strong className="font-medium">Say aloud:</strong> {prep.day.speaking}
          </p>
          <p className="text-muted-foreground">
            {prep.day.hours} h planned · {prep.minutes_today} min studied today · {prep.day.status}
          </p>
          {prep.day.status !== "Done" && (
            <div>
              <Button size="sm" onClick={() => update.mutate({ day: prep.day!.day, status: "Done" })}>
                Mark day done
              </Button>
            </div>
          )}
        </div>
      )}
      {reviews.length > 0 && (
        <div>
          <p className="font-medium">Due for review</p>
          <ul className="mt-1 list-inside list-disc text-muted-foreground">
            {reviews.map((topic) => (
              <li key={topic.id}>{topic.title}</li>
            ))}
          </ul>
        </div>
      )}
    </div>
  );
}

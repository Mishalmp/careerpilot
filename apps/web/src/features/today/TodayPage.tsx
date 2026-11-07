"use client";

import { ArrowRight, BookOpen, Briefcase, CalendarClock, ClipboardCheck, Inbox, ListChecks, Plus, Rocket } from "lucide-react";
import Link from "next/link";

import { useTasks } from "@/features/activity/hooks";
import { useApplyQueue } from "@/features/apply/hooks";
import { useLearnStats } from "@/features/learn/hooks";
import { useFindings } from "@/features/learn/researchHooks";
import { useProfile } from "@/features/profile/hooks";
import { useUpdateDay } from "@/features/prep/hooks";
import { FollowUp } from "@/features/tracker/JobsTable";
import { StatusBadge } from "@/features/tracker/StatusBadge";
import { Avatar } from "@/components/ui/avatar";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { PageHeader } from "@/components/ui/page-header";
import { ProgressBar } from "@/components/ui/progress";
import { Skeleton } from "@/components/ui/skeleton";
import { StatTile } from "@/components/ui/stat";
import { EmptyState, ErrorState } from "@/components/ui/states";
import type { TodayPrep } from "@/lib/api/types";

import { useTodayData } from "./hooks";

function greeting(): string {
  const hour = new Date().getHours();
  return hour < 5 ? "Working late" : hour < 12 ? "Good morning" : hour < 18 ? "Good afternoon" : "Good evening";
}

/** Shown until account setup is finished: what is missing, and one button to do it. */
function SetupBanner({ missing, done }: { missing: string[]; done: number }) {
  return (
    <div className="flex flex-col gap-3 rounded-lg border border-primary/30 bg-accent-soft p-4 sm:flex-row sm:items-center sm:justify-between">
      <div className="flex min-w-0 items-start gap-3">
        <Rocket className="mt-0.5 size-5 shrink-0 text-accent-text" aria-hidden="true" />
        <div className="min-w-0">
          <p className="font-medium text-accent-text">Finish setting up your account</p>
          <p className="text-sm text-accent-text">
            CareerPilot works from what you tell it, not from built-in details. Still needed: {missing.join(", ")}.
          </p>
          <ProgressBar label="Setup progress" value={(done / 4) * 100} className="mt-2 max-w-xs" />
        </div>
      </div>
      <Button asChild variant="primary" className="shrink-0">
        <Link href="/profile">
          Continue setup <ArrowRight aria-hidden="true" />
        </Link>
      </Button>
    </div>
  );
}

export function TodayPage() {
  const today = useTodayData();
  const learn = useLearnStats();
  const inbox = useFindings(1);
  const apply = useApplyQueue(false);
  const profile = useProfile();
  const tasks = useTasks();

  if (today.isPending) {
    return (
      <div className="flex flex-col gap-6" aria-busy="true" aria-label="Loading today">
        <Skeleton className="h-9 w-40" />
        <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-3">
          {[0, 1, 2, 3, 4, 5].map((i) => (
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
  const me = profile.data;
  const firstName = me?.full_name?.trim().split(/\s+/)[0];
  const failed = tasks.data?.counts.failed ?? 0;

  return (
    <div className="flex flex-col gap-6">
      <PageHeader
        title={
          <span className="flex items-center gap-3">
            {me?.full_name ? <Avatar name={me.full_name} className="size-10" /> : null}
            {firstName ? `${greeting()}, ${firstName}` : "Today"}
          </span>
        }
        description="What needs your attention, chosen by rules, not by a model."
        actions={
          <Button asChild variant="primary">
            <Link href="/jobs">
              <Plus aria-hidden="true" /> Add job
            </Link>
          </Button>
        }
      />

      {me && !me.setup.complete && <SetupBanner missing={me.setup.missing} done={4 - me.setup.missing.length} />}

      <div className="grid grid-cols-2 gap-3 lg:grid-cols-3 lg:gap-4">
        <StatTile
          href="/apply"
          label="Jobs ready to review"
          value={apply.data ? apply.data.ready_count : "-"}
          icon={ClipboardCheck}
          tone="success"
          hint={apply.data && apply.data.ready_count > 0 ? "Pay, interview and company details are waiting" : "Build today’s list on the Apply page"}
        />
        <StatTile href="/jobs" label="Jobs tracked" value={totalJobs} icon={Briefcase} hint={active.length ? `${active.length} ${active.length === 1 ? "stage" : "stages"} in use` : "Start by adding one"} />
        <StatTile
          label="Follow-ups due"
          value={followups.length}
          icon={CalendarClock}
          tone={followups.length ? "warning" : "neutral"}
          hint={followups.length ? "Open them below" : "Nothing overdue"}
        />
        <StatTile
          href="/learn/review"
          label="Questions due"
          value={learn.data ? learn.data.due_now : "-"}
          icon={BookOpen}
          tone="violet"
          hint={learn.data ? `${learn.data.new_today_left} new allowed today · streak ${learn.data.streak_days} d` : "Learn"}
        />
        <StatTile
          href="/learn#inbox"
          label="Research inbox"
          value={inbox.data ? inbox.data.total : "-"}
          icon={Inbox}
          hint={inbox.data && inbox.data.total > 0 ? "Approve or reject" : "Nothing waiting"}
        />
        <StatTile
          href="/tasks"
          label="Background tasks failed"
          value={tasks.data ? failed : "-"}
          icon={ListChecks}
          tone={failed ? "danger" : "neutral"}
          hint={failed ? "Open Activity to retry" : "All background work is fine"}
        />
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

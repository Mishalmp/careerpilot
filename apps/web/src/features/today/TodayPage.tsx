"use client";

import Link from "next/link";

import { button, card, muted } from "@/components/ui";
import { useUpdateDay } from "@/features/prep/hooks";
import { FollowUp } from "@/features/tracker/JobsTable";
import { StatusBadge } from "@/features/tracker/StatusBadge";
import type { TodayPrep } from "@/lib/api/types";

import { useTodayData } from "./hooks";

export function TodayPage() {
  const today = useTodayData();

  if (today.isPending) return <p className={muted}>Loading...</p>;
  if (today.isError) {
    return (
      <p role="alert" className="text-red-600 dark:text-red-400">
        Could not load Today: {today.error.message}
      </p>
    );
  }
  const { prep, pipeline, due_followups: followups } = today.data;
  const active = pipeline.filter((p) => p.count > 0);

  return (
    <div className="space-y-6">
      <h1 className="text-2xl font-semibold">Today</h1>

      <div className="grid gap-6 lg:grid-cols-2">
        <section className={`${card} space-y-2`}>
          <h2 className="font-semibold">Prep</h2>
          <PrepToday prep={prep} />
        </section>

        <section className={`${card} space-y-2`}>
          <h2 className="font-semibold">Follow-ups due</h2>
          {followups.length === 0 && <p className={muted}>Nothing is due.</p>}
          <ul className="space-y-2 text-sm">
            {followups.map((job) => (
              <li key={job.id} className="flex items-center justify-between gap-3">
                <Link href={`/jobs/${job.id}`} className="hover:underline">
                  <strong>{job.company.name}</strong> · {job.title}
                </Link>
                <span className="flex items-center gap-2">
                  <StatusBadge status={job.application.status} />
                  <FollowUp job={job} />
                </span>
              </li>
            ))}
          </ul>
        </section>
      </div>

      <section className={`${card} space-y-2`}>
        <h2 className="font-semibold">Pipeline</h2>
        {active.length === 0 ? (
          <p className={muted}>
            No jobs yet. <Link href="/jobs" className="underline">Add your first job</Link>.
          </p>
        ) : (
          <ul className="flex flex-wrap gap-2">
            {active.map((p) => (
              <li key={p.status} className="flex items-center gap-2 text-sm">
                <StatusBadge status={p.status} /> {p.count}
              </li>
            ))}
          </ul>
        )}
      </section>
    </div>
  );
}

function PrepToday({ prep }: { prep: TodayPrep }) {
  const update = useUpdateDay();
  const reviews = prep.due_reviews;

  return (
    <div className="space-y-3 text-sm">
      {prep.phase === "not_configured" && (
        <p>
          The 45-day plan has not started. <Link href="/prep" className="underline">Open Prep</Link> to load it and
          pick day 1.
        </p>
      )}
      {prep.phase === "upcoming" && <p>The plan starts on {prep.start_date}.</p>}
      {prep.phase === "finished" && <p>The 45-day plan is finished. Review your weak topics.</p>}
      {prep.phase === "active" && prep.day && (
        <div className="space-y-1">
          <p className="font-medium">
            Day {prep.day_number} of {prep.total_days}: {prep.day.focus}
          </p>
          <p><strong>Learn:</strong> {prep.day.core_topics}</p>
          <p><strong>Practise:</strong> {prep.day.practice}</p>
          <p><strong>Say aloud:</strong> {prep.day.speaking}</p>
          <p className={muted}>
            {prep.day.hours} h planned · {prep.minutes_today} min studied today · {prep.day.status}
          </p>
          {prep.day.status !== "Done" && (
            <button
              type="button"
              className={button}
              onClick={() => update.mutate({ day: prep.day!.day, status: "Done" })}
            >
              Mark day done
            </button>
          )}
        </div>
      )}
      {reviews.length > 0 && (
        <div>
          <p className="font-medium">Due for review</p>
          <ul className="list-inside list-disc">
            {reviews.map((topic) => (
              <li key={topic.id}>{topic.title}</li>
            ))}
          </ul>
        </div>
      )}
    </div>
  );
}

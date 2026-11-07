"use client";

import Link from "next/link";
import { useRouter } from "next/navigation";
import { useState } from "react";

import {
  button,
  card,
  input,
  muted,
  primaryButton,
  select,
} from "@/components/ui";
import { useJobs } from "@/features/tracker/hooks";

import { useDeleteMock, useMockSessions, useStartMock } from "./hooks";
import { PageHeader } from "@/components/ui/page-header";

function StartForm() {
  const router = useRouter();
  const start = useStartMock();
  const jobs = useJobs({});
  const [focus, setFocus] = useState("");
  const [jobId, setJobId] = useState("");
  const [questions, setQuestions] = useState(5);
  const options = jobs.data?.pages.flatMap((page) => page.items) ?? [];

  return (
    <form
      className={`${card} space-y-3`}
      onSubmit={(e) => {
        e.preventDefault();
        start.mutate(
          { job_id: jobId || null, focus: focus.trim() || null, questions },
          { onSuccess: (data) => router.push(`/mock/${data.id}`) },
        );
      }}
    >
      <h2 className="font-semibold">Start a mock interview</h2>
      <p className="text-sm text-muted-foreground">
        The model plays the interviewer: one question at a time, a score and
        feedback on each answer, and a summary of weak topics at the end. Pick a
        job to follow its description and any interview intel you collected, or
        give a topic.
      </p>
      <div className="grid gap-3 sm:grid-cols-2">
        <label className="space-y-1 text-sm">
          <span>Job</span>
          <select
            className={`${select} w-full`}
            value={jobId}
            onChange={(e) => setJobId(e.target.value)}
          >
            <option value="">No job, just a topic</option>
            {options.map((job) => (
              <option key={job.id} value={job.id}>
                {job.company.name} · {job.title}
              </option>
            ))}
          </select>
        </label>
        <label className="space-y-1 text-sm">
          <span>Topic{jobId ? " (optional)" : ""}</span>
          <input
            className={input}
            placeholder="SQL, system design, Python..."
            value={focus}
            onChange={(e) => setFocus(e.target.value)}
            required={!jobId}
          />
        </label>
      </div>
      <label className="flex items-center gap-2 text-sm">
        <span>Questions</span>
        <select
          className={select}
          value={questions}
          onChange={(e) => setQuestions(Number(e.target.value))}
        >
          {[3, 4, 5, 6, 7, 8].map((n) => (
            <option key={n}>{n}</option>
          ))}
        </select>
      </label>
      <button
        type="submit"
        className={primaryButton}
        disabled={start.isPending}
      >
        {start.isPending ? "Preparing the first question..." : "Start"}
      </button>
      {start.error && (
        <p role="alert" className="text-sm text-danger-text">
          {start.error.message}
        </p>
      )}
    </form>
  );
}

export function MockPage() {
  const sessions = useMockSessions();
  const remove = useDeleteMock();

  return (
    <div className="space-y-6">
      <PageHeader title="Mock interviews" />
      <StartForm />
      <section className="space-y-2" aria-labelledby="past-heading">
        <h2 id="past-heading" className="font-semibold">
          Past interviews
        </h2>
        {sessions.isPending && <p className={muted}>Loading...</p>}
        {sessions.isError && (
          <p role="alert">Could not load them: {sessions.error.message}</p>
        )}
        {sessions.data?.length === 0 && <p className={muted}>None yet.</p>}
        <ul className="space-y-2">
          {sessions.data?.map((s) => (
            <li
              key={s.id}
              className={`${card} flex flex-wrap items-center justify-between gap-2`}
            >
              <Link
                href={`/mock/${s.id}`}
                className="underline underline-offset-2"
              >
                {s.title}
              </Link>
              <span className={muted}>
                {s.finished ? "finished" : "in progress"} · {s.answered}/
                {s.total_questions} answered
                {s.average !== null && ` · average ${s.average}/5`} ·{" "}
                {new Date(s.created_at).toLocaleDateString()}
              </span>
              <button
                type="button"
                className={button}
                disabled={remove.isPending}
                onClick={() => {
                  if (window.confirm(`Delete "${s.title}"?`))
                    remove.mutate(s.id);
                }}
              >
                Delete
              </button>
            </li>
          ))}
        </ul>
      </section>
    </div>
  );
}

"use client";

import { useState } from "react";

import { button, card, muted, select } from "@/components/ui";

import {
  type TaskStatus,
  useRetryFailed,
  useRetryTask,
  useTasks,
} from "./hooks";

const KIND_LABEL = {
  discover: "Read a job board",
  daily_digest: "Build the daily digest",
  backup: "Back up the database",
  research: "Research interview topics",
} as const;

export function TasksPage() {
  const [status, setStatus] = useState<TaskStatus | "all">("all");
  const tasks = useTasks(status === "all" ? undefined : status);
  const retry = useRetryTask();
  const retryAll = useRetryFailed();
  const counts = tasks.data?.counts;

  return (
    <div className="space-y-4">
      <h1 className="text-2xl font-semibold">Background tasks</h1>
      <p className={muted}>
        Job boards are read and the digest is built automatically each morning
        while CareerPilot is running. Failures stay here until you retry them.
      </p>
      {counts && (
        <p className="text-sm">
          {counts.queued} waiting · {counts.running} running ·{" "}
          {counts.succeeded} done ·{" "}
          <span
            className={
              counts.failed > 0
                ? "font-medium text-danger-text "
                : ""
            }
          >
            {counts.failed} failed
          </span>
        </p>
      )}
      <div className="flex flex-wrap items-center gap-2">
        <select
          className={select}
          aria-label="Show"
          value={status}
          onChange={(e) => setStatus(e.target.value as TaskStatus | "all")}
        >
          <option value="all">All</option>
          <option value="failed">Failed</option>
          <option value="queued">Waiting</option>
          <option value="running">Running</option>
          <option value="succeeded">Done</option>
        </select>
        {counts && counts.failed > 0 && (
          <button
            type="button"
            className={button}
            disabled={retryAll.isPending}
            onClick={() => retryAll.mutate()}
          >
            Retry all failed
          </button>
        )}
      </div>
      {tasks.isPending && <p className={muted}>Loading...</p>}
      {tasks.isError && (
        <p role="alert">Could not load tasks: {tasks.error.message}</p>
      )}
      {tasks.data?.items.length === 0 && <p className={muted}>No tasks yet.</p>}
      <ul className="space-y-2">
        {tasks.data?.items.map((task) => (
          <li key={task.id} className={`${card} space-y-1`}>
            <div className="flex flex-wrap items-center justify-between gap-2 text-sm">
              <span className="font-medium">{KIND_LABEL[task.kind]}</span>
              <span
                className={
                  task.status === "failed"
                    ? "text-danger-text "
                    : muted
                }
              >
                {task.status} · attempt {task.attempts}/{task.max_attempts} ·{" "}
                {new Date(task.created_at).toLocaleString()}
              </span>
            </div>
            {task.error && (
              <p className="text-sm text-danger-text">
                {task.error}
              </p>
            )}
            {task.status === "queued" && task.attempts > 0 && (
              <p className={muted}>
                Next try {new Date(task.run_after).toLocaleTimeString()}.
              </p>
            )}
            {task.status === "failed" && (
              <button
                type="button"
                className={button}
                disabled={retry.isPending}
                onClick={() => retry.mutate(task.id)}
              >
                Retry
              </button>
            )}
          </li>
        ))}
      </ul>
      {(retry.error ?? retryAll.error) && (
        <p role="alert" className="text-sm text-danger-text">
          {(retry.error ?? retryAll.error)?.message}
        </p>
      )}
    </div>
  );
}

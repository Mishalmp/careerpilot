"use client";

import { useDeferredValue, useState } from "react";

import { button, input, muted, primaryButton, select } from "@/components/ui";
import type { Status } from "@/lib/api/types";

import { AddJobDialog } from "./AddJobDialog";
import { useJobs } from "./hooks";
import { JobsBoard } from "./JobsBoard";
import { JobsTable } from "./JobsTable";
import { STATUSES } from "./status";
import { useStatusChanger } from "./StatusChanger";

type View = "table" | "board";

export function JobsPage() {
  const [view, setView] = useState<View>("table");
  const [adding, setAdding] = useState(false);
  const [search, setSearch] = useState("");
  const [status, setStatus] = useState<Status | "">("");
  const q = useDeferredValue(search.trim());

  const filters = {
    q: q || undefined,
    status: status ? [status] : undefined,
    // The board needs everything in view at once; the table pages as you scroll.
    limit: view === "board" ? 200 : 50,
  };
  const jobs = useJobs(filters);
  const changer = useStatusChanger();
  const items = jobs.data?.pages.flatMap((page) => page.items) ?? [];
  const hasMore = jobs.hasNextPage;

  return (
    <div className="space-y-4">
      <div className="flex flex-wrap items-center gap-3">
        <h1 className="mr-auto text-2xl font-semibold">Jobs</h1>
        <input
          type="search"
          aria-label="Search company or role"
          placeholder="Search company or role"
          value={search}
          onChange={(event) => setSearch(event.target.value)}
          className={`${input} max-w-60`}
        />
        <select
          aria-label="Filter by status"
          value={status}
          onChange={(event) => setStatus(event.target.value as Status | "")}
          className={select}
        >
          <option value="">All statuses</option>
          {STATUSES.map((s) => (
            <option key={s}>{s}</option>
          ))}
        </select>
        <div role="group" aria-label="View" className="flex">
          {(["table", "board"] as const).map((v) => (
            <button
              key={v}
              type="button"
              aria-pressed={view === v}
              onClick={() => setView(v)}
              className={`${button} capitalize ${view === v ? "bg-surface-hover " : ""}`}
            >
              {v}
            </button>
          ))}
        </div>
        <a href="/api/v1/jobs/export.csv" download className={button}>
          Export CSV
        </a>
        <button type="button" onClick={() => setAdding(true)} className={primaryButton}>
          Add job
        </button>
      </div>

      {changer.error && (
        <p role="alert" className="text-sm text-danger-text">
          {changer.error}
        </p>
      )}

      {jobs.isPending && <p className={muted}>Loading...</p>}
      {jobs.isError && (
        <p role="alert" className="text-danger-text">
          Could not load jobs: {jobs.error.message}
        </p>
      )}
      {jobs.isSuccess && items.length === 0 && (
        <p className={muted}>
          {q || status
            ? "No jobs match these filters."
            : "No jobs yet. Add one, or import your workbook with `careerpilot import-tracker`."}
        </p>
      )}

      {items.length > 0 &&
        (view === "table" ? (
          <JobsTable jobs={items} onStatus={changer.request} />
        ) : (
          <JobsBoard jobs={items} onStatus={changer.request} />
        ))}

      {hasMore && view === "table" && (
        <button
          type="button"
          onClick={() => jobs.fetchNextPage()}
          disabled={jobs.isFetchingNextPage}
          className={button}
        >
          {jobs.isFetchingNextPage ? "Loading..." : "Load more"}
        </button>
      )}
      {hasMore && view === "board" && (
        <p className={muted}>Showing the 200 most recently active jobs. Use search to narrow down.</p>
      )}

      <AddJobDialog open={adding} onClose={() => setAdding(false)} />
      {changer.dialog}
    </div>
  );
}

"use client";

import { Briefcase, Download, LayoutGrid, Plus, Rows3, Search } from "lucide-react";
import { useDeferredValue, useState } from "react";

import { Button } from "@/components/ui/button";
import { Input, Select } from "@/components/ui/field";
import { PageHeader } from "@/components/ui/page-header";
import { Skeleton } from "@/components/ui/skeleton";
import { EmptyState, ErrorState } from "@/components/ui/states";
import type { Status } from "@/lib/api/types";
import { cn } from "@/lib/utils";

import { AddJobDialog } from "./AddJobDialog";
import { useJobs } from "./hooks";
import { JobsBoard } from "./JobsBoard";
import { JobsTable } from "./JobsTable";
import { STATUSES } from "./status";
import { useStatusChanger } from "./StatusChanger";

type View = "table" | "board";

const VIEWS = [
  { id: "table", label: "Table", Icon: Rows3 },
  { id: "board", label: "Board", Icon: LayoutGrid },
] as const;

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
  const filtered = Boolean(q || status);

  return (
    <div className="flex flex-col gap-5">
      <PageHeader
        title="Jobs"
        description="Every application, from first look to offer."
        actions={
          <>
            <Button asChild variant="secondary">
              <a href="/api/v1/jobs/export.csv" download>
                <Download aria-hidden="true" /> Export CSV
              </a>
            </Button>
            <Button variant="primary" onClick={() => setAdding(true)}>
              <Plus aria-hidden="true" /> Add job
            </Button>
          </>
        }
      />

      <div className="flex flex-wrap items-center gap-2">
        <div className="relative w-full sm:w-72">
          <Search
            className="pointer-events-none absolute left-2.5 top-1/2 size-4 -translate-y-1/2 text-muted-foreground"
            aria-hidden="true"
          />
          <Input
            type="search"
            aria-label="Search company or role"
            placeholder="Search company or role"
            value={search}
            onChange={(event) => setSearch(event.target.value)}
            className="pl-8"
          />
        </div>
        <Select
          aria-label="Filter by status"
          value={status}
          onChange={(event) => setStatus(event.target.value as Status | "")}
          className="w-auto"
        >
          <option value="">All statuses</option>
          {STATUSES.map((s) => (
            <option key={s}>{s}</option>
          ))}
        </Select>
        <div
          role="group"
          aria-label="View"
          className="ml-auto inline-flex rounded-md border border-input bg-surface p-0.5"
        >
          {VIEWS.map(({ id, label, Icon }) => (
            <button
              key={id}
              type="button"
              aria-pressed={view === id}
              onClick={() => setView(id)}
              className={cn(
                "inline-flex h-[calc(var(--control-h)-0.5rem)] items-center gap-1.5 rounded px-2.5 text-[0.8125rem] font-medium",
                "transition-colors duration-[var(--dur-fast)]",
                view === id ? "bg-accent-soft text-accent-text" : "text-muted-foreground hover:text-foreground",
              )}
            >
              <Icon className="size-3.5" aria-hidden="true" /> {label}
            </button>
          ))}
        </div>
      </div>

      {changer.error && (
        <p role="alert" className="text-sm text-danger-text">
          {changer.error}
        </p>
      )}

      {jobs.isPending && (
        <div className="flex flex-col gap-2" aria-busy="true" aria-label="Loading jobs">
          {[0, 1, 2, 3, 4].map((i) => (
            <Skeleton key={i} className="h-14 w-full" />
          ))}
        </div>
      )}
      {jobs.isError && (
        <ErrorState
          title="Could not load jobs"
          description={jobs.error.message}
          onRetry={() => void jobs.refetch()}
        />
      )}
      {jobs.isSuccess && items.length === 0 && (
        <EmptyState
          icon={<Briefcase aria-hidden="true" />}
          title={filtered ? "No jobs match these filters" : "No jobs yet"}
          description={
            filtered
              ? "Try a different search or clear the status filter."
              : "Add your first job, or import your workbook with `careerpilot import-tracker`."
          }
          action={
            filtered ? (
              <Button
                onClick={() => {
                  setSearch("");
                  setStatus("");
                }}
              >
                Clear filters
              </Button>
            ) : (
              <Button variant="primary" onClick={() => setAdding(true)}>
                <Plus aria-hidden="true" /> Add job
              </Button>
            )
          }
        />
      )}

      {items.length > 0 &&
        (view === "table" ? (
          <JobsTable jobs={items} onStatus={changer.request} />
        ) : (
          <JobsBoard jobs={items} onStatus={changer.request} />
        ))}

      {hasMore && view === "table" && (
        <div>
          <Button onClick={() => jobs.fetchNextPage()} loading={jobs.isFetchingNextPage}>
            Load more
          </Button>
        </div>
      )}
      {hasMore && view === "board" && (
        <p className="text-sm text-muted-foreground">
          Showing the 200 most recently active jobs. Use search to narrow down.
        </p>
      )}

      <AddJobDialog open={adding} onClose={() => setAdding(false)} />
      {changer.dialog}
    </div>
  );
}

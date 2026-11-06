"use client";

import Link from "next/link";
import { useState } from "react";

import { muted } from "@/components/ui";
import { cn } from "@/lib/utils";
import type { JobSummary, Status } from "@/lib/api/types";

import { FollowUp } from "./JobsTable";
import { StatusSelect } from "./StatusChanger";
import { STATUSES, statusTone } from "./status";

/**
 * One column per status. Drag a card to another column to change its status. The select on each
 * card does the same without a mouse.
 */
export function JobsBoard({
  jobs,
  onStatus,
}: {
  jobs: JobSummary[];
  onStatus: (job: JobSummary, status: Status) => void;
}) {
  const [over, setOver] = useState<Status | null>(null);

  return (
    <div className="flex gap-3 overflow-x-auto pb-3">
      {STATUSES.map((status) => {
        const column = jobs.filter((job) => job.application.status === status);
        return (
          <section
            key={status}
            aria-label={`${status}, ${column.length} jobs`}
            onDragOver={(event) => {
              event.preventDefault();
              setOver(status);
            }}
            onDragLeave={() => setOver((current) => (current === status ? null : current))}
            onDrop={(event) => {
              event.preventDefault();
              setOver(null);
              const job = jobs.find((j) => j.id === event.dataTransfer.getData("text/plain"));
              if (job && job.application.status !== status) onStatus(job, status);
            }}
            className={cn(
              "w-64 shrink-0 rounded-lg border bg-surface-muted p-2 transition-colors",
              over === status ? "border-primary bg-accent-soft" : "border-border-subtle",
            )}
          >
            <h2 className={cn("mb-2 flex items-center justify-between rounded-md px-2 py-1 text-xs font-semibold", statusTone(status))}>
              {status} <span className="tabular font-normal">{column.length}</span>
            </h2>
            <ul className="space-y-2">
              {column.map((job) => (
                <li
                  key={job.id}
                  draggable
                  onDragStart={(event) => event.dataTransfer.setData("text/plain", job.id)}
                  className="cursor-grab space-y-1.5 rounded-md border border-border-subtle bg-surface p-2.5 text-sm shadow-sm active:cursor-grabbing"
                >
                  <Link href={`/jobs/${job.id}`} className="font-medium hover:underline">
                    {job.company.name}
                  </Link>
                  <div className={muted}>{job.title}</div>
                  {job.est_ctc_lpa ? <div className="text-xs">{job.est_ctc_lpa} LPA</div> : null}
                  <div className="text-xs">
                    <FollowUp job={job} />
                  </div>
                  <StatusSelect
                    job={job}
                    statuses={STATUSES}
                    label={`Move ${job.title} at ${job.company.name}`}
                    onChange={(next) => onStatus(job, next)}
                  />
                </li>
              ))}
            </ul>
          </section>
        );
      })}
    </div>
  );
}

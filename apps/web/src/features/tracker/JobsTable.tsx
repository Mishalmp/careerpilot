"use client";

import Link from "next/link";

import { dateOnly, todayLocal } from "@/lib/dates";
import type { JobSummary, Status } from "@/lib/api/types";
import { cn } from "@/lib/utils";

import { StatusSelect } from "./StatusChanger";
import { STATUSES } from "./status";

export function FollowUp({ job }: { job: JobSummary }) {
  const date = job.application.next_followup_on;
  if (!date) return <span className="text-muted-foreground">-</span>;
  const overdue = date < todayLocal();
  return (
    <span className={cn(overdue && "font-medium text-danger-text")}>
      {date}
      {overdue && " (overdue)"}
    </span>
  );
}

const TH = "px-3 py-2 text-xs font-medium text-muted-foreground";
const TD = "px-3 py-[calc(var(--row-h)/4)] align-middle";

export function JobsTable({
  jobs,
  onStatus,
}: {
  jobs: JobSummary[];
  onStatus: (job: JobSummary, status: Status) => void;
}) {
  return (
    <div className="overflow-x-auto rounded-lg border border-border-subtle bg-surface">
      <table className="w-full text-left md:min-w-[52rem] text-[length:var(--text-base)]">
        <caption className="sr-only">Tracked jobs, newest activity first</caption>
        <thead className="border-b border-border-subtle bg-surface-muted">
          <tr>
            <th scope="col" className={TH}>Company and role</th>
            <th scope="col" className={TH}>Status</th>
            <th scope="col" className={cn(TH, "hidden md:table-cell")}>Where</th>
            <th scope="col" className={cn(TH, "hidden md:table-cell")}>Est. CTC</th>
            <th scope="col" className={cn(TH, "hidden sm:table-cell")}>Follow-up</th>
            <th scope="col" className={cn(TH, "hidden md:table-cell")}>Updated</th>
          </tr>
        </thead>
        <tbody className="divide-y divide-border-subtle">
          {jobs.map((job) => (
            <tr key={job.id} className="transition-colors hover:bg-surface-muted">
              <td className={TD}>
                <Link
                  href={`/jobs/${job.id}`}
                  className="font-medium text-foreground underline-offset-2 hover:text-accent-text hover:underline"
                >
                  {job.company.name}
                </Link>
                <div className="text-muted-foreground">{job.title}</div>
              </td>
              <td className={TD}>
                <StatusSelect
                  job={job}
                  statuses={STATUSES}
                  label={`Change status of ${job.title} at ${job.company.name}`}
                  onChange={(status) => onStatus(job, status)}
                />
              </td>
              <td className={cn(TD, "hidden md:table-cell")}>{[job.location_text, job.work_mode].filter(Boolean).join(" · ") || "-"}</td>
              <td className={cn(TD, "hidden md:table-cell")}>{job.est_ctc_lpa ? `${job.est_ctc_lpa} LPA` : "-"}</td>
              <td className={cn(TD, "hidden sm:table-cell")}>
                <FollowUp job={job} />
              </td>
              <td className={cn(TD, "hidden text-muted-foreground md:table-cell")}>{dateOnly(job.updated_at)}</td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}

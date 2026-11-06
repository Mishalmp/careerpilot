"use client";

import Link from "next/link";

import { muted } from "@/components/ui";
import type { JobSummary, Status } from "@/lib/api/types";

import { StatusSelect } from "./StatusChanger";
import { STATUSES } from "./status";
import { StatusBadge } from "./StatusBadge";
import { todayLocal } from "@/lib/dates";


export function FollowUp({ job }: { job: JobSummary }) {
  const date = job.application.next_followup_on;
  if (!date) return <span className={muted}>-</span>;
  const overdue = date < todayLocal();
  return (
    <span className={overdue ? "font-medium text-danger-text " : ""}>
      {date}
      {overdue && " (overdue)"}
    </span>
  );
}

export function JobsTable({
  jobs,
  onStatus,
}: {
  jobs: JobSummary[];
  onStatus: (job: JobSummary, status: Status) => void;
}) {
  return (
    <div className="overflow-x-auto">
      <table className="w-full min-w-[56rem] text-left text-sm">
        <caption className="sr-only">Tracked jobs, newest activity first</caption>
        <thead className="border-b border-border-subtle text-xs uppercase text-muted-foreground">
          <tr>
            <th scope="col" className="py-2 pr-3">Company and role</th>
            <th scope="col" className="py-2 pr-3">Status</th>
            <th scope="col" className="py-2 pr-3">Where</th>
            <th scope="col" className="py-2 pr-3">Est. CTC</th>
            <th scope="col" className="py-2 pr-3">Follow-up</th>
            <th scope="col" className="py-2">Updated</th>
          </tr>
        </thead>
        <tbody>
          {jobs.map((job) => (
            <tr key={job.id} className="border-b border-border-subtle align-top">
              <td className="py-2 pr-3">
                <Link href={`/jobs/${job.id}`} className="font-medium underline-offset-2 hover:underline">
                  {job.company.name}
                </Link>
                <div className={muted}>{job.title}</div>
              </td>
              <td className="space-y-1 py-2 pr-3">
                <StatusBadge status={job.application.status} />
                <div>
                  <StatusSelect
                    job={job}
                    statuses={STATUSES}
                    label={`Change status of ${job.title} at ${job.company.name}`}
                    onChange={(status) => onStatus(job, status)}
                  />
                </div>
              </td>
              <td className="py-2 pr-3">
                {[job.location_text, job.work_mode].filter(Boolean).join(" · ") || "-"}
              </td>
              <td className="py-2 pr-3">{job.est_ctc_lpa ? `${job.est_ctc_lpa} LPA` : "-"}</td>
              <td className="py-2 pr-3">
                <FollowUp job={job} />
              </td>
              <td className="py-2">{new Date(job.updated_at).toLocaleDateString("en-CA")}</td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}

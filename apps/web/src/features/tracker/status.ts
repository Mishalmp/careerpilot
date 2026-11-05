import type { Status } from "@/lib/api/types";

/** Pipeline order, matching the workbook's Status list. */
export const STATUSES: Status[] = [
  "New",
  "Shortlisted",
  "Applied - Pending",
  "Follow-up Sent",
  "Interview Confirmed",
  "Technical Round",
  "Next Round",
  "HR Round",
  "Manager Round",
  "Offer Received",
  "Offer Accepted",
  "Rejected",
  "No Response",
  "On Hold",
  "Withdrawn",
  "Job Closed",
];

// Colour by meaning, as in the workbook: blue = early, amber = waiting, purple = interviewing,
// green = good outcome, red = bad outcome, grey = parked.
const TONE: Record<Status, string> = {
  New: "bg-sky-100 text-sky-900 dark:bg-sky-900/40 dark:text-sky-200",
  Shortlisted: "bg-sky-200 text-sky-950 dark:bg-sky-800/50 dark:text-sky-100",
  "Applied - Pending": "bg-amber-100 text-amber-900 dark:bg-amber-900/40 dark:text-amber-200",
  "Follow-up Sent": "bg-amber-200 text-amber-950 dark:bg-amber-800/50 dark:text-amber-100",
  "Interview Confirmed": "bg-violet-100 text-violet-900 dark:bg-violet-900/40 dark:text-violet-200",
  "Technical Round": "bg-violet-200 text-violet-950 dark:bg-violet-800/50 dark:text-violet-100",
  "Next Round": "bg-violet-200 text-violet-950 dark:bg-violet-800/50 dark:text-violet-100",
  "HR Round": "bg-violet-200 text-violet-950 dark:bg-violet-800/50 dark:text-violet-100",
  "Manager Round": "bg-violet-300 text-violet-950 dark:bg-violet-700/50 dark:text-violet-100",
  "Offer Received": "bg-emerald-100 text-emerald-900 dark:bg-emerald-900/40 dark:text-emerald-200",
  "Offer Accepted": "bg-emerald-300 text-emerald-950 dark:bg-emerald-700/60 dark:text-emerald-50",
  Rejected: "bg-red-100 text-red-900 dark:bg-red-900/40 dark:text-red-200",
  "No Response": "bg-zinc-200 text-zinc-800 dark:bg-zinc-700/60 dark:text-zinc-200",
  "On Hold": "bg-zinc-200 text-zinc-800 dark:bg-zinc-700/60 dark:text-zinc-200",
  Withdrawn: "bg-zinc-200 text-zinc-800 dark:bg-zinc-700/60 dark:text-zinc-200",
  "Job Closed": "bg-zinc-300 text-zinc-800 dark:bg-zinc-600/60 dark:text-zinc-200",
};

export function statusTone(status: Status): string {
  return TONE[status];
}

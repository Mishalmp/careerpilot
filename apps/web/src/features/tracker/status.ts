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

// Colour by meaning (never colour alone: the label is always shown): blue = early, amber = waiting,
// violet = interviewing, green = good outcome, red = bad outcome, grey = parked.
const EARLY = "bg-accent-soft text-accent-text";
const WAITING = "bg-warning-soft text-warning-text";
const INTERVIEW = "bg-violet-soft text-violet-text";
const GOOD = "bg-success-soft text-success-text";
const BAD = "bg-danger-soft text-danger-text";
const PARKED = "bg-surface-hover text-muted-foreground";

const TONE: Record<Status, string> = {
  New: EARLY,
  Shortlisted: EARLY,
  "Applied - Pending": WAITING,
  "Follow-up Sent": WAITING,
  "Interview Confirmed": INTERVIEW,
  "Technical Round": INTERVIEW,
  "Next Round": INTERVIEW,
  "HR Round": INTERVIEW,
  "Manager Round": INTERVIEW,
  "Offer Received": GOOD,
  "Offer Accepted": GOOD,
  Rejected: BAD,
  "No Response": PARKED,
  "On Hold": PARKED,
  Withdrawn: PARKED,
  "Job Closed": PARKED,
};

export function statusTone(status: Status): string {
  return TONE[status];
}

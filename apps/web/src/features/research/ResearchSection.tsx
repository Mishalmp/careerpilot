"use client";

import type { JobDetail } from "@/lib/api/types";

import { IntelPanel } from "./IntelPanel";
import { OutreachPanel } from "./OutreachPanel";
import { ScorePanel } from "./ScorePanel";
import { VerificationPanel } from "./VerificationPanel";
import { useVerification } from "./hooks";

/** Company checks, fit score, interview intel and outreach drafts for one job. */
export function ResearchSection({ job }: { job: JobDetail }) {
  const verification = useVerification(job.id);
  const aiAvailable = verification.data?.ai_available ?? false;
  return (
    <div className="space-y-6">
      <VerificationPanel jobId={job.id} />
      <ScorePanel jobId={job.id} />
      <IntelPanel jobId={job.id} />
      <OutreachPanel job={job} aiAvailable={aiAvailable} />
    </div>
  );
}

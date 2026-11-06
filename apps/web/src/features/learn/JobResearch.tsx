"use client";

import { Loader2, Search } from "lucide-react";
import Link from "next/link";

import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";

import { type ResearchRun, useResearchRuns, useStartResearch } from "./researchHooks";

const STATUS = {
  queued: { label: "Waiting to start", tone: "neutral" },
  running: { label: "Searching and reading", tone: "accent" },
  succeeded: { label: "Finished", tone: "success" },
  partial: { label: "Finished early", tone: "warning" },
  failed: { label: "Failed", tone: "danger" },
} as const;

/** Start research for a job and follow it. Shown on the job's Research tab. */
export function JobResearch({ jobId }: { jobId: string }) {
  const runs = useResearchRuns(jobId);
  const start = useStartResearch(jobId);
  const active = runs.data?.some((r) => r.status === "queued" || r.status === "running") ?? false;

  return (
    <Card>
      <CardHeader>
        <CardTitle>Interview topics for this job</CardTitle>
        <CardDescription>
          Searches the web for what this role is asked, reads a few pages, and puts topics and questions in your inbox with the
          source and a quote. Nothing is added until you approve it.
        </CardDescription>
      </CardHeader>
      <CardContent className="flex flex-col gap-4">
        <div className="flex flex-wrap items-center gap-3">
          <Button variant="primary" loading={start.isPending} disabled={active} onClick={() => start.mutate()}>
            {active ? <Loader2 className="animate-spin" aria-hidden="true" /> : <Search aria-hidden="true" />}
            {active ? "Research in progress" : "Research interview topics"}
          </Button>
          <Link href="/learn#inbox" className="text-sm text-accent-text underline underline-offset-2">
            Open your inbox
          </Link>
        </div>
        {start.error && (
          <p role="alert" className="text-sm text-danger-text">
            {start.error.message}
          </p>
        )}
        {runs.data && runs.data.length > 0 && (
          <ul className="flex flex-col gap-2" aria-label="Research runs">
            {runs.data.slice(0, 5).map((run) => (
              <RunRow key={run.id} run={run} />
            ))}
          </ul>
        )}
      </CardContent>
    </Card>
  );
}

function RunRow({ run }: { run: ResearchRun }) {
  const status = STATUS[run.status];
  const usage = run.usage as Record<string, number | undefined>;
  return (
    <li className="rounded-md border border-border-subtle p-3 text-sm">
      <div className="flex flex-wrap items-center gap-2">
        <Badge tone={status.tone}>{status.label}</Badge>
        <span className="text-muted-foreground">{new Date(run.created_at).toLocaleString()}</span>
        {run.pending_findings > 0 && <Badge tone="accent">{run.pending_findings} waiting in your inbox</Badge>}
      </div>
      {(run.status === "succeeded" || run.status === "partial") && (
        <p className="mt-1 text-muted-foreground">
          Read {usage.pages_read ?? 0} pages, found {usage.items_found ?? 0} items
          {usage.items_dropped ? `, discarded ${usage.items_dropped} whose quote was not on the page` : ""}.
        </p>
      )}
      {run.message && <p className="mt-1 text-muted-foreground">{run.message}</p>}
    </li>
  );
}

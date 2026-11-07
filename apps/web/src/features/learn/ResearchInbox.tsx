"use client";

import { Check, ExternalLink, Inbox, X } from "lucide-react";

import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Skeleton } from "@/components/ui/skeleton";
import { EmptyState, ErrorState } from "@/components/ui/states";

import { type ResearchFinding, useDecide, useFindings } from "./researchHooks";

/** Things the research found, waiting for you. Nothing enters Learn until you approve it. */
export function ResearchInbox() {
  const findings = useFindings(50);
  const decide = useDecide();

  if (findings.isPending) return <Skeleton className="h-24" aria-busy="true" aria-label="Loading inbox" />;
  if (findings.isError) {
    return <ErrorState title="Could not load the inbox" description={findings.error.message} onRetry={() => void findings.refetch()} />;
  }
  const items = findings.data.items;
  if (items.length === 0) {
    return (
      <EmptyState
        icon={<Inbox aria-hidden="true" />}
        title="Your research inbox is empty"
        description="Open a job and choose “Research interview topics”. What it finds waits here for your approval."
      />
    );
  }

  const error = decide.approve.error ?? decide.reject.error;
  return (
    <div className="flex flex-col gap-3">
      {error && (
        <p role="alert" className="text-sm text-danger-text">
          {error.message}
        </p>
      )}
      <ul className="flex flex-col gap-3">
        {items.map((f) => (
          <FindingCard
            key={f.id}
            finding={f}
            busy={decide.approve.isPending || decide.reject.isPending}
            onApprove={() => decide.approve.mutate(f.id)}
            onReject={() => decide.reject.mutate(f.id)}
          />
        ))}
      </ul>
      {findings.data.total > items.length && (
        <p className="text-sm text-muted-foreground">
          Showing the {items.length} most relevant of {findings.data.total}. Decide these to see more.
        </p>
      )}
    </div>
  );
}

function FindingCard({
  finding,
  busy,
  onApprove,
  onReject,
}: {
  finding: ResearchFinding;
  busy: boolean;
  onApprove: () => void;
  onReject: () => void;
}) {
  return (
    <li className="rounded-lg border border-border-subtle bg-surface p-4">
      <div className="flex flex-wrap items-center gap-1.5">
        <Badge tone="accent">{finding.topic}</Badge>
        <Badge tone="outline">{finding.kind === "question" ? "Question" : "Topic"}</Badge>
        <Badge tone="neutral">Relevance {finding.relevance}</Badge>
        {finding.mentions > 1 && <Badge tone="success">Asked on {finding.mentions} pages</Badge>}
      </div>
      <p className="mt-2 font-medium">{finding.text}</p>
      <blockquote className="mt-2 border-l-2 border-border-strong pl-3 text-sm text-muted-foreground">
        “{finding.quote}”
      </blockquote>
      <a
        href={finding.source_url}
        target="_blank"
        rel="noopener noreferrer"
        className="mt-1 inline-flex items-center gap-1 text-sm text-accent-text underline underline-offset-2"
      >
        {finding.source_title ?? finding.source_url} <ExternalLink className="size-3" aria-hidden="true" />
      </a>
      {finding.more_sources.length > 0 && (
        <p className="mt-1 text-sm text-muted-foreground">
          Also on:{" "}
          {finding.more_sources.map((s, i) => (
            <span key={s.url}>
              {i > 0 && ", "}
              <a href={s.url} target="_blank" rel="noopener noreferrer" className="text-accent-text underline underline-offset-2">
                {s.title ?? s.url}
              </a>
            </span>
          ))}
        </p>
      )}
      <div className="mt-3 flex gap-2">
        <Button size="sm" variant="primary" disabled={busy} onClick={onApprove} aria-label={`Approve: ${finding.text}`}>
          <Check aria-hidden="true" /> Approve
        </Button>
        <Button size="sm" disabled={busy} onClick={onReject} aria-label={`Reject: ${finding.text}`}>
          <X aria-hidden="true" /> Reject
        </Button>
      </div>
    </li>
  );
}

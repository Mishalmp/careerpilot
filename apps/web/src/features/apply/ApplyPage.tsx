"use client";

import {
  Check,
  CircleCheck,
  ClipboardCheck,
  ExternalLink,
  RefreshCw,
  SkipForward,
  TriangleAlert,
} from "lucide-react";
import Link from "next/link";
import { useState } from "react";

import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { PageHeader } from "@/components/ui/page-header";
import { Skeleton } from "@/components/ui/skeleton";
import { EmptyState, ErrorState } from "@/components/ui/states";

import {
  type ApplyItem,
  useApplyQueue,
  useBuildQueue,
  useDecideItem,
  useResearchItem,
} from "./hooks";

type Pay = NonNullable<ApplyItem["pay"]>;
type Interview = NonNullable<ApplyItem["interview"]>;
type Steps = Pay["tried"];

/** Amounts per year in the currency they were found in. Rupee figures are shown in lakhs. */
function formatMoney(value: number, currency: string | null): string {
  if (currency === "INR") return `${+(value / 100_000).toFixed(1)} LPA`;
  return `${currency ?? ""} ${Math.round(value).toLocaleString("en-US")}`.trim();
}

function range(pay: Pay): string {
  if (pay.low === null || pay.high === null) return "";
  const a = formatMoney(pay.low, pay.currency);
  return pay.low === pay.high
    ? a
    : `${a} to ${formatMoney(pay.high, pay.currency)}`;
}

const VERDICT_TONE = {
  verified: "success",
  likely_genuine: "success",
  needs_check: "warning",
  suspicious: "danger",
  unverified: "neutral",
  not_checked: "neutral",
} as const;
const STATUS_TEXT: Record<ApplyItem["status"], string> = {
  ready: "Ready to review",
  approved: "Approved: apply, then say you did",
  applied: "Applied",
  skipped: "Skipped",
  blocked: "Held back",
};

/**
 * The daily apply list. Every piece of information says where it came from, so you can check it
 * before you apply. Nothing here applies for you: Approve shortlists the job, you open the apply
 * page yourself, and "I applied" records it afterwards.
 */
export function ApplyPage() {
  const build = useBuildQueue();
  const [asked, setAsked] = useState(false);
  const queue = useApplyQueue(asked);
  const decide = useDecideItem();

  if (queue.isPending)
    return (
      <Skeleton
        className="h-48"
        aria-busy="true"
        aria-label="Loading the list"
      />
    );
  if (queue.isError) {
    return (
      <ErrorState
        title="Could not load the list"
        description={queue.error.message}
        onRetry={() => void queue.refetch()}
      />
    );
  }
  const data = queue.data;
  const open = data.items.filter((i) =>
    ["ready", "approved"].includes(i.status),
  );
  const held = data.items.filter((i) => i.status === "blocked");
  const done = data.items.filter((i) =>
    ["applied", "skipped"].includes(i.status),
  );
  const error = decide.error ?? build.error;

  return (
    <div className="flex flex-col gap-6">
      <PageHeader
        title="Apply list"
        description="A few jobs a day, researched for you. Read each one, check the sources, then decide. Nothing is applied for you."
        actions={
          <Button
            variant="primary"
            loading={build.isPending}
            onClick={() => {
              setAsked(true);
              build.mutate();
            }}
          >
            <RefreshCw aria-hidden="true" /> Build today’s list
          </Button>
        }
      />

      <p className="rounded-lg border border-border-subtle bg-surface-hover px-4 py-3 text-sm text-muted-foreground">
        {data.notice} Chosen by <code>{data.policy_source}</code>: up to{" "}
        {data.policy.daily_limit} a day, match of at least{" "}
        {data.policy.min_match_score}.
      </p>

      {data.policy_problems.length > 0 && (
        <div
          role="alert"
          className="rounded-lg border border-danger-solid px-4 py-3 text-sm text-danger-text"
        >
          <p className="font-medium">
            Your apply policy file has a problem, so nothing can be built:
          </p>
          <ul className="mt-1 list-disc pl-5">
            {data.policy_problems.map((p) => (
              <li key={p}>{p}</li>
            ))}
          </ul>
        </div>
      )}
      {build.isSuccess && (
        <p role="status" className="text-sm text-muted-foreground">
          {build.data.queued
            ? "Building. This page refreshes while it works."
            : "A build for this minute is already queued."}
        </p>
      )}
      {error && (
        <p role="alert" className="text-sm text-danger-text">
          {error.message}
        </p>
      )}

      {open.length === 0 && held.length === 0 && done.length === 0 ? (
        <div className="flex flex-col gap-4">
          <EmptyState
            icon={<ClipboardCheck aria-hidden="true" />}
            title="Nothing on the list yet"
            description="The list is built each morning from jobs in your tracker that are still New or Shortlisted. Add jobs, make sure your CV profile is filled in, then build it."
            action={
              <Button asChild>
                <Link href="/profile">Check your profile</Link>
              </Button>
            }
          />
          {data && data.last_build.length > 0 && (
            <div
              className="rounded-lg border border-border-subtle bg-surface-muted p-4 text-sm"
              aria-label="What the last build found"
            >
              <p className="font-medium">What the last build found</p>
              <ul className="mt-1.5 list-disc pl-5 text-muted-foreground">
                {data.last_build.map((line) => (
                  <li key={line}>{line}</li>
                ))}
              </ul>
            </div>
          )}
        </div>
      ) : (
        <>
          <Section
            title="To review"
            empty="Everything on the list has been decided."
          >
            {open.map((item) => (
              <ItemCard
                key={item.id}
                item={item}
                busy={decide.isPending}
                onAct={(action) => decide.mutate({ id: item.id, action })}
              />
            ))}
          </Section>
          {held.length > 0 && (
            <Section title="Held back by the company check">
              {held.map((item) => (
                <ItemCard
                  key={item.id}
                  item={item}
                  busy={decide.isPending}
                  onAct={(action) => decide.mutate({ id: item.id, action })}
                />
              ))}
            </Section>
          )}
          {done.length > 0 && (
            <Section title="Decided this week">
              {done.map((item) => (
                <ItemCard
                  key={item.id}
                  item={item}
                  busy={decide.isPending}
                  onAct={(action) => decide.mutate({ id: item.id, action })}
                />
              ))}
            </Section>
          )}
        </>
      )}
    </div>
  );
}

function Section({
  title,
  empty,
  children,
}: {
  title: string;
  empty?: string;
  children: React.ReactNode[];
}) {
  return (
    <section className="flex flex-col gap-3" aria-label={title}>
      <h2 className="text-lg font-semibold">{title}</h2>
      {children.length === 0 && empty ? (
        <p className="text-sm text-muted-foreground">{empty}</p>
      ) : (
        <ul className="flex flex-col gap-4">{children}</ul>
      )}
    </section>
  );
}

function TriedList({ steps }: { steps: Steps }) {
  return (
    <details className="mt-2 text-sm text-muted-foreground">
      <summary className="cursor-pointer">
        Where I looked ({steps.length})
      </summary>
      <ul className="mt-1 flex flex-col gap-1 pl-4">
        {steps.map((s) => (
          <li key={s.label}>
            {s.found ? "Found" : "Nothing"} · {s.label}: {s.note}
          </li>
        ))}
      </ul>
    </details>
  );
}

function Source({
  url,
  title,
  quote,
}: {
  url: string | null;
  title: string;
  quote: string;
}) {
  return (
    <li className="text-sm">
      <blockquote className="border-l-2 border-border-strong pl-3 text-muted-foreground">
        “{quote}”
      </blockquote>
      {url ? (
        <a
          href={url}
          target="_blank"
          rel="noopener noreferrer"
          className="inline-flex items-center gap-1 text-accent-text underline underline-offset-2"
        >
          {title} <ExternalLink className="size-3" aria-hidden="true" />
        </a>
      ) : (
        <span className="text-muted-foreground">{title}</span>
      )}
    </li>
  );
}

function PayBlock({ pay }: { pay: Pay }) {
  return (
    <div>
      <h3 className="text-sm font-semibold">Pay</h3>
      {pay.level === null ? (
        <p className="text-sm text-muted-foreground">
          No pay information found anywhere I looked.
        </p>
      ) : (
        <>
          <p className="text-base font-medium">
            {range(pay)}
            {pay.n > 1 && pay.mid !== null ? (
              <span className="text-sm font-normal text-muted-foreground">
                {" "}
                · middle {formatMoney(pay.mid, pay.currency)} from {pay.n}{" "}
                figures
              </span>
            ) : null}
          </p>
          <Badge
            tone={
              pay.level === "posted"
                ? "success"
                : pay.level === "similar_roles"
                  ? "warning"
                  : "accent"
            }
          >
            {pay.label}
          </Badge>
          <ul className="mt-2 flex flex-col gap-2">
            {pay.evidence.map((e) => (
              <Source key={`${e.url ?? "tracker"}-${e.quote}`} {...e} />
            ))}
          </ul>
        </>
      )}
      <TriedList steps={pay.tried} />
    </div>
  );
}

function InterviewBlock({ interview }: { interview: Interview }) {
  return (
    <div>
      <h3 className="text-sm font-semibold">Interview</h3>
      {interview.level === null ? (
        <p className="text-sm text-muted-foreground">
          No interview information found anywhere I looked.
        </p>
      ) : (
        <>
          <Badge
            tone={interview.level === "similar_roles" ? "warning" : "accent"}
          >
            {interview.label}
          </Badge>
          <ul className="mt-2 flex flex-col gap-2">
            {interview.points.map((p) => (
              <Source key={`${p.url ?? "post"}-${p.quote}`} {...p} />
            ))}
          </ul>
        </>
      )}
      <TriedList steps={interview.tried} />
    </div>
  );
}

function ItemCard({
  item,
  busy,
  onAct,
}: {
  item: ApplyItem;
  busy: boolean;
  onAct: (a: "approve" | "applied" | "skip") => void;
}) {
  const research = useResearchItem();
  const link = item.apply_url ?? item.jd_url;
  const check = item.company_check;
  const decided = item.status === "applied" || item.status === "skipped";
  return (
    <li
      className="rounded-lg border border-border-subtle bg-surface p-4"
      aria-label={`${item.title} at ${item.company}`}
    >
      <div className="flex flex-wrap items-start justify-between gap-3">
        <div className="min-w-0">
          <h3 className="text-lg font-semibold">
            <Link href={`/jobs/${item.job_id}`} className="hover:underline">
              {item.title}
            </Link>
          </h3>
          <p className="text-sm text-muted-foreground">
            {item.company}
            {item.location ? ` · ${item.location}` : ""}
            {item.work_mode ? ` · ${item.work_mode}` : ""}
          </p>
        </div>
        <div className="flex flex-wrap items-center gap-1.5">
          <Badge
            tone={
              item.status === "blocked"
                ? "danger"
                : item.status === "applied"
                  ? "success"
                  : "neutral"
            }
          >
            {STATUS_TEXT[item.status]}
          </Badge>
          <Badge tone="accent">Match {item.match_score}</Badge>
        </div>
      </div>

      {item.status === "blocked" && item.decision_note && (
        <p className="mt-3 flex items-start gap-2 text-sm text-danger-text">
          <TriangleAlert
            className="mt-0.5 size-4 shrink-0"
            aria-hidden="true"
          />{" "}
          {item.decision_note}
        </p>
      )}

      <div className="mt-4 grid gap-5 lg:grid-cols-2">
        {item.pay ? (
          <PayBlock pay={item.pay} />
        ) : (
          <p className="text-sm text-muted-foreground">
            Pay was not looked up.
          </p>
        )}
        {item.interview ? (
          <InterviewBlock interview={item.interview} />
        ) : (
          <p className="text-sm text-muted-foreground">
            Interview information was not looked up.
          </p>
        )}
      </div>

      <div className="mt-4 grid gap-5 lg:grid-cols-2">
        <div>
          <h3 className="text-sm font-semibold">Why it matches</h3>
          <ul className="list-disc pl-5 text-sm text-muted-foreground">
            {item.reasons.map((r) => (
              <li key={r}>{r}</li>
            ))}
          </ul>
        </div>
        <div>
          <h3 className="text-sm font-semibold">Company check</h3>
          {check ? (
            <p className="text-sm">
              <Badge
                tone={
                  VERDICT_TONE[check.verdict as keyof typeof VERDICT_TONE] ??
                  "neutral"
                }
              >
                {check.verdict.replace("_", " ")}
              </Badge>{" "}
              <span className="text-muted-foreground">{check.note}</span>
            </p>
          ) : (
            <p className="text-sm text-muted-foreground">Not checked.</p>
          )}
          <h3 className="mt-3 text-sm font-semibold">Also listed on</h3>
          {item.also_listed.length === 0 ? (
            <p className="text-sm text-muted-foreground">
              No other listing found.
            </p>
          ) : (
            <ul className="text-sm">
              {item.also_listed.map((l) => (
                <li key={l.url}>
                  <a
                    href={l.url}
                    target="_blank"
                    rel="noopener noreferrer"
                    className="text-accent-text underline underline-offset-2"
                  >
                    {l.host}
                  </a>{" "}
                  <span className="text-muted-foreground">
                    {l.kind === "same_job" ? "same job" : "similar role"}
                    {l.overlap !== null
                      ? ` · ${Math.round(l.overlap * 100)}% of skills in common`
                      : ""}
                    {l.opened ? "" : " · page not opened"}
                  </span>
                </li>
              ))}
            </ul>
          )}
        </div>
      </div>

      {research.error && (
        <p role="alert" className="mt-2 text-sm text-danger-text">
          {research.error.message}
        </p>
      )}
      {item.notes.length > 0 && (
        <ul className="mt-3 list-disc pl-5 text-sm text-muted-foreground">
          {item.notes.map((n) => (
            <li key={n}>{n}</li>
          ))}
        </ul>
      )}

      {!decided && (
        <div className="mt-4 flex flex-wrap items-center gap-2 border-t border-border-subtle pt-4">
          {item.status !== "approved" ? (
            <Button
              variant="primary"
              size="sm"
              disabled={busy}
              onClick={() => onAct("approve")}
              aria-label={`Approve ${item.title} at ${item.company}`}
            >
              <Check aria-hidden="true" /> Approve
            </Button>
          ) : (
            <Button
              variant="primary"
              size="sm"
              disabled={busy}
              onClick={() => onAct("applied")}
              aria-label={`I applied to ${item.title} at ${item.company}`}
            >
              <CircleCheck aria-hidden="true" /> I applied
            </Button>
          )}
          {link && (
            <Button asChild size="sm" variant="secondary">
              <a
                href={link}
                target="_blank"
                rel="noopener noreferrer"
                aria-label={`Open the apply page for ${item.title} at ${item.company}`}
              >
                Open the apply page <ExternalLink aria-hidden="true" />
              </a>
            </Button>
          )}
          {!item.deep && (
            <Button
              size="sm"
              variant="soft"
              loading={research.isPending}
              onClick={() => research.mutate(item.id)}
              aria-label={`Research ${item.title} at ${item.company}`}
            >
              Research this job
            </Button>
          )}
          {!link && (
            <span className="text-sm text-muted-foreground">
              No apply link on file. Add one on the job page.
            </span>
          )}
          <Button
            size="sm"
            variant="ghost"
            disabled={busy}
            onClick={() => onAct("skip")}
            aria-label={`Skip ${item.title} at ${item.company}`}
          >
            <SkipForward aria-hidden="true" /> Skip
          </Button>
          <span className="text-xs text-muted-foreground">
            Tracker: {item.tracker_status}
          </span>
        </div>
      )}
    </li>
  );
}

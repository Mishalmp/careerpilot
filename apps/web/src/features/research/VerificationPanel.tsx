"use client";

import { useState } from "react";

import { button, card, input, muted, primaryButton } from "@/components/ui";

import {
  type CheckOut,
  useRunVerification,
  useSetCheck,
  useSetWebsite,
  useVerification,
} from "./hooks";

function WebsiteField({
  jobId,
  website,
}: {
  jobId: string;
  website: string | null;
}) {
  const save = useSetWebsite(jobId);
  const [value, setValue] = useState(website ?? "");
  return (
    <form
      className="flex flex-wrap items-center gap-2"
      onSubmit={(e) => {
        e.preventDefault();
        save.mutate(value.trim() || null);
      }}
    >
      <label className="flex flex-1 items-center gap-2 text-sm">
        <span>Company website</span>
        <input
          className={input}
          placeholder="https://example.com"
          value={value}
          onChange={(e) => setValue(e.target.value)}
        />
      </label>
      <button type="submit" className={button} disabled={save.isPending}>
        Save
      </button>
      {save.error && (
        <p
          role="alert"
          className="w-full text-sm text-danger-text"
        >
          {save.error.message}
        </p>
      )}
    </form>
  );
}

const LABELS: Record<CheckOut["key"], string> = {
  website: "Website loads with a valid certificate",
  domain_age: "Domain is at least a year old",
  mail_domain: "Domain accepts email",
  careers_page: "Careers page exists",
  registration: "Registered company details published",
  contact_details: "Address and a way to reach them published",
  people: "Named leadership or team",
  independent_mentions: "Independent sources mention it",
  asks_for_money: "Asks candidates for money",
  chat_only_hiring: "Hiring only over WhatsApp or Telegram",
  no_interview: "Promises a job without an interview",
  free_mail_recruiter: "Recruiter uses a free email address",
};

const VERDICTS = {
  verified: ["Verified", "text-success-text "],
  likely_genuine: ["Likely genuine", "text-success-text "],
  needs_check: ["Needs your check", "text-warning-text "],
  suspicious: ["Suspicious", "text-danger-text "],
} as const;

function Symbol({ check }: { check: CheckOut }) {
  if (check.status === "unknown")
    return <span aria-label="not checked">?</span>;
  const good = check.status === "pass"; // for a red flag, "pass" means it was cleared
  return (
    <span
      aria-label={check.status}
      className={good ? "text-success-text" : "text-danger-text"}
    >
      {good ? "✓" : "✗"}
    </span>
  );
}

function CheckRow({ jobId, check }: { jobId: string; check: CheckOut }) {
  const set = useSetCheck(jobId);
  const [open, setOpen] = useState(false);
  const [note, setNote] = useState("");
  const flag = check.kind === "flag";

  const save = (status: "pass" | "fail") =>
    set.mutate(
      { key: check.key, body: { status, note: note.trim() || null } },
      { onSuccess: () => setOpen(false) },
    );

  return (
    <li className="space-y-1 border-b border-border-subtle py-2 last:border-0">
      <div className="flex items-start gap-2 text-sm">
        <Symbol check={check} />
        <div className="flex-1">
          <p>{LABELS[check.key]}</p>
          {check.note && <p className={muted}>{check.note}</p>}
          {check.evidence_quote && (
            <blockquote className="mt-1 border-l-2 border-input pl-2 text-xs">
              “{check.evidence_quote}”
            </blockquote>
          )}
          {check.evidence_url && (
            <a
              href={check.evidence_url}
              target="_blank"
              rel="noopener noreferrer"
              className="text-xs underline"
            >
              Evidence
            </a>
          )}
        </div>
        <span className={`${muted} text-xs`}>
          {check.source ?? "not checked"}
        </span>
        <button
          type="button"
          className="text-xs underline"
          onClick={() => setOpen(!open)}
        >
          {open ? "Close" : "Set myself"}
        </button>
      </div>
      {open && (
        <div className="ml-6 space-y-2">
          <input
            className={input}
            placeholder="What you found (optional)"
            aria-label={`Note for ${LABELS[check.key]}`}
            value={note}
            onChange={(e) => setNote(e.target.value)}
          />
          <div className="flex flex-wrap gap-2">
            <button
              type="button"
              className={button}
              onClick={() => save("pass")}
              disabled={set.isPending}
            >
              {flag ? "Not a problem" : "Mark as passed"}
            </button>
            <button
              type="button"
              className={button}
              onClick={() => save("fail")}
              disabled={set.isPending}
            >
              {flag ? "Raise the flag" : "Mark as failed"}
            </button>
            {check.source && (
              <button
                type="button"
                className={button}
                onClick={() => set.mutate({ key: check.key, clear: true })}
                disabled={set.isPending}
              >
                Forget result
              </button>
            )}
          </div>
          {set.error && (
            <p role="alert" className="text-sm text-danger-text">
              {set.error.message}
            </p>
          )}
        </div>
      )}
    </li>
  );
}

export function VerificationPanel({ jobId }: { jobId: string }) {
  const query = useVerification(jobId);
  const run = useRunVerification(jobId);

  if (query.isPending)
    return <p className={muted}>Loading company checks...</p>;
  if (query.isError)
    return (
      <p role="alert">Could not load company checks: {query.error.message}</p>
    );
  const data = query.data;
  const [label, colour] = VERDICTS[data.verdict];

  return (
    <section
      className={`${card} space-y-3`}
      aria-labelledby="verification-heading"
    >
      <div className="flex flex-wrap items-center justify-between gap-2">
        <h2 id="verification-heading" className="font-semibold">
          Is {data.company_name} genuine?
        </h2>
        <p className={`font-medium ${colour}`}>
          {label} · {data.passed}/{data.total} checks
        </p>
      </div>
      <p className={muted}>{data.notice}</p>
      {data.raised_flags.length > 0 && (
        <p
          role="alert"
          className="text-sm font-medium text-danger-text"
        >
          Red flag raised. Do not share documents or pay anything until you have
          checked it.
        </p>
      )}
      <div className="flex flex-wrap gap-2">
        <button
          type="button"
          className={primaryButton}
          disabled={run.isPending}
          onClick={() => run.mutate(false)}
        >
          {run.isPending ? "Checking..." : "Run lookups"}
        </button>
        {data.ai_available && (
          <button
            type="button"
            className={button}
            disabled={run.isPending}
            onClick={() => run.mutate(true)}
          >
            Lookups + read their pages
          </button>
        )}
      </div>
      <WebsiteField
        key={data.website ?? "none"}
        jobId={jobId}
        website={data.website}
      />
      {run.error && (
        <p role="alert" className="text-sm text-danger-text">
          {run.error.message}
        </p>
      )}
      <ul>
        {data.checks.map((check) => (
          <CheckRow key={check.key} jobId={jobId} check={check} />
        ))}
      </ul>
    </section>
  );
}

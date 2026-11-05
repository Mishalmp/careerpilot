"use client";

import { useState } from "react";

import { button, card, input, muted, primaryButton } from "@/components/ui";
import type { JobDetail } from "@/lib/api/types";

import {
  type OutreachDraft,
  useCreateOutreach,
  useDeleteOutreach,
  useEditOutreach,
  useGenerateOutreach,
  useMoveOutreach,
  useOutreach,
} from "./hooks";

type Contact = JobDetail["contacts"][number];

function DraftCard({ jobId, draft }: { jobId: string; draft: OutreachDraft }) {
  const move = useMoveOutreach(jobId);
  const edit = useEditOutreach(jobId);
  const remove = useDeleteOutreach(jobId);
  const [editing, setEditing] = useState(false);
  const [subject, setSubject] = useState(draft.subject);
  const [body, setBody] = useState(draft.body);
  const [acknowledge, setAcknowledge] = useState(false);
  const [copied, setCopied] = useState(false);
  const flags = draft.lint.flags;
  const error = move.error ?? edit.error ?? remove.error;

  return (
    <li className="space-y-2 rounded border border-black/10 p-3 dark:border-white/15">
      <div className="flex flex-wrap items-center justify-between gap-2 text-sm">
        <span className="font-medium">
          Variant {draft.variant} · {draft.channel.replace("_", " ")}
        </span>
        <span className={muted}>
          {draft.status} · {draft.lint.words} words
        </span>
      </div>
      {editing ? (
        <div className="space-y-2">
          <input
            className={input}
            aria-label="Subject"
            value={subject}
            onChange={(e) => setSubject(e.target.value)}
          />
          <textarea
            className={`${input} min-h-40`}
            aria-label="Message"
            value={body}
            onChange={(e) => setBody(e.target.value)}
          />
          <div className="flex gap-2">
            <button
              type="button"
              className={primaryButton}
              disabled={edit.isPending}
              onClick={() =>
                edit.mutate(
                  { id: draft.id, body: { subject, body } },
                  { onSuccess: () => setEditing(false) },
                )
              }
            >
              Save
            </button>
            <button
              type="button"
              className={button}
              onClick={() => setEditing(false)}
            >
              Cancel
            </button>
          </div>
        </div>
      ) : (
        <>
          <p className="text-sm font-medium">{draft.subject}</p>
          <pre className="whitespace-pre-wrap font-sans text-sm">
            {draft.body}
          </pre>
        </>
      )}
      {draft.recipient_email && (
        <p className={muted}>
          To {draft.recipient_email}
          {draft.recipient_source_url && (
            <>
              {" "}
              (published at{" "}
              <a
                href={draft.recipient_source_url}
                target="_blank"
                rel="noopener noreferrer"
                className="underline"
              >
                this page
              </a>
              )
            </>
          )}
        </p>
      )}
      {flags.length > 0 ? (
        <details>
          <summary className="cursor-pointer text-sm text-amber-700 dark:text-amber-400">
            {flags.length} thing(s) to fix before you send
          </summary>
          <ul className="list-disc pl-5 text-sm">
            {flags.map((f) => (
              <li key={f}>{f}</li>
            ))}
          </ul>
        </details>
      ) : (
        <p className="text-sm text-green-700 dark:text-green-400">
          No lint flags. Read it aloud before sending.
        </p>
      )}
      {error && (
        <p role="alert" className="text-sm text-red-600 dark:text-red-400">
          {error.message}
        </p>
      )}
      <div className="flex flex-wrap items-center gap-2">
        {draft.status === "draft" && (
          <>
            <button
              type="button"
              className={button}
              onClick={() => setEditing(true)}
            >
              Edit
            </button>
            {flags.length > 0 && (
              <label className="flex items-center gap-1 text-sm">
                <input
                  type="checkbox"
                  checked={acknowledge}
                  onChange={(e) => setAcknowledge(e.target.checked)}
                />
                I have read the flags
              </label>
            )}
            <button
              type="button"
              className={primaryButton}
              disabled={move.isPending || (flags.length > 0 && !acknowledge)}
              onClick={() =>
                move.mutate({ id: draft.id, status: "approved", acknowledge })
              }
            >
              Approve
            </button>
          </>
        )}
        {draft.status === "approved" && (
          <>
            <button
              type="button"
              className={button}
              onClick={() => {
                void navigator.clipboard
                  .writeText(`${draft.subject}\n\n${draft.body}`)
                  .then(() => setCopied(true));
              }}
            >
              {copied ? "Copied" : "Copy to send myself"}
            </button>
            <button
              type="button"
              className={primaryButton}
              disabled={move.isPending}
              onClick={() => move.mutate({ id: draft.id, status: "sent" })}
            >
              I sent it
            </button>
            <button
              type="button"
              className={button}
              onClick={() => move.mutate({ id: draft.id, status: "draft" })}
            >
              Withdraw approval
            </button>
          </>
        )}
        {draft.status === "rejected" && (
          <button
            type="button"
            className={button}
            onClick={() => move.mutate({ id: draft.id, status: "draft" })}
          >
            Reopen
          </button>
        )}
        {(draft.status === "draft" || draft.status === "approved") && (
          <button
            type="button"
            className={button}
            onClick={() => move.mutate({ id: draft.id, status: "rejected" })}
          >
            Reject
          </button>
        )}
        {(draft.status === "draft" || draft.status === "rejected") && (
          <button
            type="button"
            className={button}
            disabled={remove.isPending}
            onClick={() => remove.mutate(draft.id)}
          >
            Delete
          </button>
        )}
      </div>
    </li>
  );
}

function NewDraft({
  jobId,
  contacts,
  aiAvailable,
}: {
  jobId: string;
  contacts: Contact[];
  aiAvailable: boolean;
}) {
  const generate = useGenerateOutreach(jobId);
  const create = useCreateOutreach(jobId);
  const [contactId, setContactId] = useState("");
  const [sender, setSender] = useState("");
  const [fact, setFact] = useState("");
  const [source, setSource] = useState("");
  const [constraint, setConstraint] = useState("");
  const [subject, setSubject] = useState("");
  const [body, setBody] = useState("");
  const error = generate.error ?? create.error;

  return (
    <details className="space-y-3">
      <summary className="cursor-pointer text-sm font-medium">
        New draft
      </summary>
      <label className="block space-y-1 text-sm">
        <span>Send to (an address with a published source, or a referral)</span>
        <select
          className={input}
          value={contactId}
          onChange={(e) => setContactId(e.target.value)}
        >
          <option value="">Choose a contact</option>
          {contacts
            .filter((c) => c.email)
            .map((c) => (
              <option key={c.id} value={c.id}>
                {c.name} ({c.email})
              </option>
            ))}
        </select>
      </label>
      {aiAvailable && (
        <form
          className="space-y-2 rounded border border-black/10 p-3 dark:border-white/15"
          onSubmit={(e) => {
            e.preventDefault();
            generate.mutate({
              channel: "email",
              contact_id: contactId || null,
              sender_name: sender,
              facts: [{ text: fact, source_url: source || null }],
              constraint: constraint || null,
            });
          }}
        >
          <p className="text-sm font-medium">
            Let the model draft two variants
          </p>
          <input
            className={input}
            required
            placeholder="Your first name"
            aria-label="Your first name"
            value={sender}
            onChange={(e) => setSender(e.target.value)}
          />
          <input
            className={input}
            required
            placeholder="A specific fact to mention, in the page's own words"
            aria-label="Fact to mention"
            value={fact}
            onChange={(e) => setFact(e.target.value)}
          />
          <input
            className={input}
            placeholder="Page the fact is from (not needed if it is in the job description)"
            aria-label="Fact source URL"
            value={source}
            onChange={(e) => setSource(e.target.value)}
          />
          <input
            className={input}
            placeholder="Constraint, e.g. my notice period ends on 31 December"
            aria-label="Constraint"
            value={constraint}
            onChange={(e) => setConstraint(e.target.value)}
          />
          <button
            type="submit"
            className={primaryButton}
            disabled={generate.isPending}
          >
            {generate.isPending ? "Drafting..." : "Draft"}
          </button>
        </form>
      )}
      <form
        className="space-y-2 rounded border border-black/10 p-3 dark:border-white/15"
        onSubmit={(e) => {
          e.preventDefault();
          create.mutate(
            {
              channel: "email",
              contact_id: contactId || null,
              subject,
              body,
              facts: fact ? [fact] : [],
            },
            {
              onSuccess: () => {
                setSubject("");
                setBody("");
              },
            },
          );
        }}
      >
        <p className="text-sm font-medium">Or write your own</p>
        <input
          className={input}
          required
          placeholder="Subject"
          aria-label="Subject"
          value={subject}
          onChange={(e) => setSubject(e.target.value)}
        />
        <textarea
          className={`${input} min-h-32`}
          required
          placeholder="Message"
          aria-label="Message body"
          value={body}
          onChange={(e) => setBody(e.target.value)}
        />
        <button type="submit" className={button} disabled={create.isPending}>
          Save draft
        </button>
      </form>
      {error && (
        <p role="alert" className="text-sm text-red-600 dark:text-red-400">
          {error.message}
        </p>
      )}
    </details>
  );
}

export function OutreachPanel({
  job,
  aiAvailable,
}: {
  job: JobDetail;
  aiAvailable: boolean;
}) {
  const query = useOutreach(job.id);
  if (query.isPending) return <p className={muted}>Loading outreach...</p>;
  if (query.isError)
    return <p role="alert">Could not load outreach: {query.error.message}</p>;
  const { items, approved_today, daily_cap, note } = query.data;

  return (
    <section className={`${card} space-y-3`} aria-labelledby="outreach-heading">
      <div className="flex flex-wrap items-center justify-between gap-2">
        <h2 id="outreach-heading" className="font-semibold">
          Outreach drafts
        </h2>
        <span className={muted}>
          {approved_today}/{daily_cap} approved today
        </span>
      </div>
      <p className={muted}>{note}</p>
      <NewDraft
        jobId={job.id}
        contacts={job.contacts}
        aiAvailable={aiAvailable}
      />
      {items.length === 0 ? (
        <p className={muted}>No drafts for this job yet.</p>
      ) : (
        <ul className="space-y-3">
          {items.map((draft) => (
            <DraftCard
              key={`${draft.id}-${draft.status}-${draft.lint.words}`}
              jobId={job.id}
              draft={draft}
            />
          ))}
        </ul>
      )}
    </section>
  );
}

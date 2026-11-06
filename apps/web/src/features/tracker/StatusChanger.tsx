"use client";

import { useState } from "react";

import { Modal } from "@/components/Modal";
import { button, input, muted, primaryButton } from "@/components/ui";
import { ApiError } from "@/lib/api/client";
import type { JobSummary, Status } from "@/lib/api/types";

import { useChangeStatus } from "./hooks";

type Ask = { job: JobSummary; status: Status; reopen: boolean; message: string };

const NEEDS_EXPLANATION = new Set(["note_required", "reason_required", "reopen_required"]);

function inDays(days: number): string {
  return new Date(Date.now() + days * 86_400_000).toISOString().slice(0, 10);
}

/**
 * Status changes go straight through. If the rules need a note (skipping a stage) or a reason
 * (reopening a final application), the server says so and we ask once, then retry.
 */
export function useStatusChanger() {
  const mutation = useChangeStatus();
  const [ask, setAsk] = useState<Ask | null>(null);
  const [error, setError] = useState<string | null>(null);

  async function request(
    job: JobSummary,
    status: Status,
    extra: { note?: string; reopen?: boolean } = {},
  ) {
    setError(null);
    try {
      await mutation.mutateAsync({
        job,
        status,
        ...extra,
        // A sensible default so applied jobs never slip through without a follow-up.
        nextFollowupOn:
          status === "Applied - Pending" && !job.application.next_followup_on
            ? inDays(5)
            : undefined,
      });
      setAsk(null);
    } catch (caught) {
      if (caught instanceof ApiError && caught.code && NEEDS_EXPLANATION.has(caught.code)) {
        setAsk({
          job,
          status,
          reopen: caught.code !== "note_required",
          message: caught.detail ?? caught.message,
        });
      } else if (caught instanceof ApiError && caught.status === 409) {
        setAsk(null);
        setError("This job was changed elsewhere. It has been refreshed; please try again.");
      } else {
        setAsk(null);
        setError(caught instanceof Error ? caught.message : "Could not change the status.");
      }
    }
  }

  const dialog = (
    <NoteDialog
      ask={ask}
      busy={mutation.isPending}
      onCancel={() => setAsk(null)}
      onSubmit={(note) => ask && request(ask.job, ask.status, { note, reopen: ask.reopen })}
    />
  );

  return { request, dialog, error, busy: mutation.isPending };
}

function NoteDialog({
  ask,
  busy,
  onCancel,
  onSubmit,
}: {
  ask: Ask | null;
  busy: boolean;
  onCancel: () => void;
  onSubmit: (note: string) => void;
}) {
  const [note, setNote] = useState("");
  return (
    <Modal open={ask !== null} onClose={onCancel} title={ask?.reopen ? "Reopen application" : "Add a note"}>
      <form
        onSubmit={(event) => {
          event.preventDefault();
          onSubmit(note.trim());
          setNote("");
        }}
        className="space-y-3"
      >
        <p className={muted}>{ask?.message}</p>
        <label className="block space-y-1 text-sm">
          <span>{ask?.reopen ? "Why is it being reopened?" : "Note (kept in the history)"}</span>
          <textarea
            required
            value={note}
            onChange={(event) => setNote(event.target.value)}
            rows={3}
            className={input}
          />
        </label>
        <div className="flex justify-end gap-2">
          <button type="button" onClick={onCancel} className={button}>
            Cancel
          </button>
          <button type="submit" disabled={busy || !note.trim()} className={primaryButton}>
            Move to {ask?.status}
          </button>
        </div>
      </form>
    </Modal>
  );
}

export function StatusSelect({
  job,
  onChange,
  statuses,
  label,
}: {
  job: JobSummary;
  onChange: (status: Status) => void;
  statuses: Status[];
  label: string;
}) {
  return (
    <select
      aria-label={label}
      value={job.application.status}
      onChange={(event) => onChange(event.target.value as Status)}
      className="rounded border border-input bg-background px-2 py-1 text-xs"
    >
      {statuses.map((status) => (
        <option key={status} value={status}>
          {status}
        </option>
      ))}
    </select>
  );
}

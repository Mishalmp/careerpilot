"use client";

import { ExternalLink } from "lucide-react";
import Link from "next/link";
import { useState } from "react";

import { Modal } from "@/components/Modal";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Field, Textarea } from "@/components/ui/field";
import { Alert } from "@/components/ui/states";
import type { LinkResult } from "@/lib/api/types";

import { useAddLinks } from "./hooks";

const WORDS = {
  added: "Saved",
  already_saved: "Already saved",
  rejected: "Not saved",
} as const;

/** Paste job links from LinkedIn, Indeed, Naukri or a company page. They are saved, never opened. */
export function PasteLinksDialog({
  open,
  onClose,
}: {
  open: boolean;
  onClose: () => void;
}) {
  const add = useAddLinks();
  const [text, setText] = useState("");
  const [results, setResults] = useState<LinkResult[] | null>(null);
  // One entry per link. A line with several addresses gives each one; a line with none is kept
  // whole so it comes back as "Not saved" instead of being cut into single words.
  const links = text.split(/\r?\n/).flatMap((line) => {
    const found = line.match(/https?:\/\/\S+/g);
    return found ?? (line.trim() ? [line.trim()] : []);
  });

  function close() {
    setText("");
    setResults(null);
    add.reset();
    onClose();
  }

  return (
    <Modal open={open} onClose={close} title="Paste job links">
      <form
        className="flex flex-col gap-4"
        onSubmit={(event) => {
          event.preventDefault();
          add.mutate(links, { onSuccess: setResults });
        }}
      >
        <p className="text-sm text-muted-foreground">
          One link per line, from LinkedIn, Indeed, Naukri, Glassdoor or a
          company page. The app does not open these sites (they forbid
          automation); it saves each link so you can click it later and use Easy
          Apply yourself. LinkedIn links also give the role and company.
        </p>
        <Field
          label="Job links"
          help={
            links.length > 0
              ? `${links.length} link${links.length === 1 ? "" : "s"}`
              : "Up to 50 at a time"
          }
        >
          {(p) => (
            <Textarea
              rows={6}
              value={text}
              placeholder="https://www.linkedin.com/jobs/view/… (one link per line)"
              onChange={(event) => setText(event.target.value)}
              {...p}
            />
          )}
        </Field>
        {add.isError && <Alert tone="danger">{add.error.message}</Alert>}
        {results && (
          <ul className="flex flex-col gap-2" aria-label="Results">
            {results.map((r, i) => (
              <li
                key={`${r.link}-${i}`}
                className="flex flex-wrap items-center justify-between gap-2 rounded-lg border border-border-subtle p-2 text-sm"
              >
                <div className="min-w-0">
                  <p className="truncate font-medium">{r.title ?? r.link}</p>
                  <p className="truncate text-xs text-muted-foreground">
                    {r.company ?? r.note}
                    {r.portal ? ` · ${r.portal}` : ""}
                    {r.needs_details
                      ? " · add the company or role when you open it"
                      : ""}
                  </p>
                </div>
                <div className="flex items-center gap-2">
                  <Badge
                    tone={
                      r.status === "rejected"
                        ? "danger"
                        : r.status === "added"
                          ? "success"
                          : "neutral"
                    }
                  >
                    {WORDS[r.status]}
                  </Badge>
                  {r.job_id && (
                    <Link
                      href={`/jobs/${r.job_id}`}
                      className="inline-flex items-center gap-1 text-accent-text underline"
                      aria-label={`Open ${r.title ?? "job"}`}
                    >
                      <ExternalLink className="size-3.5" aria-hidden="true" />{" "}
                      Open
                    </Link>
                  )}
                </div>
              </li>
            ))}
          </ul>
        )}
        <div className="flex justify-end gap-2">
          <Button type="button" onClick={close}>
            {results ? "Done" : "Cancel"}
          </Button>
          {!results && (
            <Button
              type="submit"
              variant="primary"
              disabled={links.length === 0 || links.length > 50}
              loading={add.isPending}
            >
              Save {links.length || ""} link{links.length === 1 ? "" : "s"}
            </Button>
          )}
        </div>
      </form>
    </Modal>
  );
}

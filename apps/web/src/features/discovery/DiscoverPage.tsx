"use client";

import Link from "next/link";
import { useState } from "react";

import {
  button,
  card,
  input,
  muted,
  primaryButton,
  select,
} from "@/components/ui";

import {
  type Candidate,
  type CandidateStatus,
  type DiscoverySource,
  useAcceptCandidate,
  useAddSource,
  useCandidates,
  useDeleteSource,
  useDigest,
  useRunSource,
  useSetCandidate,
  useSources,
  useUpdateSource,
} from "./hooks";
import { PageHeader } from "@/components/ui/page-header";

import { Feeds } from "./Feeds";
import { SearchProfiles } from "./SearchProfiles";

const KINDS = ["greenhouse", "lever", "ashby"] as const;

function words(value: string): string[] {
  return value
    .split(",")
    .map((w) => w.trim())
    .filter(Boolean);
}

function DigestCard() {
  const digest = useDigest();
  if (!digest.data) {
    return (
      <section className={card} aria-labelledby="digest-heading">
        <h2 id="digest-heading" className="font-semibold">
          Daily digest
        </h2>
        <p className={muted}>
          {digest.isPending
            ? "Loading..."
            : "No digest yet. The first one is built in the morning."}
        </p>
      </section>
    );
  }
  const { payload, day } = digest.data;
  return (
    <section className={`${card} space-y-2`} aria-labelledby="digest-heading">
      <h2 id="digest-heading" className="font-semibold">
        Daily digest · {day}
      </h2>
      <ul className="list-disc space-y-0.5 pl-5 text-sm">
        <li>
          {payload.new_listings_24h} new listing(s) in the last day,{" "}
          {payload.waiting_listings} waiting for your decision.
        </li>
        <li>
          {payload.due_followups.length === 0
            ? "No follow-ups due."
            : `${payload.due_followups.length} follow-up(s) due.`}{" "}
          {payload.due_followups.slice(0, 3).map((f) => (
            <Link
              key={f.job_id}
              href={`/jobs/${f.job_id}`}
              className="underline"
            >
              {f.company}
              {" · "}
              {f.title}
              {"; "}
            </Link>
          ))}
        </li>
        {payload.failed_tasks_24h > 0 && (
          <li className="text-danger-text">
            {payload.failed_tasks_24h} background task(s) failed.{" "}
            <Link href="/tasks" className="underline">
              See tasks
            </Link>
          </li>
        )}
      </ul>
    </section>
  );
}

function AddSource() {
  const add = useAddSource();
  const [kind, setKind] = useState<(typeof KINDS)[number]>("greenhouse");
  const [board, setBoard] = useState("");
  const [company, setCompany] = useState("");
  const [include, setInclude] = useState("");
  const [exclude, setExclude] = useState("");

  return (
    <form
      className={`${card} space-y-2`}
      onSubmit={(e) => {
        e.preventDefault();
        add.mutate(
          {
            kind,
            board: board.trim(),
            company_name: company.trim(),
            include: words(include),
            exclude: words(exclude),
          },
          {
            onSuccess: () => {
              setBoard("");
              setCompany("");
              setInclude("");
              setExclude("");
            },
          },
        );
      }}
    >
      <h2 className="font-semibold">Follow one company&apos;s job board</h2>
      <p className={muted}>
        Public boards only (Greenhouse, Lever, Ashby), read once a day. The
        board name is the last part of the address, for example{" "}
        <code>acme</code> in boards.greenhouse.io/acme. LinkedIn, Indeed and
        Glassdoor are never fetched.
      </p>
      <div className="grid gap-2 sm:grid-cols-3">
        <select
          className={`${select} w-full`}
          aria-label="Provider"
          value={kind}
          onChange={(e) => setKind(e.target.value as typeof kind)}
        >
          {KINDS.map((k) => (
            <option key={k}>{k}</option>
          ))}
        </select>
        <input
          className={input}
          required
          placeholder="Board name"
          aria-label="Board name"
          value={board}
          onChange={(e) => setBoard(e.target.value)}
        />
        <input
          className={input}
          required
          placeholder="Company name"
          aria-label="Company name"
          value={company}
          onChange={(e) => setCompany(e.target.value)}
        />
        <input
          className={input}
          placeholder="Title must contain (comma separated)"
          aria-label="Include words"
          value={include}
          onChange={(e) => setInclude(e.target.value)}
        />
        <input
          className={input}
          placeholder="Title must not contain"
          aria-label="Exclude words"
          value={exclude}
          onChange={(e) => setExclude(e.target.value)}
        />
        <button
          type="submit"
          className={primaryButton}
          disabled={add.isPending}
        >
          Follow
        </button>
      </div>
      {add.error && (
        <p role="alert" className="text-sm text-danger-text">
          {add.error.message}
        </p>
      )}
    </form>
  );
}

function SourceRow({ source }: { source: DiscoverySource }) {
  const run = useRunSource();
  const update = useUpdateSource();
  const remove = useDeleteSource();
  return (
    <li className="space-y-1 border-b border-border-subtle py-2 last:border-0">
      <div className="flex flex-wrap items-center justify-between gap-2 text-sm">
        <span>
          <strong>{source.company_name}</strong> · {source.kind}/{source.board}
          {source.include.length > 0 && ` · only ${source.include.join(", ")}`}
          {source.exclude.length > 0 && ` · not ${source.exclude.join(", ")}`}
        </span>
        <span className="flex flex-wrap gap-2">
          <button
            type="button"
            className={button}
            disabled={run.isPending}
            onClick={() => run.mutate(source.id)}
          >
            {run.isPending ? "Reading..." : "Read now"}
          </button>
          <button
            type="button"
            className={button}
            onClick={() =>
              update.mutate({ id: source.id, enabled: !source.enabled })
            }
          >
            {source.enabled ? "Pause daily reads" : "Resume daily reads"}
          </button>
          <button
            type="button"
            className={button}
            onClick={() => {
              if (
                window.confirm(
                  `Stop following ${source.company_name}? Its unaccepted listings are removed.`,
                )
              ) {
                remove.mutate(source.id);
              }
            }}
          >
            Remove
          </button>
        </span>
      </div>
      <p className={muted}>
        {source.last_run_at
          ? `Last read ${new Date(source.last_run_at).toLocaleString()}, ${source.last_listed ?? 0} on the board.`
          : "Not read yet."}{" "}
        {source.new_count} waiting.
        {!source.enabled && " Paused."}
      </p>
      {source.last_error && (
        <p role="alert" className="text-sm text-danger-text">
          Last read failed: {source.last_error}
        </p>
      )}
      {run.data && (
        <p className={muted}>
          Found {run.data.listed} on the board, {run.data.kept} after your
          filters, {run.data.new} new.
          {run.data.outside_search > 0 &&
            ` ${run.data.outside_search} more matched your words but are outside the places or ways you search.`}
        </p>
      )}
      {(run.error ?? update.error ?? remove.error) && (
        <p role="alert" className="text-sm text-danger-text">
          {(run.error ?? update.error ?? remove.error)?.message}
        </p>
      )}
    </li>
  );
}

function CandidateRow({ candidate }: { candidate: Candidate }) {
  const accept = useAcceptCandidate();
  const set = useSetCandidate();
  return (
    <li className="space-y-1 border-b border-border-subtle py-2 last:border-0">
      <div className="flex flex-wrap items-center justify-between gap-2">
        <span className="text-sm">
          <a
            href={candidate.url}
            target="_blank"
            rel="noopener noreferrer"
            className="font-medium underline underline-offset-2"
          >
            {candidate.title}
          </a>{" "}
          · {candidate.company_name}
          {candidate.location && ` · ${candidate.location}`}
          {candidate.remote && (candidate.location ? " · remote" : " · remote (where from: not stated)")}
          {candidate.via && ` · via ${candidate.via}`}
          {candidate.published_on && ` · posted ${candidate.published_on}`}
          {!candidate.listed && (
            <span className="text-warning-text">
              {" "}
              · no longer on the board
            </span>
          )}
        </span>
        <span className="flex gap-2">
          {candidate.status === "new" && (
            <>
              <button
                type="button"
                className={primaryButton}
                disabled={accept.isPending}
                onClick={() => accept.mutate(candidate.id)}
              >
                Add to tracker
              </button>
              <button
                type="button"
                className={button}
                onClick={() =>
                  set.mutate({ id: candidate.id, action: "dismiss" })
                }
              >
                Dismiss
              </button>
            </>
          )}
          {candidate.status === "dismissed" && (
            <button
              type="button"
              className={button}
              onClick={() =>
                set.mutate({ id: candidate.id, action: "restore" })
              }
            >
              Bring back
            </button>
          )}
          {candidate.status === "accepted" && candidate.job_id && (
            <Link
              href={`/jobs/${candidate.job_id}`}
              className="text-sm underline"
            >
              Open in tracker
            </Link>
          )}
        </span>
      </div>
      {accept.data?.already_tracked && (
        <p className={muted}>
          You were already tracking this job; nothing was duplicated.
        </p>
      )}
      {(accept.error ?? set.error) && (
        <p role="alert" className="text-sm text-danger-text">
          {(accept.error ?? set.error)?.message}
        </p>
      )}
    </li>
  );
}

export function DiscoverPage() {
  const sources = useSources();
  const [status, setStatus] = useState<CandidateStatus>("new");
  const candidates = useCandidates(status);

  return (
    <div className="space-y-6">
      <PageHeader
        title="Discover"
        description="Find jobs without searching each site: say where and how you want to work, follow free feeds and company boards, and decide on what arrives."
      />
      <DigestCard />
      <SearchProfiles />
      <Feeds followed={sources.data ?? []} />
      <AddSource />

      <section
        className={`${card} space-y-2`}
        aria-labelledby="sources-heading"
      >
        <h2 id="sources-heading" className="font-semibold">
          Boards you follow
        </h2>
        {sources.isPending && <p className={muted}>Loading...</p>}
        {sources.isError && (
          <p role="alert">Could not load them: {sources.error.message}</p>
        )}
        {sources.data?.length === 0 && <p className={muted}>None yet.</p>}
        <ul>
          {sources.data?.map((s) => (
            <SourceRow key={s.id} source={s} />
          ))}
        </ul>
      </section>

      <section className={`${card} space-y-2`} aria-labelledby="inbox-heading">
        <div className="flex flex-wrap items-center justify-between gap-2">
          <h2 id="inbox-heading" className="font-semibold">
            Listings
          </h2>
          <select
            className={select}
            aria-label="Show"
            value={status}
            onChange={(e) => setStatus(e.target.value as CandidateStatus)}
          >
            <option value="new">Waiting for you</option>
            <option value="accepted">Added to tracker</option>
            <option value="dismissed">Dismissed</option>
          </select>
        </div>
        {candidates.isPending && <p className={muted}>Loading...</p>}
        {candidates.isError && (
          <p role="alert">Could not load them: {candidates.error.message}</p>
        )}
        {candidates.data?.items.length === 0 && (
          <p className={muted}>Nothing here.</p>
        )}
        {candidates.data &&
          candidates.data.total > candidates.data.items.length && (
            <p className={muted}>
              Showing the newest {candidates.data.items.length} of{" "}
              {candidates.data.total}. Dismiss or add some to see the rest, or
              narrow what a board returns with title words.
            </p>
          )}
        <ul>
          {candidates.data?.items.map((c) => (
            <CandidateRow key={`${c.id}-${c.status}`} candidate={c} />
          ))}
        </ul>
      </section>
    </div>
  );
}

"use client";

import { useState } from "react";

import { button, card, input, muted, primaryButton } from "@/components/ui";

import {
  type IntelItem,
  useAddSource,
  useDeleteSource,
  useIntel,
  usePeers,
  useQuestionsToAsk,
} from "./hooks";

function Evidence({ item }: { item: IntelItem }) {
  return (
    <li className="space-y-0.5 text-sm">
      <p>
        {item.text}{" "}
        {item.inferred && (
          <span className="rounded bg-amber-100 px-1 text-xs text-amber-900 dark:bg-amber-900/40 dark:text-amber-100">
            inferred from {item.similar_to}
          </span>
        )}
      </p>
      <blockquote className="border-l-2 border-black/20 pl-2 text-xs dark:border-white/30">
        “{item.quote}”
      </blockquote>
      <p className={`${muted} text-xs`}>
        {item.source_url ? (
          <a
            href={item.source_url}
            target="_blank"
            rel="noopener noreferrer"
            className="underline"
          >
            {item.source_label}
          </a>
        ) : (
          item.source_label
        )}
        {item.published_on ? ` · ${item.published_on}` : " · undated"} ·
        reliability {item.reliability}/100
      </p>
    </li>
  );
}

function AddSource({ jobId }: { jobId: string }) {
  const add = useAddSource(jobId);
  const [label, setLabel] = useState("");
  const [text, setText] = useState("");
  const [url, setUrl] = useState("");
  const [about, setAbout] = useState("");
  const [published, setPublished] = useState("");

  return (
    <form
      className="space-y-2 rounded border border-black/10 p-3 dark:border-white/15"
      onSubmit={(e) => {
        e.preventDefault();
        add.mutate(
          {
            label,
            text: text || null,
            url: url || null,
            about_company: about || null,
            published_on: published || null,
          },
          {
            onSuccess: () => {
              setLabel("");
              setText("");
              setUrl("");
              setAbout("");
              setPublished("");
            },
          },
        );
      }}
    >
      <p className="text-sm font-medium">Add a source</p>
      <p className={muted}>
        Paste text you read yourself (review sites are for you to read, not for
        scraping), or give a company page to fetch.
      </p>
      <input
        className={input}
        required
        placeholder="Name of the source"
        aria-label="Source name"
        value={label}
        onChange={(e) => setLabel(e.target.value)}
      />
      <textarea
        className={`${input} min-h-28`}
        placeholder="Pasted text (at least 40 characters)"
        aria-label="Pasted text"
        value={text}
        onChange={(e) => setText(e.target.value)}
      />
      <input
        className={input}
        placeholder="Page address (fetched if no text is pasted)"
        aria-label="Page address"
        value={url}
        onChange={(e) => setUrl(e.target.value)}
      />
      <div className="grid gap-2 sm:grid-cols-2">
        <input
          className={input}
          placeholder="About another company? Its name"
          aria-label="About company"
          value={about}
          onChange={(e) => setAbout(e.target.value)}
        />
        <input
          className={input}
          type="date"
          aria-label="Published on"
          value={published}
          onChange={(e) => setPublished(e.target.value)}
        />
      </div>
      <button type="submit" className={primaryButton} disabled={add.isPending}>
        {add.isPending ? "Reading..." : "Add"}
      </button>
      {add.error && (
        <p role="alert" className="text-sm text-red-600 dark:text-red-400">
          {add.error.message}
        </p>
      )}
      {add.data && (
        <p className={muted}>
          Kept {add.data.kept} fact(s)
          {add.data.dropped > 0 &&
            `, dropped ${add.data.dropped} whose quote is not in the text`}
          .
        </p>
      )}
    </form>
  );
}

export function IntelPanel({ jobId }: { jobId: string }) {
  const query = useIntel(jobId);
  const remove = useDeleteSource(jobId);
  const peers = usePeers(jobId);
  const questions = useQuestionsToAsk(jobId);

  if (query.isPending)
    return <p className={muted}>Loading interview intel...</p>;
  if (query.isError)
    return (
      <p role="alert">Could not load interview intel: {query.error.message}</p>
    );
  const { brief, sources, note, ai_available, company_name } = query.data;

  return (
    <section className={`${card} space-y-4`} aria-labelledby="intel-heading">
      <h2 id="intel-heading" className="font-semibold">
        How {company_name} interviews
      </h2>
      <p className={muted}>{note}</p>
      {brief.needs_more_sources && (
        <p className="text-sm text-amber-700 dark:text-amber-400">
          Fewer than two recent sources about this company. Facts from similar
          companies are labelled inferred.
          {ai_available && (
            <>
              {" "}
              <button
                type="button"
                className="underline"
                disabled={peers.isPending}
                onClick={() => peers.mutate()}
              >
                Suggest companies to read about
              </button>
            </>
          )}
        </p>
      )}
      {peers.data && (
        <div className="text-sm">
          <p className={muted}>{peers.data.note}</p>
          <ul className="list-disc pl-5">
            {peers.data.peers.map((p) => (
              <li key={p.name}>
                <strong>{p.name}</strong>: {p.why}
              </li>
            ))}
          </ul>
        </div>
      )}
      {peers.error && (
        <p role="alert" className="text-sm text-red-600">
          {peers.error.message}
        </p>
      )}

      {brief.rounds.length > 0 && (
        <div>
          <h3 className="text-sm font-semibold">Rounds</h3>
          <ul className="space-y-2">
            {brief.rounds.map((i) => (
              <Evidence key={i.id} item={i} />
            ))}
          </ul>
        </div>
      )}
      {brief.topics.length > 0 && (
        <div>
          <h3 className="text-sm font-semibold">
            Topics, most-mentioned first
          </h3>
          <ul className="flex flex-wrap gap-2 text-sm">
            {brief.topics.map((t) => (
              <li
                key={t.key}
                className="rounded border border-black/10 px-2 py-0.5 dark:border-white/20"
              >
                {t.key} · {t.sources} source{t.sources === 1 ? "" : "s"}
                {t.inferred_only && " · inferred"}
                {t.prep_topics.length > 0 && (
                  <span className={muted}>
                    {" "}
                    · prep: {t.prep_topics.join(", ")}
                  </span>
                )}
              </li>
            ))}
          </ul>
        </div>
      )}
      {brief.likely_questions.length > 0 && (
        <div>
          <h3 className="text-sm font-semibold">
            Questions people reported being asked
          </h3>
          <ul className="space-y-2">
            {brief.likely_questions.map((i) => (
              <Evidence key={i.id} item={i} />
            ))}
          </ul>
        </div>
      )}
      {brief.tips.length > 0 && (
        <div>
          <h3 className="text-sm font-semibold">Tips</h3>
          <ul className="space-y-2">
            {brief.tips.map((i) => (
              <Evidence key={i.id} item={i} />
            ))}
          </ul>
        </div>
      )}

      {ai_available && (
        <div className="space-y-1">
          <button
            type="button"
            className={button}
            disabled={questions.isPending}
            onClick={() => questions.mutate()}
          >
            Suggest questions to ask them
          </button>
          {questions.data && (
            <>
              <p className={muted}>{questions.data.note}</p>
              <ul className="list-disc pl-5 text-sm">
                {questions.data.questions.map((q) => (
                  <li key={q}>{q}</li>
                ))}
              </ul>
            </>
          )}
          {questions.error && (
            <p role="alert" className="text-sm text-red-600">
              {questions.error.message}
            </p>
          )}
        </div>
      )}

      <div>
        <h3 className="text-sm font-semibold">Sources</h3>
        {sources.length === 0 ? (
          <p className={muted}>None yet.</p>
        ) : (
          <ul className="space-y-1 text-sm">
            {sources.map((s) => (
              <li
                key={s.id}
                className="flex flex-wrap items-center justify-between gap-2"
              >
                <span>
                  {s.label} · {s.kind}
                  {s.inferred && ` · about ${s.about_company}`} · {s.item_count}{" "}
                  fact(s)
                </span>
                <button
                  type="button"
                  className="text-xs underline"
                  disabled={remove.isPending}
                  onClick={() => remove.mutate(s.id)}
                >
                  Remove
                </button>
              </li>
            ))}
          </ul>
        )}
      </div>
      <AddSource jobId={jobId} />
    </section>
  );
}

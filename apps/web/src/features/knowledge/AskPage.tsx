"use client";

import Link from "next/link";
import { Fragment, useState } from "react";

import { button, card, input, muted, primaryButton } from "@/components/ui";

import { type AskResult, type Hit, useAsk, useIngest, useKnowledgeStatus } from "./hooks";

const EXAMPLES = [
  "Why does a lambda in a loop capture the last value?",
  "How do I make an upsert idempotent in Postgres?",
  "When should I use BackgroundTasks instead of Celery?",
];

export function AskPage() {
  const status = useKnowledgeStatus();
  const ingest = useIngest();
  const ask = useAsk();
  const [question, setQuestion] = useState("");
  const empty = status.data?.documents === 0;

  return (
    <div className="space-y-6">
      <div className="space-y-1">
        <h1 className="text-2xl font-semibold">Ask my notes</h1>
        <p className={muted}>
          Searches your study guides and private notes by meaning and by words. Answers come only
          from your notes, with sources.
        </p>
      </div>

      <section className={`${card} flex flex-wrap items-center gap-3 text-sm`}>
        {status.data && (
          <span className={muted}>
            {status.data.documents} notes, {status.data.chunks} passages
            {status.data.indexed_at && `, indexed ${new Date(status.data.indexed_at).toLocaleString("en-GB")}`}
            {" · "}
            written answers {status.data.ai_enabled ? "on" : "off (no AI key set)"}
          </span>
        )}
        <button
          type="button"
          className={`${button} ml-auto`}
          disabled={ingest.isPending}
          onClick={() => ingest.mutate()}
        >
          {ingest.isPending ? "Indexing..." : "Update index"}
        </button>
        {ingest.isPending && (
          <span className={muted}>The first run downloads the search model (about 130 MB).</span>
        )}
        {ingest.data && (
          <span role="status" className={muted}>
            Added {ingest.data.added}, updated {ingest.data.updated}, unchanged {ingest.data.unchanged}.
          </span>
        )}
        {ingest.error && (
          <span role="alert" className="text-danger-text">
            {ingest.error.message}
          </span>
        )}
      </section>

      {empty && (
        <p className={muted}>Nothing is indexed yet. Press “Update index” first.</p>
      )}

      <form
        className="space-y-2"
        onSubmit={(event) => {
          event.preventDefault();
          if (question.trim().length >= 2) ask.mutate(question.trim());
        }}
      >
        <label className="block space-y-1 text-sm">
          <span>Your question</span>
          <input
            value={question}
            onChange={(event) => setQuestion(event.target.value)}
            maxLength={500}
            placeholder="Ask in plain English"
            className={input}
          />
        </label>
        <div className="flex flex-wrap items-center gap-2">
          <button type="submit" disabled={ask.isPending || empty} className={primaryButton}>
            {ask.isPending ? "Searching..." : "Ask"}
          </button>
          {EXAMPLES.map((example) => (
            <button key={example} type="button" className={button} onClick={() => setQuestion(example)}>
              {example}
            </button>
          ))}
        </div>
      </form>

      <div aria-live="polite">
        {ask.error && (
          <p role="alert" className="text-danger-text">
            {ask.error.message}
          </p>
        )}
        {ask.data && <Result result={ask.data} />}
      </div>
    </div>
  );
}

function Result({ result }: { result: AskResult }) {
  if (result.mode === "answered" && result.answer) {
    return (
      <div className="space-y-4">
        <section className={`${card} space-y-2`}>
          <h2 className="font-semibold">Answer</h2>
          <p className="whitespace-pre-wrap">
            <Cited text={result.answer} />
          </p>
        </section>
        <section className="space-y-2">
          <h2 className="font-semibold">Sources</h2>
          <ol className="space-y-2">
            {result.citations.map((citation) => (
              <li key={citation.number} id={`source-${citation.number}`}>
                <Passage hit={citation.hit} label={`[${citation.number}]`} />
              </li>
            ))}
          </ol>
        </section>
      </div>
    );
  }

  const heading: Record<string, string> = {
    not_in_notes: "Your notes do not seem to cover this.",
    retrieval_only: "Written answers are off (no AI key). The most relevant passages:",
    ungrounded: "The AI answered without citing your notes, so the answer was withheld. Closest passages:",
    refused: "The AI declined to answer. Closest passages:",
  };
  return (
    <section className="space-y-3">
      <p className="font-medium">{heading[result.mode]}</p>
      {result.mode === "not_in_notes" && result.hits.length > 0 && (
        <p className={muted}>Closest matches, which are probably not what you need:</p>
      )}
      <ul className="space-y-2">
        {result.hits.slice(0, result.mode === "not_in_notes" ? 3 : 6).map((hit) => (
          <li key={hit.chunk_id}>
            <Passage hit={hit} />
          </li>
        ))}
      </ul>
    </section>
  );
}

/** Turns [1] in the answer into links to the matching source. The text itself is shown as plain text. */
function Cited({ text }: { text: string }) {
  const parts = text.split(/(\[\d+\])/g);
  return (
    <>
      {parts.map((part, index) => {
        const match = /^\[(\d+)\]$/.exec(part);
        return match ? (
          <a key={index} href={`#source-${match[1]}`} className="align-super text-xs font-medium underline">
            {part}
          </a>
        ) : (
          <Fragment key={index}>{part}</Fragment>
        );
      })}
    </>
  );
}

function Passage({ hit, label }: { hit: Hit; label?: string }) {
  return (
    <details className={card} open={Boolean(label)}>
      <summary className="flex cursor-pointer flex-wrap items-center gap-2 text-sm">
        {label && <strong>{label}</strong>}
        <span className="font-medium">{hit.document_title}</span>
        {hit.heading_path && <span className={muted}>{hit.heading_path}</span>}
        {hit.kind === "private" && <span className={muted}>(private)</span>}
        {hit.similarity !== null && (
          <span className={`${muted} ml-auto`}>match {Math.round(hit.similarity * 100)}%</span>
        )}
      </summary>
      <p className="mt-2 whitespace-pre-wrap text-sm">{hit.text}</p>
      <Link href={`/prep/guides/${hit.document_name}`} className="mt-2 inline-block text-sm underline">
        Open the full guide
      </Link>
    </details>
  );
}

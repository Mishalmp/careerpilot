"use client";

import Link from "next/link";
import { useParams } from "next/navigation";
import { useState } from "react";

import { card, input, muted, primaryButton } from "@/components/ui";

import { useAnswerMock, useMockSession } from "./hooks";

export function MockSessionPage() {
  const { id } = useParams<{ id: string }>();
  const query = useMockSession(id);
  const answer = useAnswerMock(id);
  const [text, setText] = useState("");

  if (query.isPending) return <p className={muted}>Loading...</p>;
  if (query.isError) {
    return (
      <p role="alert">
        Could not load this interview: {query.error.message}.{" "}
        <Link href="/mock" className="underline">
          Back
        </Link>
      </p>
    );
  }
  const session = query.data;
  const summary = session.summary;

  return (
    <div className="space-y-5">
      <Link href="/mock" className={`${muted} hover:underline`}>
        &larr; All mock interviews
      </Link>
      <header className="space-y-1">
        <h1 className="text-2xl font-semibold">{session.title}</h1>
        <p className={muted}>
          {session.finished
            ? "Finished"
            : `Question ${(session.current_turn ?? 0) + 1} of ${session.total_questions}`}
          . {session.note}
        </p>
      </header>

      <ol className="space-y-4">
        {session.turns.map((turn, index) => (
          <li key={index} className={`${card} space-y-2`}>
            <p className="text-xs uppercase tracking-wide text-zinc-500">
              {index + 1}. {turn.topic}
            </p>
            <p className="font-medium">{turn.question}</p>
            {turn.answer !== null && (
              <>
                <p className="whitespace-pre-wrap rounded bg-black/5 p-2 text-sm dark:bg-white/10">
                  {turn.answer}
                </p>
                <p className="text-sm">
                  <strong>{turn.score}/5.</strong> {turn.feedback}
                </p>
              </>
            )}
            {index === session.current_turn && (
              <form
                className="space-y-2"
                onSubmit={(e) => {
                  e.preventDefault();
                  answer.mutate(
                    { turn: index, answer: text },
                    { onSuccess: () => setText("") },
                  );
                }}
              >
                <textarea
                  className={`${input} min-h-36`}
                  aria-label="Your answer"
                  placeholder="Answer as you would out loud."
                  value={text}
                  onChange={(e) => setText(e.target.value)}
                  required
                  maxLength={4000}
                />
                <button
                  type="submit"
                  className={primaryButton}
                  disabled={answer.isPending}
                >
                  {answer.isPending ? "Scoring..." : "Submit answer"}
                </button>
                {answer.error && (
                  <p
                    role="alert"
                    className="text-sm text-red-600 dark:text-red-400"
                  >
                    {answer.error.message}
                  </p>
                )}
              </form>
            )}
          </li>
        ))}
      </ol>

      {summary && (
        <section
          className={`${card} space-y-2`}
          aria-labelledby="summary-heading"
        >
          <h2 id="summary-heading" className="font-semibold">
            Summary
          </h2>
          <p>
            Average {summary.average ?? "n/a"}/5 over {summary.answered}{" "}
            answers.
          </p>
          {summary.weak.length > 0 ? (
            <p className="text-sm text-amber-700 dark:text-amber-400">
              Revisit:{" "}
              {summary.weak.map((t) => `${t.topic} (${t.average})`).join(", ")}.{" "}
              <Link href="/prep" className="underline">
                Open prep
              </Link>
            </p>
          ) : (
            <p className={muted}>No topic averaged below 3.</p>
          )}
          {summary.strong.length > 0 && (
            <p className={muted}>
              Strong:{" "}
              {summary.strong
                .map((t) => `${t.topic} (${t.average})`)
                .join(", ")}
              .
            </p>
          )}
        </section>
      )}
    </div>
  );
}

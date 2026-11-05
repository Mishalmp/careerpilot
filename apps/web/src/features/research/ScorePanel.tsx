"use client";

import { button, card, muted, primaryButton } from "@/components/ui";

import { useComputeScore, useScore } from "./hooks";

const CHANCE = {
  good: "Good fit",
  possible: "Possible",
  unlikely: "Unlikely",
  unknown: "Not enough information",
} as const;

export function ScorePanel({ jobId }: { jobId: string }) {
  const query = useScore(jobId);
  const compute = useComputeScore(jobId);

  if (query.isPending) return <p className={muted}>Loading score...</p>;
  if (query.isError)
    return <p role="alert">Could not load the score: {query.error.message}</p>;
  const score = compute.data ?? query.data;

  return (
    <section className={`${card} space-y-3`} aria-labelledby="score-heading">
      <div className="flex flex-wrap items-center justify-between gap-2">
        <h2 id="score-heading" className="font-semibold">
          How well does it fit you?
        </h2>
        {score && score.score !== null && (
          <p className="font-medium">
            {score.score}/100 · {CHANCE[score.chance]}
            {score.priority && (
              <span className={muted}> · {score.priority} priority</span>
            )}
          </p>
        )}
      </div>
      <div className="flex flex-wrap gap-2">
        <button
          type="button"
          className={primaryButton}
          disabled={compute.isPending}
          onClick={() => compute.mutate(false)}
        >
          {score ? "Recompute" : "Score this job"}
        </button>
        <button
          type="button"
          className={button}
          disabled={compute.isPending}
          onClick={() => compute.mutate(true)}
        >
          Score + read the description
        </button>
      </div>
      {compute.error && (
        <p role="alert" className="text-sm text-red-600 dark:text-red-400">
          {compute.error.message}
        </p>
      )}
      {!score && (
        <p className={muted}>
          Not scored yet. It compares the job with content/private/profile.yaml.
        </p>
      )}
      {score && (
        <>
          {score.stale && (
            <p className="text-sm text-amber-700 dark:text-amber-400">
              Your profile or the scoring rules changed since this was computed.
              Recompute.
            </p>
          )}
          <p className={muted}>
            {score.chance_note} Measured {score.coverage}% of the weight.
          </p>
          {score.blockers.length > 0 && (
            <ul className="list-disc pl-5 text-sm text-red-700 dark:text-red-400">
              {score.blockers.map((b) => (
                <li key={b}>{b}</li>
              ))}
            </ul>
          )}
          <table className="w-full text-sm">
            <caption className="sr-only">Score breakdown</caption>
            <thead>
              <tr className="text-left text-zinc-500">
                <th className="py-1">Part</th>
                <th>Weight</th>
                <th>Score</th>
                <th>Why</th>
              </tr>
            </thead>
            <tbody>
              {score.components.map((c) => (
                <tr
                  key={c.key}
                  className="border-t border-black/5 align-top dark:border-white/10"
                >
                  <td className="py-1 capitalize">{c.key}</td>
                  <td>{c.weight}</td>
                  <td>{c.score ?? "n/a"}</td>
                  <td className={muted}>{c.detail}</td>
                </tr>
              ))}
            </tbody>
          </table>
          {score.reading && (
            <div className="space-y-1 text-sm">
              <p>{score.reading.summary}</p>
              {score.reading.red_flags.map((f) => (
                <p key={f.quote} className="text-red-700 dark:text-red-400">
                  {f.text} <span className="italic">“{f.quote}”</span>
                </p>
              ))}
              {score.reading.dropped_flags > 0 && (
                <p className={muted}>
                  {score.reading.dropped_flags} warning sign(s) from the model
                  were dropped because their quote is not in the description.
                </p>
              )}
            </div>
          )}
        </>
      )}
    </section>
  );
}

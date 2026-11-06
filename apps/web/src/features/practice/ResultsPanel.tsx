"use client";

import { card, muted } from "@/components/ui";

import type { ProblemDetail } from "./hooks";
import type { Outcome, OutcomeStatus, Phase, RunSummary } from "./runner/runner";

const MARK: Record<OutcomeStatus, { symbol: string; label: string; tone: string }> = {
  pass: { symbol: "✓", label: "passed", tone: "text-success-text " },
  fail: { symbol: "✗", label: "wrong answer", tone: "text-danger-text " },
  error: { symbol: "!", label: "error", tone: "text-danger-text " },
  timeout: { symbol: "⏱", label: "timed out", tone: "text-warning-text " },
  skipped: { symbol: "-", label: "not run", tone: "text-muted-foreground" },
};

const show = (value: unknown) => JSON.stringify(value);

function expectedText(problem: ProblemDetail, outcome: Outcome): string | null {
  if (problem.kind === "sql") {
    const test = problem.sql_tests[outcome.index];
    return test ? show({ columns: test.expected.columns, rows: test.expected.rows }) : null;
  }
  const test = problem.function_tests[outcome.index];
  return test ? show(test.expected) : null;
}

function inputText(problem: ProblemDetail, outcome: Outcome): string | null {
  if (problem.kind === "sql") return null;
  const test = problem.function_tests[outcome.index];
  return test ? show(test.args) : null;
}

export function ResultsPanel({
  problem,
  summary,
  running,
  phase,
}: {
  problem: ProblemDetail;
  summary: RunSummary | null;
  running: boolean;
  phase: Phase | null;
}) {
  return (
    <section aria-live="polite" aria-label="Test results" className={`${card} space-y-3`}>
      {running && (
        <p className={muted}>
          {phase === "loading"
            ? "Starting the runtime. The first run downloads it from this app, which can take a few seconds."
            : "Running the tests..."}
        </p>
      )}
      {!running && !summary && <p className={muted}>Run your code to see the results. Ctrl+Enter also runs.</p>}

      {summary?.fatal && (
        <p role="alert" className="text-sm text-danger-text">
          {summary.fatal}
        </p>
      )}

      {summary && !summary.fatal && (
        <>
          <p className="font-medium">
            {summary.passed === summary.total ? "All tests passed" : `${summary.passed} of ${summary.total} tests passed`}
            <span className={`${muted} ml-2`}>{summary.ms} ms</span>
          </p>
          <ol className="space-y-2">
            {summary.outcomes.map((outcome) => (
              <OutcomeRow key={outcome.index} problem={problem} outcome={outcome} />
            ))}
          </ol>
        </>
      )}
    </section>
  );
}

function OutcomeRow({ problem, outcome }: { problem: ProblemDetail; outcome: Outcome }) {
  const mark = MARK[outcome.status];
  const failed = outcome.status !== "pass" && outcome.status !== "skipped";
  const name = outcome.hidden ? `Hidden test ${outcome.index + 1}` : outcome.name;
  const input = failed && !outcome.hidden ? inputText(problem, outcome) : null;
  const expected = failed && !outcome.hidden ? expectedText(problem, outcome) : null;

  return (
    <li className="text-sm">
      <div className={`flex items-center gap-2 ${mark.tone}`}>
        <span aria-hidden="true" className="w-4 text-center font-bold">
          {mark.symbol}
        </span>
        <span className="font-medium">{name}</span>
        <span className="text-xs">({mark.label})</span>
      </div>
      {failed && (
        <dl className="ml-6 mt-1 space-y-1 font-mono text-xs">
          {input && <Line label="input" value={input} />}
          {expected && <Line label="expected" value={expected} />}
          {outcome.actual !== undefined && outcome.actual !== "" && !outcome.hidden && (
            <Line label="got" value={outcome.actual} />
          )}
          {outcome.message && <Line label="message" value={outcome.message} />}
        </dl>
      )}
      {outcome.stdout && !outcome.hidden && (
        <pre className="ml-6 mt-1 whitespace-pre-wrap rounded bg-surface-hover p-2 text-xs">
          {outcome.stdout}
        </pre>
      )}
    </li>
  );
}

function Line({ label, value }: { label: string; value: string }) {
  return (
    <div className="flex gap-2">
      <dt className="w-16 shrink-0 text-muted-foreground">{label}</dt>
      <dd className="break-all">{value}</dd>
    </div>
  );
}

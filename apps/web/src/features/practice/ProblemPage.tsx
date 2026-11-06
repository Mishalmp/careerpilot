"use client";

import Link from "next/link";
import { useParams } from "next/navigation";
import { useState } from "react";
import ReactMarkdown from "react-markdown";
import remarkGfm from "remark-gfm";

import { button, card, muted, primaryButton } from "@/components/ui";

import { CodeEditor } from "./CodeEditor";
import { type ProblemDetail, useProblem, useSubmissions, useSubmit } from "./hooks";
import { DifficultyBadge } from "./ProblemsPage";
import { ResultsPanel } from "./ResultsPanel";
import { type Language, type Phase, type RunSummary, runProblem } from "./runner/runner";

const LABELS: Record<Language, string> = {
  python: "Python",
  javascript: "JavaScript",
  typescript: "TypeScript",
  sql: "SQL",
};

// Drafts are a per-browser convenience, so every access tolerates storage being unavailable.
const draftKey = (slug: string, language: Language) => `cp-draft:${slug}:${language}`;
function readDraft(slug: string, language: Language): string | null {
  try {
    return window.localStorage.getItem(draftKey(slug, language));
  } catch {
    return null;
  }
}
function writeDraft(slug: string, language: Language, code: string | null) {
  try {
    if (code === null) window.localStorage.removeItem(draftKey(slug, language));
    else window.localStorage.setItem(draftKey(slug, language), code);
  } catch {
    /* storage unavailable: the code is simply not kept between visits */
  }
}

export function ProblemPage() {
  const { slug } = useParams<{ slug: string }>();
  const problem = useProblem(slug);
  if (problem.isPending) return <p className={muted}>Loading...</p>;
  if (problem.isError) {
    return (
      <p role="alert" className="text-danger-text">
        Could not load this problem. <Link href="/practice" className="underline">Back to practice</Link>
      </p>
    );
  }
  return <Workspace key={problem.data.slug} problem={problem.data} />;
}

function Workspace({ problem }: { problem: ProblemDetail }) {
  const languages = problem.specs.map((s) => s.language as Language);
  const [language, setLanguage] = useState<Language>(languages[0]);
  const starter = (lang: Language) => problem.specs.find((s) => s.language === lang)?.starter ?? "";
  const [codes, setCodes] = useState<Partial<Record<Language, string>>>({});
  const code = codes[language] ?? readDraft(problem.slug, language) ?? starter(language);

  const [summary, setSummary] = useState<RunSummary | null>(null);
  const [phase, setPhase] = useState<Phase | null>(null);
  const [running, setRunning] = useState(false);
  const submit = useSubmit(problem.slug);
  const history = useSubmissions(problem.slug);

  function setCode(next: string) {
    setCodes((current) => ({ ...current, [language]: next }));
    writeDraft(problem.slug, language, next);
  }

  async function run() {
    if (running) return;
    setRunning(true);
    setSummary(null);
    const result = await runProblem({ problem, language, code, onPhase: setPhase });
    setSummary(result);
    setRunning(false);
    setPhase(null);
    if (!result.fatal) {
      submit.mutate({
        language,
        code,
        passed: result.passed,
        total: result.total,
        runtime_ms: result.ms,
        results: result.outcomes.map((o) => ({ name: o.name, status: o.status })),
      });
    }
  }

  const solved = problem.status === "solved";

  return (
    <div className="grid gap-6 lg:grid-cols-2">
      <section className="space-y-4">
        <Link href="/practice" className={`${muted} hover:underline`}>
          &larr; All problems
        </Link>
        <header className="space-y-2">
          <h1 className="text-2xl font-semibold">{problem.title}</h1>
          <div className="flex flex-wrap items-center gap-2 text-sm">
            <DifficultyBadge difficulty={problem.difficulty} />
            {solved && <span className="text-success-text">Solved</span>}
            {problem.tags.map((tag) => (
              <span key={tag} className={muted}>#{tag}</span>
            ))}
          </div>
        </header>
        <article className="guide">
          <ReactMarkdown remarkPlugins={[remarkGfm]}>{problem.statement}</ReactMarkdown>
        </article>
        <Examples problem={problem} />
      </section>

      <section className="space-y-3">
        <div className="flex flex-wrap items-center gap-2">
          {languages.length > 1 && (
            <div role="group" aria-label="Language" className="flex">
              {languages.map((lang) => (
                <button
                  key={lang}
                  type="button"
                  aria-pressed={language === lang}
                  onClick={() => {
                    setLanguage(lang);
                    setSummary(null);
                  }}
                  className={`${button} ${language === lang ? "bg-surface-hover " : ""}`}
                >
                  {LABELS[lang]}
                </button>
              ))}
            </div>
          )}
          {languages.length === 1 && <span className="text-sm font-medium">{LABELS[language]}</span>}
          <div className="ml-auto flex gap-2">
            <button
              type="button"
              className={button}
              disabled={running}
              onClick={() => {
                writeDraft(problem.slug, language, null);
                setCodes((current) => ({ ...current, [language]: starter(language) }));
                setSummary(null);
              }}
            >
              Reset
            </button>
            <button type="button" className={primaryButton} disabled={running} onClick={run}>
              {running ? "Running..." : "Run tests"}
            </button>
          </div>
        </div>

        <CodeEditor
          value={code}
          language={language}
          label={`${LABELS[language]} solution for ${problem.title}`}
          onChange={setCode}
          onRun={run}
        />
        <p className={muted}>Tab indents. Press Escape, then Tab, to move focus out of the editor.</p>

        <ResultsPanel problem={problem} summary={summary} running={running} phase={phase} />
        {submit.isError && (
          <p role="alert" className="text-sm text-danger-text">
            Your result could not be saved: {submit.error.message}
          </p>
        )}

        <section className={`${card} space-y-2`}>
          <h2 className="font-semibold">Recent runs</h2>
          {history.data?.length === 0 && <p className={muted}>No runs yet.</p>}
          <ul className="space-y-1 text-sm">
            {history.data?.slice(0, 6).map((run) => (
              <li key={run.id} className="flex items-center justify-between gap-3">
                <span>
                  {LABELS[run.language as Language]} · {run.passed}/{run.total} passed ·{" "}
                  {new Date(run.created_at).toLocaleString("en-GB")}
                </span>
                <button
                  type="button"
                  className={button}
                  onClick={() => {
                    setLanguage(run.language as Language);
                    setCodes((current) => ({ ...current, [run.language]: run.code }));
                    writeDraft(problem.slug, run.language as Language, run.code);
                  }}
                >
                  Load code
                </button>
              </li>
            ))}
          </ul>
        </section>
      </section>
    </div>
  );
}

function Examples({ problem }: { problem: ProblemDetail }) {
  if (problem.kind === "sql") {
    const sample = problem.sql_tests.find((t) => !t.hidden);
    return (
      <section className={`${card} space-y-2 text-sm`}>
        <h2 className="font-semibold">Schema</h2>
        <pre className="overflow-x-auto whitespace-pre-wrap font-mono text-xs">{problem.sql_ddl}</pre>
        {sample && (
          <>
            <h2 className="font-semibold">Example: {sample.name}</h2>
            <pre className="overflow-x-auto whitespace-pre-wrap font-mono text-xs">{sample.data}</pre>
            <p className={muted}>Expected result</p>
            <pre className="overflow-x-auto font-mono text-xs">
              {JSON.stringify(sample.expected.columns)}
              {"\n"}
              {sample.expected.rows.map((row) => JSON.stringify(row)).join("\n")}
            </pre>
          </>
        )}
        <p className={muted}>Your query also runs against hidden datasets, so do not hard-code answers.</p>
      </section>
    );
  }
  const visible = problem.function_tests.filter((t) => !t.hidden);
  return (
    <section className={`${card} space-y-2 text-sm`}>
      <h2 className="font-semibold">Examples</h2>
      <ul className="space-y-2 font-mono text-xs">
        {visible.slice(0, 3).map((test) => (
          <li key={test.name}>
            <div className={muted}>{test.name}</div>
            <div>input: {JSON.stringify(test.args)}</div>
            <div>output: {JSON.stringify(test.expected)}</div>
          </li>
        ))}
      </ul>
      <p className={muted}>
        {problem.function_tests.length} tests in total; some are hidden edge cases.
      </p>
    </section>
  );
}

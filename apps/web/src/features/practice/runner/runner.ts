import { transform } from "sucrase";

import type { ProblemDetail } from "../hooks";

export type Language = "python" | "javascript" | "typescript" | "sql";
type Engine = "python" | "javascript" | "sql";
export type OutcomeStatus = "pass" | "fail" | "error" | "timeout" | "skipped";

export type Outcome = {
  index: number;
  name: string;
  hidden: boolean;
  status: OutcomeStatus;
  actual?: string;
  message?: string;
  stdout?: string;
  ms?: number;
};

export type RunSummary = {
  outcomes: Outcome[];
  passed: number;
  total: number;
  ms: number;
  /** Set when nothing could run at all (runtime failed to start, TypeScript syntax error...). */
  fatal?: string;
};

export type Phase = "loading" | "running";

const WORKERS: Record<Engine, string> = {
  python: "/runner/python-worker.js",
  javascript: "/runner/js-worker.js",
  sql: "/runner/sql-worker.js",
};

// Time to start a runtime (Python and SQL download it the first time) and per test afterwards.
// A test that runs past its limit is stopped by terminating the whole worker: the only way to
// interrupt code that never returns.
const START_LIMIT_MS: Record<Engine, number> = { python: 120_000, javascript: 10_000, sql: 120_000 };
const TEST_LIMIT_MS: Record<Engine, number> = { python: 5_000, javascript: 3_000, sql: 5_000 };

type WorkerMessage =
  | { type: "ready" }
  | { type: "progress"; id: number; outcome: Omit<Outcome, "hidden"> }
  | { type: "done"; id: number }
  | { type: "fatal"; id: number; message: string };

type Handle = { worker: Worker; ready: Promise<void> };
const handles = new Map<Engine, Handle>();
let nextRunId = 1;

function start(engine: Engine): Handle {
  const worker = new Worker(WORKERS[engine], { type: "module" });
  const ready = new Promise<void>((resolve, reject) => {
    const timer = setTimeout(() => reject(new Error("The runtime took too long to start.")), START_LIMIT_MS[engine]);
    const onMessage = (event: MessageEvent<WorkerMessage>) => {
      if (event.data.type !== "ready") return;
      clearTimeout(timer);
      worker.removeEventListener("message", onMessage);
      resolve();
    };
    worker.addEventListener("message", onMessage);
    worker.addEventListener("error", () => {
      clearTimeout(timer);
      reject(new Error("The runtime could not be loaded. Is the app serving /runner and /pyodide?"));
    }, { once: true });
  });
  ready.catch(() => stop(engine));
  const handle = { worker, ready };
  handles.set(engine, handle);
  return handle;
}

function stop(engine: Engine) {
  handles.get(engine)?.worker.terminate();
  handles.delete(engine);
}

/** The engine's worker, started on first use and kept warm for later runs. */
function engineFor(language: Language): Engine {
  return language === "typescript" ? "javascript" : language;
}

function prepareSource(language: Language, code: string): string {
  if (language !== "typescript") return code;
  // Types are removed, not checked: the tests decide what is correct.
  return transform(code, { transforms: ["typescript"], disableESTransforms: true }).code;
}

type TestInput = { index: number; name: string; hidden: boolean; payload: Record<string, unknown> };

function testsFor(problem: ProblemDetail): TestInput[] {
  if (problem.kind === "sql") {
    return problem.sql_tests.map((t, index) => ({
      index,
      name: t.name,
      hidden: t.hidden,
      payload: { data: t.data, expected: t.expected },
    }));
  }
  return problem.function_tests.map((t, index) => ({
    index,
    name: t.name,
    hidden: t.hidden,
    payload: { args: t.args, expected: t.expected, compare: t.compare },
  }));
}

export async function runProblem(options: {
  problem: ProblemDetail;
  language: Language;
  code: string;
  onPhase?: (phase: Phase) => void;
  onOutcome?: (outcome: Outcome) => void;
}): Promise<RunSummary> {
  const { problem, language, code, onPhase, onOutcome } = options;
  const began = performance.now();
  const tests = testsFor(problem);
  const empty = (fatal: string): RunSummary => ({
    outcomes: [],
    passed: 0,
    total: tests.length,
    ms: Math.round(performance.now() - began),
    fatal,
  });

  let source: string;
  try {
    source = prepareSource(language, code);
  } catch (error) {
    return empty(`TypeScript syntax error: ${error instanceof Error ? error.message : String(error)}`);
  }
  const spec = problem.specs.find((s) => s.language === language);
  if (!spec) return empty(`${language} is not available for this problem.`);

  const engine = engineFor(language);
  onPhase?.("loading");
  const handle = handles.get(engine) ?? start(engine);
  try {
    await handle.ready;
  } catch (error) {
    return empty(error instanceof Error ? error.message : "The runtime failed to start.");
  }
  onPhase?.("running");

  const runId = nextRunId++;
  const outcomes: Outcome[] = [];
  const hiddenAt = new Map(tests.map((t) => [t.index, t.hidden]));

  return new Promise<RunSummary>((resolve) => {
    const worker = handle.worker;
    let timer: ReturnType<typeof setTimeout>;

    const finish = (fatal?: string) => {
      clearTimeout(timer);
      worker.removeEventListener("message", onMessage);
      worker.removeEventListener("error", onError);
      resolve({
        outcomes,
        passed: outcomes.filter((o) => o.status === "pass").length,
        total: tests.length,
        ms: Math.round(performance.now() - began),
        fatal,
      });
    };

    // Tests run in order, so the first one without an outcome is the one that hung.
    const onTimeout = () => {
      stop(engine);
      const stuck = tests[outcomes.length];
      outcomes.push({
        index: stuck.index,
        name: stuck.name,
        hidden: stuck.hidden,
        status: "timeout",
        message: `Stopped after ${TEST_LIMIT_MS[engine] / 1000} seconds. Is there an infinite loop?`,
      });
      for (const rest of tests.slice(outcomes.length)) {
        outcomes.push({ index: rest.index, name: rest.name, hidden: rest.hidden, status: "skipped" });
      }
      finish();
    };
    const arm = () => {
      clearTimeout(timer);
      timer = setTimeout(onTimeout, TEST_LIMIT_MS[engine]);
    };

    const onMessage = (event: MessageEvent<WorkerMessage>) => {
      const message = event.data;
      if (message.type === "ready" || message.id !== runId) return;
      if (message.type === "progress") {
        const outcome = { ...message.outcome, hidden: hiddenAt.get(message.outcome.index) ?? false };
        outcomes.push(outcome);
        onOutcome?.(outcome);
        arm();
      } else if (message.type === "done") {
        finish();
      } else {
        stop(engine);
        finish(message.message);
      }
    };
    const onError = () => {
      stop(engine);
      finish("The runner crashed. Try again.");
    };

    worker.addEventListener("message", onMessage);
    worker.addEventListener("error", onError, { once: true });
    arm();
    worker.postMessage({
      type: "run",
      id: runId,
      source,
      entry: spec.entry,
      schema: problem.sql_ddl,
      tests: tests.map((t) => ({ index: t.index, name: t.name, ...t.payload })),
    });
  });
}

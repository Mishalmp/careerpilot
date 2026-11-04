import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import type { ProblemDetail } from "../hooks";

type Listener = (event: { data?: unknown }) => void;
type Sent = { id: number; tests: { index: number; name: string }[] };

/** A stand-in for a browser Worker whose behaviour each test scripts. */
class FakeWorker {
  static all: FakeWorker[] = [];
  static onRun: (worker: FakeWorker, message: Sent) => void = () => {};
  static startsReady = true;
  listeners: Record<string, Listener[]> = { message: [], error: [] };
  terminated = false;

  constructor(readonly url: string) {
    FakeWorker.all.push(this);
    if (FakeWorker.startsReady) queueMicrotask(() => this.emit({ type: "ready" }));
  }
  addEventListener(type: string, listener: Listener) {
    this.listeners[type].push(listener);
  }
  removeEventListener(type: string, listener: Listener) {
    this.listeners[type] = this.listeners[type].filter((l) => l !== listener);
  }
  postMessage(message: Sent) {
    FakeWorker.onRun(this, message);
  }
  terminate() {
    this.terminated = true;
  }
  emit(data: unknown) {
    for (const listener of [...this.listeners.message]) listener({ data });
  }
  fail() {
    for (const listener of [...this.listeners.error]) listener({});
  }
}

const problem = {
  slug: "p",
  title: "P",
  kind: "function",
  specs: [
    { language: "python", starter: "", entry: "f" },
    { language: "javascript", starter: "", entry: "f" },
    { language: "typescript", starter: "", entry: "f" },
  ],
  function_tests: [
    { name: "a", hidden: false, args: [], expected: 1, compare: "exact" },
    { name: "b", hidden: true, args: [], expected: 2, compare: "exact" },
    { name: "c", hidden: false, args: [], expected: 3, compare: "exact" },
  ],
  sql_tests: [],
  sql_ddl: null,
} as unknown as ProblemDetail;

const outcome = (index: number, status = "pass") => ({ index, name: "x", status, ms: 1 });

async function load() {
  vi.resetModules();
  return (await import("./runner")).runProblem;
}

beforeEach(() => {
  FakeWorker.all = [];
  FakeWorker.startsReady = true;
  FakeWorker.onRun = () => {};
  vi.stubGlobal("Worker", FakeWorker);
  vi.useFakeTimers();
});
afterEach(() => {
  vi.useRealTimers();
  vi.unstubAllGlobals();
});

describe("runProblem", () => {
  it("collects every outcome and marks hidden tests", async () => {
    FakeWorker.onRun = (worker, { id, tests }) => {
      for (const t of tests) worker.emit({ type: "progress", id, outcome: outcome(t.index, t.index === 1 ? "fail" : "pass") });
      worker.emit({ type: "done", id });
    };
    const runProblem = await load();
    const summary = await runProblem({ problem, language: "javascript", code: "x" });
    expect(summary).toMatchObject({ passed: 2, total: 3 });
    expect(summary.outcomes.map((o) => o.hidden)).toEqual([false, true, false]);
    expect(summary.fatal).toBeUndefined();
  });

  it("stops a test that never returns and reports the rest as not run", async () => {
    FakeWorker.onRun = (worker, { id }) => worker.emit({ type: "progress", id, outcome: outcome(0) });
    const runProblem = await load();
    const pending = runProblem({ problem, language: "javascript", code: "x" });
    await vi.advanceTimersByTimeAsync(3_000);
    const summary = await pending;

    expect(summary.outcomes.map((o) => o.status)).toEqual(["pass", "timeout", "skipped"]);
    expect(summary.outcomes[1].message).toMatch(/infinite loop/);
    expect(FakeWorker.all[0].terminated).toBe(true);
  });

  it("starts a fresh worker after one was stopped", async () => {
    FakeWorker.onRun = () => {}; // never answers
    const runProblem = await load();
    const first = runProblem({ problem, language: "javascript", code: "x" });
    await vi.advanceTimersByTimeAsync(3_000);
    await first;

    FakeWorker.onRun = (worker, { id }) => worker.emit({ type: "done", id });
    const second = await runProblem({ problem, language: "javascript", code: "x" });
    expect(FakeWorker.all).toHaveLength(2);
    expect(second.fatal).toBeUndefined();
  });

  it("reuses a healthy worker between runs", async () => {
    FakeWorker.onRun = (worker, { id }) => worker.emit({ type: "done", id });
    const runProblem = await load();
    await runProblem({ problem, language: "javascript", code: "x" });
    await runProblem({ problem, language: "javascript", code: "y" });
    expect(FakeWorker.all).toHaveLength(1);
  });

  it("runs TypeScript on the JavaScript worker after removing types", async () => {
    let sent = "";
    FakeWorker.onRun = (worker, message) => {
      sent = (message as unknown as { source: string }).source;
      worker.emit({ type: "done", id: message.id });
    };
    const runProblem = await load();
    await runProblem({ problem, language: "typescript", code: "function f(a: number): number { return a }" });
    expect(FakeWorker.all[0].url).toBe("/runner/js-worker.js");
    expect(sent).not.toContain(": number");
    expect(sent).toContain("function f(a)");
  });

  it("reports a TypeScript syntax error without starting a worker", async () => {
    const runProblem = await load();
    const summary = await runProblem({ problem, language: "typescript", code: "function f( {" });
    expect(summary.fatal).toMatch(/TypeScript syntax error/);
    expect(FakeWorker.all).toHaveLength(0);
  });

  it("reports a runtime that fails to load, and recovers on the next run", async () => {
    FakeWorker.startsReady = false;
    const runProblem = await load();
    const pending = runProblem({ problem, language: "python", code: "x" });
    await vi.advanceTimersByTimeAsync(0);
    FakeWorker.all[0].fail();
    expect((await pending).fatal).toMatch(/could not be loaded/);

    FakeWorker.startsReady = true;
    FakeWorker.onRun = (worker, { id }) => worker.emit({ type: "done", id });
    const retry = await runProblem({ problem, language: "python", code: "x" });
    expect(retry.fatal).toBeUndefined();
    expect(FakeWorker.all).toHaveLength(2);
  });

  it("gives up if the runtime never starts", async () => {
    FakeWorker.startsReady = false;
    const runProblem = await load();
    const pending = runProblem({ problem, language: "python", code: "x" });
    await vi.advanceTimersByTimeAsync(120_000);
    expect((await pending).fatal).toMatch(/too long to start/);
    expect(FakeWorker.all[0].terminated).toBe(true);
  });

  it("surfaces a fatal message from the worker and drops that worker", async () => {
    FakeWorker.onRun = (worker, { id }) => worker.emit({ type: "fatal", id, message: "Could not start Python" });
    const runProblem = await load();
    const summary = await runProblem({ problem, language: "python", code: "x" });
    expect(summary.fatal).toBe("Could not start Python");
    expect(FakeWorker.all[0].terminated).toBe(true);
  });

  it("refuses a language the problem does not offer", async () => {
    const runProblem = await load();
    const summary = await runProblem({ problem, language: "sql", code: "select 1" });
    expect(summary.fatal).toMatch(/not available/);
  });

  it("reports progress phases to the caller", async () => {
    FakeWorker.onRun = (worker, { id }) => worker.emit({ type: "done", id });
    const runProblem = await load();
    const phases: string[] = [];
    await runProblem({ problem, language: "javascript", code: "x", onPhase: (p) => phases.push(p) });
    expect(phases).toEqual(["loading", "running"]);
  });
});

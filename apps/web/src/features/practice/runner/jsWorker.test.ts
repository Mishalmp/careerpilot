import { readFileSync } from "node:fs";
import { fileURLToPath } from "node:url";
import vm from "node:vm";

import { describe, expect, it } from "vitest";

// These tests load the real worker file that the browser runs, in a bare context that only has
// `self`, `console` and a few built-ins, like a worker.
const workerPath = fileURLToPath(new URL("../../../../public/runner/js-worker.js", import.meta.url));
const casesPath = fileURLToPath(new URL("../../../../public/runner/compare-cases.json", import.meta.url));
const workerSource = readFileSync(workerPath, "utf8");
const cases = JSON.parse(readFileSync(casesPath, "utf8")) as {
  name: string;
  mode: string;
  actual: unknown;
  expected: unknown;
  equal: boolean;
}[];

type Outcome = { status: string; actual: string; message: string; stdout: string };
type Message = { type: string; outcome?: Outcome; message?: string };

async function run(source: string, entry: string, tests: unknown[]): Promise<Message[]> {
  const messages: Message[] = [];
  const self: { postMessage: (m: Message) => void; onmessage?: (e: { data: unknown }) => Promise<void> } = {
    postMessage: (m) => messages.push(m),
  };
  vm.runInNewContext(workerSource, { self, console: { ...console }, performance, structuredClone });
  await self.onmessage!({ data: { type: "run", id: 1, source, entry, tests } });
  return messages.filter((m) => m.type !== "ready");
}

const one = (args: unknown[], expected: unknown, compare = "exact") => ({ index: 0, name: "t", args, expected, compare });

async function outcome(source: string, test: ReturnType<typeof one>, entry = "f"): Promise<Outcome> {
  const messages = await run(source, entry, [test]);
  const progress = messages.find((m) => m.type === "progress");
  if (!progress?.outcome) throw new Error(`no outcome: ${JSON.stringify(messages)}`);
  return progress.outcome;
}

describe("js-worker.js", () => {
  it("reports pass and fail with the actual value", async () => {
    expect((await outcome("function f(a, b) { return a + b }", one([2, 3], 5))).status).toBe("pass");
    const wrong = await outcome("function f(a, b) { return a + b }", one([2, 2], 5));
    expect(wrong).toMatchObject({ status: "fail", actual: "4" });
  });

  it("finishes with a done message after every test", async () => {
    const messages = await run("function f(x) { return x }", "f", [
      { index: 0, name: "a", args: [1], expected: 1, compare: "exact" },
      { index: 1, name: "b", args: [2], expected: 3, compare: "exact" },
    ]);
    expect(messages.map((m) => m.type)).toEqual(["progress", "progress", "done"]);
  });

  it("captures console output, including from a failing test", async () => {
    const result = await outcome('function f() { console.log("hi", {a: 1}); return 0 }', one([], 1));
    expect(result).toMatchObject({ status: "fail", stdout: 'hi {"a":1}' });
  });

  it("supports async functions", async () => {
    expect((await outcome("async function f() { return 7 }", one([], 7))).status).toBe("pass");
  });

  it("reports thrown errors and missing functions", async () => {
    const thrown = await outcome('function f() { throw new RangeError("too big") }', one([], 1));
    expect(thrown).toMatchObject({ status: "error", message: "RangeError: too big" });
    const missing = await outcome("function other() {}", one([], 1));
    expect(missing).toMatchObject({ status: "error", message: "ReferenceError: Define a function named f" });
    const syntax = await outcome("function f( {", one([], 1));
    expect(syntax).toMatchObject({ status: "error" });
    expect(syntax.message).toMatch(/SyntaxError/);
  });

  it("treats undefined as null and rejects values that are not JSON", async () => {
    expect((await outcome("function f() {}", one([], null))).status).toBe("pass");
    const cyclic = await outcome("function f() { const a = {}; a.a = a; return a }", one([], 1));
    expect(cyclic.status).toBe("error");
  });

  it("does not let one test change the arguments of the next", async () => {
    const shared = [[3, 1, 2]];
    const messages = await run("function f(xs) { xs.sort(); return xs }", "f", [
      { index: 0, name: "a", args: shared, expected: [1, 2, 3], compare: "exact" },
      { index: 1, name: "b", args: shared, expected: [1, 2, 3], compare: "exact" },
    ]);
    expect(messages.filter((m) => m.outcome?.status === "pass")).toHaveLength(2);
  });

  it("refuses an entry name that is not a plain identifier", async () => {
    const messages = await run("", "f(); alert(1); function g", [one([], 1)]);
    expect(messages).toEqual([{ type: "fatal", id: 1, message: expect.stringContaining("Invalid") }]);
  });

  it.each(cases)("comparison: $name", async ({ mode, actual, expected, equal }) => {
    const source = `function f() { return ${JSON.stringify(actual)} }`;
    const result = await outcome(source, one([], expected, mode));
    expect(result.status).toBe(equal ? "pass" : "fail");
  });
});

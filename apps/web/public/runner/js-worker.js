// Runs the learner's JavaScript (TypeScript is converted before it gets here).
// This file is served with its own Content-Security-Policy (see next.config.ts): no network at
// all and no other scripts, so learner code cannot reach this app's API. Plain script, no imports.

const MAX_TEXT = 2000;
const clip = (text) => (text.length <= MAX_TEXT ? text : `${text.slice(0, MAX_TEXT)}... (truncated)`);

const isNumber = (v) => typeof v === "number";
const sortKey = (v) => JSON.stringify(v);

/** Strict deep equality. `tolerance` allows float error. Mirrors harness.py. */
function same(actual, expected, tolerance = 0) {
  if (isNumber(actual) && isNumber(expected)) {
    if (!tolerance) return actual === expected;
    const diff = Math.abs(actual - expected);
    return diff <= tolerance || diff <= tolerance * Math.max(Math.abs(actual), Math.abs(expected));
  }
  if (Array.isArray(actual) && Array.isArray(expected)) {
    return actual.length === expected.length && actual.every((v, i) => same(v, expected[i], tolerance));
  }
  if (actual && expected && typeof actual === "object" && typeof expected === "object") {
    const keys = Object.keys(actual);
    return (
      keys.length === Object.keys(expected).length &&
      keys.every((k) => k in expected && same(actual[k], expected[k], tolerance))
    );
  }
  return actual === expected;
}

const unordered = (items) => [...items].sort((a, b) => (sortKey(a) < sortKey(b) ? -1 : sortKey(a) > sortKey(b) ? 1 : 0));
const nestedUnordered = (groups) => unordered(groups.map(unordered));

function equal(actual, expected, mode = "exact") {
  if (mode === "float") return same(actual, expected, 1e-6);
  if (mode === "unordered") return Array.isArray(actual) && same(unordered(actual), unordered(expected));
  if (mode === "unordered_nested") {
    return (
      Array.isArray(actual) &&
      actual.every(Array.isArray) &&
      same(nestedUnordered(actual), nestedUnordered(expected))
    );
  }
  return same(actual, expected);
}

/** JSON round trip, like the Python side. `undefined` becomes null; functions and cycles throw. */
function normalise(value) {
  return value === undefined ? null : JSON.parse(JSON.stringify(value));
}

const format = (arg) => {
  if (typeof arg === "string") return arg;
  try {
    return JSON.stringify(arg);
  } catch {
    return String(arg);
  }
};

async function runTest(source, entry, test) {
  const lines = [];
  const log = (...args) => lines.push(args.map(format).join(" "));
  const original = { ...console };
  console.log = console.info = console.warn = console.error = log;

  const result = { status: "error", actual: "", message: "", stdout: "" };
  try {
    // `entry` comes from the problem file and is checked below; the source is the learner's own.
    const factory = new Function(`${source}\n;return typeof ${entry} === "function" ? ${entry} : undefined;`);
    const fn = factory();
    if (typeof fn !== "function") throw new ReferenceError(`Define a function named ${entry}`);
    const actual = normalise(await fn(...structuredClone(test.args)));
    result.actual = clip(JSON.stringify(actual));
    result.status = equal(actual, test.expected, test.compare) ? "pass" : "fail";
  } catch (error) {
    result.message = clip(error instanceof Error ? `${error.name}: ${error.message}` : String(error));
  } finally {
    Object.assign(console, original);
    result.stdout = clip(lines.join("\n"));
  }
  return result;
}

self.onmessage = async (event) => {
  const { type, id, source, entry, tests } = event.data;
  if (type !== "run") return;
  if (!/^[A-Za-z_$][\w$]*$/.test(entry)) {
    self.postMessage({ type: "fatal", id, message: "Invalid function name in the problem file." });
    return;
  }
  for (const test of tests) {
    const started = performance.now();
    const outcome = await runTest(source, entry, test);
    self.postMessage({
      type: "progress",
      id,
      outcome: { index: test.index, name: test.name, ms: Math.round(performance.now() - started), ...outcome },
    });
  }
  self.postMessage({ type: "done", id });
};

self.postMessage({ type: "ready" });

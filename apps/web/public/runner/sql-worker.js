// Runs the learner's SQL on PGlite (PostgreSQL compiled to WebAssembly), served by this app.
// Each test gets an empty schema, the problem's tables and that test's data, so a query that
// hard-codes the sample answer fails on the next dataset.
import { PGlite } from "/runner/pglite/index.js";

let db;
const starting = (async () => {
  db = await PGlite.create();
  self.postMessage({ type: "ready" });
})();

const EPSILON = 1e-6;

/** Make database values comparable: bigint and numeric become numbers, dates become strings. */
function cell(value) {
  if (value === null || value === undefined) return null;
  if (typeof value === "bigint") return Number(value);
  if (value instanceof Date) return value.toISOString().replace(/T00:00:00\.000Z$/, "");
  if (typeof value === "string" && /^-?\d+(\.\d+)?$/.test(value.trim())) return Number(value);
  return value;
}

const sameCell = (a, b) =>
  typeof a === "number" && typeof b === "number" ? Math.abs(a - b) <= EPSILON : a === b;

const rowKey = (row) => JSON.stringify(row.map((c) => (typeof c === "number" ? Number(c.toFixed(6)) : c)));
const sameRow = (a, b) => a.length === b.length && a.every((c, i) => sameCell(c, b[i]));

function compare(actual, expected) {
  const wanted = expected.columns.map((c) => c.toLowerCase());
  const got = actual.columns.map((c) => c.toLowerCase());
  if (JSON.stringify(wanted) !== JSON.stringify(got)) {
    return `Expected columns [${wanted.join(", ")}] but got [${got.join(", ")}].`;
  }
  const want = expected.rows.map((r) => r.map(cell));
  let have = actual.rows.map((r) => r.map(cell));
  if (have.length !== want.length) return `Expected ${want.length} rows but got ${have.length}.`;
  let target = want;
  if (!expected.ordered) {
    const byKey = (a, b) => (rowKey(a) < rowKey(b) ? -1 : rowKey(a) > rowKey(b) ? 1 : 0);
    have = [...have].sort(byKey);
    target = [...want].sort(byKey);
  }
  const bad = target.findIndex((row, i) => !sameRow(row, have[i]));
  return bad === -1 ? null : `Row ${bad + 1} differs.`;
}

async function runTest(query, schema, test) {
  const result = { status: "error", actual: "", message: "", stdout: "" };
  try {
    await db.exec("DROP SCHEMA IF EXISTS public CASCADE; CREATE SCHEMA public;");
    await db.exec(`${schema}\n${test.data ?? ""}`);
    const results = await db.exec(query, { rowMode: "array" });
    const last = results[results.length - 1];
    if (!last || !last.fields.length) throw new Error("The query returned no result set. Use SELECT.");
    const actual = { columns: last.fields.map((f) => f.name), rows: last.rows };
    const shown = { columns: actual.columns, rows: actual.rows.slice(0, 20).map((r) => r.map(cell)) };
    result.actual = JSON.stringify(shown);
    const problem = compare(actual, test.expected);
    result.status = problem ? "fail" : "pass";
    result.message = problem ?? "";
  } catch (error) {
    result.message = String(error instanceof Error ? error.message : error).slice(0, 2000);
  }
  return result;
}

self.onmessage = async (event) => {
  const { type, id, source, schema, tests } = event.data;
  if (type !== "run") return;
  try {
    await starting;
  } catch (error) {
    self.postMessage({ type: "fatal", id, message: `Could not start the SQL engine: ${error}` });
    return;
  }
  for (const test of tests) {
    const started = performance.now();
    const outcome = await runTest(source, schema, test);
    self.postMessage({
      type: "progress",
      id,
      outcome: { index: test.index, name: test.name, ms: Math.round(performance.now() - started), ...outcome },
    });
  }
  self.postMessage({ type: "done", id });
};
